"""
API Gateway Service
Routes all /api/* requests to the appropriate downstream microservice.
Exposes aggregated /api/health and /api/info for the frontend status panel.
"""
import os
import time
import asyncio
import logging
from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

USER_SVC       = os.getenv("USER_SERVICE_URL",         "http://user-svc:8001")
RECORDS_SVC    = os.getenv("RECORDS_SERVICE_URL",      "http://records-svc:8002")
NOTIFICATION_SVC = os.getenv("NOTIFICATION_SERVICE_URL", "http://notification-svc:8003")

# ─── Prometheus ───────────────────────────────────────────────────────────────
GW_REQUESTS = Counter(
    "gateway_requests_total",
    "Total requests handled by the gateway",
    ["method", "path", "status"]
)
GW_UPSTREAM_LATENCY = Histogram(
    "gateway_upstream_latency_seconds",
    "Latency of upstream microservice calls from gateway",
    ["service", "endpoint"],
    buckets=[0.005, 0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5]
)

# ─── HTTP client pool ─────────────────────────────────────────────────────────
http_client: httpx.AsyncClient | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client
    http_client = httpx.AsyncClient(timeout=httpx.Timeout(10.0), limits=httpx.Limits(max_connections=100))
    logger.info("Gateway started — routing to: user=%s records=%s notifications=%s",
                USER_SVC, RECORDS_SVC, NOTIFICATION_SVC)
    yield
    await http_client.aclose()

app = FastAPI(title="DESC API Gateway", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ─── Middleware ───────────────────────────────────────────────────────────────
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    response = await call_next(request)
    GW_REQUESTS.labels(request.method, request.url.path, response.status_code).inc()
    return response

# ─── Helpers ─────────────────────────────────────────────────────────────────
async def proxy(method: str, url: str, service: str, **kwargs) -> httpx.Response:
    start = time.time()
    try:
        response = await http_client.request(method, url, **kwargs)
        GW_UPSTREAM_LATENCY.labels(service, url.split(service)[-1] or "/").observe(time.time() - start)
        return response
    except httpx.RequestError as e:
        logger.error("Upstream %s unreachable: %s", service, e)
        raise HTTPException(status_code=503, detail=f"{service} unavailable")

async def check_service(name: str, base_url: str) -> dict:
    try:
        r = await http_client.get(f"{base_url}/health", timeout=3.0)
        return {"service": name, "status": "healthy" if r.status_code == 200 else "degraded", "url": base_url}
    except Exception as e:
        return {"service": name, "status": "unreachable", "error": str(e)}

# ─── Gateway endpoints ────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "service": "gateway"}

@app.get("/ready")
async def ready():
    return {"status": "ready", "service": "gateway"}

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/api/health")
async def aggregate_health():
    """Fan-out health check to all 3 downstream services — used by frontend status panel."""
    results = await asyncio.gather(
        check_service("gateway", f"http://localhost:{os.getenv('PORT', '8000')}"),
        check_service("user-service", USER_SVC),
        check_service("records-service", RECORDS_SVC),
        check_service("notification-service", NOTIFICATION_SVC),
    )
    overall = "healthy" if all(r["status"] == "healthy" for r in results[1:]) else "degraded"
    results[0]["status"] = "healthy"
    return {"overall": overall, "services": results}

@app.get("/api/info")
async def info():
    return {
        "gateway": {
            "pod": os.getenv("POD_NAME", "local"),
            "node": os.getenv("NODE_NAME", "local"),
        },
        "upstreams": {
            "user-service": USER_SVC,
            "records-service": RECORDS_SVC,
            "notification-service": NOTIFICATION_SVC,
        },
        "tender": "DESC-MRD-2026-CNC-088",
    }

# ─── Users proxy ─────────────────────────────────────────────────────────────
@app.get("/api/users")
async def list_users():
    r = await proxy("GET", f"{USER_SVC}/users", "user-service")
    return JSONResponse(r.json(), status_code=r.status_code)

@app.post("/api/users")
async def create_user(request: Request):
    body = await request.json()
    r = await proxy("POST", f"{USER_SVC}/users", "user-service", json=body)
    return JSONResponse(r.json(), status_code=r.status_code)

# ─── Records proxy ────────────────────────────────────────────────────────────
@app.get("/api/records")
async def list_records():
    r = await proxy("GET", f"{RECORDS_SVC}/records", "records-service")
    return JSONResponse(r.json(), status_code=r.status_code)

@app.post("/api/records")
async def create_record(request: Request):
    body = await request.json()
    r = await proxy("POST", f"{RECORDS_SVC}/records", "records-service", json=body)
    return JSONResponse(r.json(), status_code=r.status_code)

@app.get("/api/stress")
async def stress(request: Request):
    """Proxy to records-service /stress — this is the HPA trigger endpoint for load tests."""
    n = request.query_params.get("n", "8000")
    r = await proxy("GET", f"{RECORDS_SVC}/stress?n={n}", "records-service")
    return JSONResponse(r.json(), status_code=r.status_code)

# ─── Notifications proxy ──────────────────────────────────────────────────────
@app.get("/api/notifications")
async def list_notifications():
    r = await proxy("GET", f"{NOTIFICATION_SVC}/notifications", "notification-service")
    return JSONResponse(r.json(), status_code=r.status_code)

@app.post("/api/notifications")
async def create_notification(request: Request):
    body = await request.json()
    r = await proxy("POST", f"{NOTIFICATION_SVC}/notifications", "notification-service", json=body)
    return JSONResponse(r.json(), status_code=r.status_code)
