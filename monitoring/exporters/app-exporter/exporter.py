"""
DESC Cloud-Native Demo — Standalone Prometheus Exporter
Exports custom business metrics not covered by the built-in FastAPI /metrics endpoint.

Metrics exported:
  desc_active_sessions_total    — gauge: active user sessions (simulated)
  desc_queue_depth              — gauge: background job queue depth
  desc_db_pool_available        — gauge: available DB connection pool slots
  desc_uptime_seconds           — counter: exporter uptime

Usage:
  python exporter.py
  # Metrics available at: http://localhost:9090/metrics
"""

import os
import time
import random
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from prometheus_client import (
    Gauge, Counter, Histogram,
    generate_latest, CONTENT_TYPE_LATEST,
    CollectorRegistry, REGISTRY
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PORT = int(os.getenv("EXPORTER_PORT", "9090"))
SCRAPE_INTERVAL = int(os.getenv("SCRAPE_INTERVAL", "15"))

# ─── Metric definitions ───────────────────────────────────────────────────────
ACTIVE_SESSIONS = Gauge(
    "desc_active_sessions_total",
    "Current number of active user sessions"
)
QUEUE_DEPTH = Gauge(
    "desc_background_queue_depth",
    "Number of jobs waiting in the background queue",
    ["queue_name"]
)
DB_POOL_AVAILABLE = Gauge(
    "desc_db_pool_available_connections",
    "Available connections in the DB pool"
)
DB_POOL_TOTAL = Gauge(
    "desc_db_pool_total_connections",
    "Total connections in the DB pool"
)
EXPORTER_UPTIME = Counter(
    "desc_exporter_uptime_seconds_total",
    "Total seconds the exporter has been running"
)
LAST_SCRAPE_DURATION = Histogram(
    "desc_exporter_scrape_duration_seconds",
    "Duration of metric collection scrapes",
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1]
)

# ─── Metric collection ────────────────────────────────────────────────────────
def collect_metrics():
    """Simulate collecting metrics from internal app state / external sources."""
    start = time.time()

    # In a real deployment these would come from:
    # - A Redis key storing session count
    # - A Celery queue inspector
    # - A SQLAlchemy pool status call
    ACTIVE_SESSIONS.set(random.randint(50, 500))
    QUEUE_DEPTH.labels(queue_name="email").set(random.randint(0, 20))
    QUEUE_DEPTH.labels(queue_name="reports").set(random.randint(0, 5))
    DB_POOL_AVAILABLE.set(random.randint(2, 8))
    DB_POOL_TOTAL.set(10)

    duration = time.time() - start
    LAST_SCRAPE_DURATION.observe(duration)
    logger.debug("Metrics collected in %.3fs", duration)

def background_collector():
    """Continuously refreshes metrics in the background."""
    while True:
        try:
            collect_metrics()
            EXPORTER_UPTIME.inc(SCRAPE_INTERVAL)
        except Exception as e:
            logger.error("Metric collection error: %s", e)
        time.sleep(SCRAPE_INTERVAL)

# ─── HTTP Handler ─────────────────────────────────────────────────────────────
class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/metrics":
            output = generate_latest(REGISTRY)
            self.send_response(200)
            self.send_header("Content-Type", CONTENT_TYPE_LATEST)
            self.end_headers()
            self.wfile.write(output)
        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        logger.debug("%s - %s", self.address_string(), format % args)

# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("DESC Prometheus Exporter starting on port %d", PORT)

    collector_thread = threading.Thread(target=background_collector, daemon=True)
    collector_thread.start()

    collect_metrics()

    server = HTTPServer(("0.0.0.0", PORT), MetricsHandler)
    logger.info("Serving metrics at http://0.0.0.0:%d/metrics", PORT)
    server.serve_forever()
