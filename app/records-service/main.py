"""
Records Service
Manages citizen records/applications in PostgreSQL with Redis cache-aside.
Also exposes /stress — the CPU-intensive endpoint that k6 targets to trigger HPA.
"""
import os
import time
import json
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

import asyncpg
import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Prometheus ───────────────────────────────────────────────────────────────
RECORDS_CREATED = Counter("records_created_total", "Total records created")
DB_LATENCY      = Histogram("db_query_duration_seconds", "DB query latency", ["operation", "status"],
                            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5])
CACHE_HITS      = Counter("cache_hits_total", "Redis cache hits")
CACHE_MISSES    = Counter("cache_misses_total", "Redis cache misses")
DB_CONNECTIONS  = Gauge("db_connections_active", "Active DB pool connections")

db_pool: Optional[asyncpg.Pool] = None
redis_client: Optional[aioredis.Redis] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool, redis_client
    db_url    = os.getenv("DATABASE_URL", "postgresql://descadmin:devpassword123@localhost:5432/descapp")
    redis_url = os.getenv("REDIS_URL",    "redis://localhost:6379")

    db_pool = await asyncpg.create_pool(db_url, min_size=2, max_size=10)
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS records (
                id          SERIAL PRIMARY KEY,
                title       TEXT NOT NULL,
                description TEXT,
                status      TEXT NOT NULL DEFAULT 'pending',
                created_at  TIMESTAMP DEFAULT NOW()
            )
        """)
    logger.info("Records Service DB ready")

    try:
        redis_client = aioredis.from_url(redis_url, decode_responses=True)
        await redis_client.ping()
        logger.info("Records Service Redis connected")
    except Exception as e:
        logger.warning("Redis unavailable — cache disabled: %s", e)

    yield
    await db_pool.close()
    if redis_client:
        await redis_client.close()

app = FastAPI(title="DESC Records Service", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class RecordCreate(BaseModel):
    title: str
    description: Optional[str] = None
    status: str = "pending"

@app.get("/health")
async def health():
    return {"status": "ok", "service": "records-service"}

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

@app.get("/records")
async def list_records():
    cache_key = "records:all"
    if redis_client:
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                CACHE_HITS.inc()
                return {"records": json.loads(cached), "source": "cache"}
        except Exception:
            pass
    CACHE_MISSES.inc()

    start = time.time()
    try:
        async with db_pool.acquire() as conn:
            DB_CONNECTIONS.inc()
            rows = await conn.fetch(
                "SELECT id, title, description, status, created_at::text FROM records ORDER BY id DESC LIMIT 50"
            )
            DB_CONNECTIONS.dec()
        DB_LATENCY.labels("select", "success").observe(time.time() - start)
    except Exception as e:
        DB_LATENCY.labels("select", "error").observe(time.time() - start)
        raise HTTPException(status_code=500, detail=str(e))

    records = [dict(r) for r in rows]
    if redis_client:
        try:
            await redis_client.setex(cache_key, 30, json.dumps(records))
        except Exception:
            pass
    return {"records": records, "source": "database"}

@app.post("/records", status_code=201)
async def create_record(record: RecordCreate):
    start = time.time()
    try:
        async with db_pool.acquire() as conn:
            DB_CONNECTIONS.inc()
            row = await conn.fetchrow(
                "INSERT INTO records (title, description, status) VALUES ($1, $2, $3) "
                "RETURNING id, title, description, status, created_at::text",
                record.title, record.description, record.status
            )
            DB_CONNECTIONS.dec()
        DB_LATENCY.labels("insert", "success").observe(time.time() - start)
    except Exception as e:
        DB_LATENCY.labels("insert", "error").observe(time.time() - start)
        raise HTTPException(status_code=500, detail=str(e))

    if redis_client:
        try:
            await redis_client.delete("records:all")
        except Exception:
            pass
    RECORDS_CREATED.inc()
    return dict(row)

@app.get("/stress")
async def stress(n: int = 8000):
    """CPU-intensive endpoint — triggers HPA scaling when hammered by k6."""
    def count_primes(limit: int) -> int:
        count = 0
        for num in range(2, limit):
            if all(num % i != 0 for i in range(2, int(num**0.5) + 1)):
                count += 1
        return count

    loop = asyncio.get_event_loop()
    primes = await loop.run_in_executor(None, count_primes, n)
    return {"primes_found": primes, "upper_limit": n, "service": "records-service",
            "pod": os.getenv("POD_NAME", "local")}
