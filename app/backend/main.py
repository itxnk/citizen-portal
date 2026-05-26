import os
import time
import logging
import asyncio
from contextlib import asynccontextmanager
from typing import Optional

import asyncpg
import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from prometheus_client import (
    Counter, Histogram, Gauge, generate_latest,
    CONTENT_TYPE_LATEST, CollectorRegistry, multiprocess
)
from fastapi.responses import Response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Prometheus Metrics ───────────────────────────────────────────────────────
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"]
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)
DB_QUERY_LATENCY = Histogram(
    "db_query_duration_seconds",
    "Database query latency",
    ["operation", "status"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0]
)
CACHE_HITS = Counter("cache_hits_total", "Redis cache hits")
CACHE_MISSES = Counter("cache_misses_total", "Redis cache misses")
DB_CONNECTIONS = Gauge("db_connections_active", "Active DB connections")
ITEMS_CREATED = Counter("items_created_total", "Total items created")

# ─── App State ────────────────────────────────────────────────────────────────
class AppState:
    db_pool: Optional[asyncpg.Pool] = None
    redis_client: Optional[aioredis.Redis] = None

app_state = AppState()

@asynccontextmanager
async def lifespan(app: FastAPI):
    db_url = os.getenv("DATABASE_URL", "postgresql://descadmin:password@localhost:5432/descapp")
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

    try:
        app_state.db_pool = await asyncpg.create_pool(db_url, min_size=2, max_size=10)
        async with app_state.db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS items (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
        logger.info("Database connected and schema ready")
    except Exception as e:
        logger.error("Database connection failed: %s", e)

    try:
        app_state.redis_client = aioredis.from_url(redis_url, decode_responses=True)
        await app_state.redis_client.ping()
        logger.info("Redis connected")
    except Exception as e:
        logger.error("Redis connection failed: %s", e)

    yield

    if app_state.db_pool:
        await app_state.db_pool.close()
    if app_state.redis_client:
        await app_state.redis_client.close()

app = FastAPI(title="DESC Cloud-Native Backend", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Middleware: metrics ───────────────────────────────────────────────────────
@app.middleware("http")
async def metrics_middleware(request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    endpoint = request.url.path
    REQUEST_COUNT.labels(request.method, endpoint, response.status_code).inc()
    REQUEST_LATENCY.labels(request.method, endpoint).observe(duration)
    return response

# ─── Models ───────────────────────────────────────────────────────────────────
class ItemCreate(BaseModel):
    name: str
    description: Optional[str] = None

class Item(BaseModel):
    id: int
    name: str
    description: Optional[str]
    created_at: str

# ─── Endpoints ────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "service": "desc-backend"}

@app.get("/ready")
async def ready():
    checks = {}

    try:
        async with app_state.db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"

    try:
        await app_state.redis_client.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"

    all_ok = all(v == "ok" for v in checks.values())
    if not all_ok:
        raise HTTPException(status_code=503, detail=checks)
    return {"status": "ready", "checks": checks}

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/api/items")
async def list_items():
    cache_key = "items:all"

    try:
        cached = await app_state.redis_client.get(cache_key)
        if cached:
            CACHE_HITS.inc()
            import json
            return {"items": json.loads(cached), "source": "cache"}
    except Exception:
        pass

    CACHE_MISSES.inc()

    start = time.time()
    try:
        async with app_state.db_pool.acquire() as conn:
            DB_CONNECTIONS.inc()
            rows = await conn.fetch(
                "SELECT id, name, description, created_at::text FROM items ORDER BY id DESC LIMIT 50"
            )
            DB_CONNECTIONS.dec()
        duration = time.time() - start
        DB_QUERY_LATENCY.labels("select", "success").observe(duration)
    except Exception as e:
        duration = time.time() - start
        DB_QUERY_LATENCY.labels("select", "error").observe(duration)
        raise HTTPException(status_code=500, detail=str(e))

    items = [dict(row) for row in rows]

    try:
        import json
        await app_state.redis_client.setex(cache_key, 30, json.dumps(items))
    except Exception:
        pass

    return {"items": items, "source": "database"}

@app.post("/api/items", status_code=201)
async def create_item(item: ItemCreate):
    start = time.time()
    try:
        async with app_state.db_pool.acquire() as conn:
            DB_CONNECTIONS.inc()
            row = await conn.fetchrow(
                "INSERT INTO items (name, description) VALUES ($1, $2) RETURNING id, name, description, created_at::text",
                item.name, item.description
            )
            DB_CONNECTIONS.dec()
        duration = time.time() - start
        DB_QUERY_LATENCY.labels("insert", "success").observe(duration)
    except Exception as e:
        duration = time.time() - start
        DB_QUERY_LATENCY.labels("insert", "error").observe(duration)
        raise HTTPException(status_code=500, detail=str(e))

    try:
        await app_state.redis_client.delete("items:all")
    except Exception:
        pass

    ITEMS_CREATED.inc()
    return dict(row)

@app.get("/api/stress")
async def stress_endpoint(n: int = 5000):
    """CPU-intensive endpoint used by load tests to trigger HPA scaling."""
    def count_primes(limit: int) -> int:
        count = 0
        for num in range(2, limit):
            is_prime = all(num % i != 0 for i in range(2, int(num**0.5) + 1))
            if is_prime:
                count += 1
        return count

    loop = asyncio.get_event_loop()
    prime_count = await loop.run_in_executor(None, count_primes, n)
    return {"primes_found": prime_count, "upper_limit": n}

@app.get("/api/info")
async def info():
    return {
        "app": "DESC Cloud-Native Demo",
        "version": "1.0.0",
        "tender": "DESC-MRD-2026-CNC-088",
        "pod_name": os.getenv("POD_NAME", "unknown"),
        "node_name": os.getenv("NODE_NAME", "unknown"),
    }
