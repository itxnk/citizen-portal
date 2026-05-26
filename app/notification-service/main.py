"""
Notification Service
Manages system announcements in PostgreSQL.
Publishes to Redis pub/sub on every new notification — demonstrates event-driven pattern.
"""
import os
import time
import json
import logging
from contextlib import asynccontextmanager
from typing import Optional, Literal

import asyncpg
import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REDIS_CHANNEL = "desc:notifications"

# ─── Prometheus ───────────────────────────────────────────────────────────────
NOTIFICATIONS_SENT  = Counter("notifications_sent_total", "Total notifications published", ["type"])
DB_LATENCY          = Histogram("db_query_duration_seconds", "DB query latency", ["operation", "status"],
                                buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5])
REDIS_PUB_LATENCY   = Histogram("redis_publish_latency_seconds", "Redis publish latency",
                                 buckets=[0.001, 0.005, 0.01, 0.05, 0.1])

db_pool: Optional[asyncpg.Pool] = None
redis_client: Optional[aioredis.Redis] = None

SEED_NOTIFICATIONS = [
    ("System Maintenance", "Scheduled maintenance on Sunday 01:00–03:00 AM", "info"),
    ("New Feature Launch", "Citizen portal upgraded to cloud-native architecture", "success"),
    ("Service Degradation", "Resolved: connectivity issue in AZ-b — now fully restored", "warning"),
]

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool, redis_client
    db_url    = os.getenv("DATABASE_URL", "postgresql://descadmin:devpassword123@localhost:5432/descapp")
    redis_url = os.getenv("REDIS_URL",    "redis://localhost:6379")

    db_pool = await asyncpg.create_pool(db_url, min_size=2, max_size=6)
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id         SERIAL PRIMARY KEY,
                title      TEXT NOT NULL,
                message    TEXT NOT NULL,
                type       TEXT NOT NULL DEFAULT 'info',
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        for title, message, ntype in SEED_NOTIFICATIONS:
            await conn.execute(
                "INSERT INTO notifications (title, message, type) "
                "SELECT $1, $2, $3 WHERE NOT EXISTS (SELECT 1 FROM notifications WHERE title = $1)",
                title, message, ntype
            )
    logger.info("Notification Service DB ready with seed data")

    try:
        redis_client = aioredis.from_url(redis_url, decode_responses=True)
        await redis_client.ping()
        logger.info("Notification Service Redis connected — publishing to channel: %s", REDIS_CHANNEL)
    except Exception as e:
        logger.warning("Redis unavailable — pub/sub disabled: %s", e)

    yield
    await db_pool.close()
    if redis_client:
        await redis_client.close()

app = FastAPI(title="DESC Notification Service", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class NotificationCreate(BaseModel):
    title: str
    message: str
    type: Literal["info", "success", "warning", "error"] = "info"

@app.get("/health")
async def health():
    return {"status": "ok", "service": "notification-service"}

@app.get("/ready")
async def ready():
    checks: dict = {}
    try:
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = str(e)
    try:
        if redis_client:
            await redis_client.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = str(e)
    if checks.get("database") != "ok":
        raise HTTPException(status_code=503, detail=checks)
    return {"status": "ready", "checks": checks}

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/notifications")
async def list_notifications():
    start = time.time()
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, title, message, type, created_at::text "
                "FROM notifications ORDER BY id DESC LIMIT 50"
            )
        DB_LATENCY.labels("select", "success").observe(time.time() - start)
        return {"notifications": [dict(r) for r in rows]}
    except Exception as e:
        DB_LATENCY.labels("select", "error").observe(time.time() - start)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/notifications", status_code=201)
async def create_notification(notif: NotificationCreate):
    start = time.time()
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO notifications (title, message, type) VALUES ($1, $2, $3) "
                "RETURNING id, title, message, type, created_at::text",
                notif.title, notif.message, notif.type
            )
        DB_LATENCY.labels("insert", "success").observe(time.time() - start)
    except Exception as e:
        DB_LATENCY.labels("insert", "error").observe(time.time() - start)
        raise HTTPException(status_code=500, detail=str(e))

    result = dict(row)

    # Publish event to Redis for any downstream consumers (e.g., WebSocket service)
    if redis_client:
        try:
            pub_start = time.time()
            await redis_client.publish(REDIS_CHANNEL, json.dumps(result))
            REDIS_PUB_LATENCY.observe(time.time() - pub_start)
            logger.info("Published notification id=%s to channel %s", result["id"], REDIS_CHANNEL)
        except Exception as e:
            logger.warning("Redis publish failed (non-fatal): %s", e)

    NOTIFICATIONS_SENT.labels(notif.type).inc()
    return result
