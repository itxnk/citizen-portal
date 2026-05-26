"""
User Service
Manages citizen user profiles in PostgreSQL.
No cache dependency — demonstrates service isolation.
"""
import os
import time
import logging
from contextlib import asynccontextmanager
from typing import Optional

import asyncpg
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Prometheus ───────────────────────────────────────────────────────────────
USERS_CREATED  = Counter("users_created_total", "Total users created")
DB_LATENCY     = Histogram("db_query_duration_seconds", "DB query latency", ["operation", "status"],
                           buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5])
DB_CONNECTIONS = Gauge("db_connections_active", "Active DB pool connections")

db_pool: Optional[asyncpg.Pool] = None

SEED_USERS = [
    ("Ahmed Khan",      "ahmed.khan@desc.gov.pk",    "admin"),
    ("Fatima Bibi",     "fatima.bibi@desc.gov.pk",   "officer"),
    ("Tariq Mehmood",   "tariq@desc.gov.pk",         "citizen"),
    ("Zainab Hussain",  "zainab@desc.gov.pk",        "citizen"),
    ("Imran Gul",       "imran.gul@desc.gov.pk",     "officer"),
]

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool
    db_url = os.getenv("DATABASE_URL", "postgresql://descadmin:devpassword123@localhost:5432/descapp")
    db_pool = await asyncpg.create_pool(db_url, min_size=2, max_size=8)
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id         SERIAL PRIMARY KEY,
                name       TEXT NOT NULL,
                email      TEXT UNIQUE NOT NULL,
                role       TEXT NOT NULL DEFAULT 'citizen',
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        for name, email, role in SEED_USERS:
            await conn.execute(
                "INSERT INTO users (name, email, role) VALUES ($1, $2, $3) ON CONFLICT (email) DO NOTHING",
                name, email, role
            )
    logger.info("User Service ready — DB connected, seed data loaded")
    yield
    await db_pool.close()

app = FastAPI(title="DESC User Service", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class UserCreate(BaseModel):
    name: str
    email: str
    role: str = "citizen"

@app.get("/health")
async def health():
    return {"status": "ok", "service": "user-service"}

@app.get("/ready")
async def ready():
    try:
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "ready", "database": "ok"}
    except Exception as e:
        raise HTTPException(status_code=503, detail={"database": str(e)})

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/users")
async def list_users():
    start = time.time()
    try:
        async with db_pool.acquire() as conn:
            DB_CONNECTIONS.inc()
            rows = await conn.fetch(
                "SELECT id, name, email, role, created_at::text FROM users ORDER BY id DESC LIMIT 100"
            )
            DB_CONNECTIONS.dec()
        DB_LATENCY.labels("select", "success").observe(time.time() - start)
        return {"users": [dict(r) for r in rows]}
    except Exception as e:
        DB_LATENCY.labels("select", "error").observe(time.time() - start)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/users", status_code=201)
async def create_user(user: UserCreate):
    start = time.time()
    try:
        async with db_pool.acquire() as conn:
            DB_CONNECTIONS.inc()
            row = await conn.fetchrow(
                "INSERT INTO users (name, email, role) VALUES ($1, $2, $3) "
                "RETURNING id, name, email, role, created_at::text",
                user.name, user.email, user.role
            )
            DB_CONNECTIONS.dec()
        DB_LATENCY.labels("insert", "success").observe(time.time() - start)
        USERS_CREATED.inc()
        return dict(row)
    except asyncpg.UniqueViolationError:
        raise HTTPException(status_code=409, detail="Email already exists")
    except Exception as e:
        DB_LATENCY.labels("insert", "error").observe(time.time() - start)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, name, email, role, created_at::text FROM users WHERE id = $1", user_id
        )
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return dict(row)
