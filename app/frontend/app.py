import os
import logging
import requests
from flask import Flask, render_template, request, jsonify
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000")

PAGE_REQUESTS = Counter("frontend_requests_total", "Frontend page requests", ["path", "status"])

def gw_get(path: str, timeout: int = 5):
    try:
        r = requests.get(f"{GATEWAY_URL}{path}", timeout=timeout)
        r.raise_for_status()
        return r.json(), None
    except requests.RequestException as e:
        logger.error("Gateway %s failed: %s", path, e)
        return None, str(e)

@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "desc-frontend"})

@app.route("/metrics")
def metrics():
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}

@app.route("/")
def index():
    health_data, health_err = gw_get("/api/health")
    records_data, _         = gw_get("/api/records")
    users_data, _           = gw_get("/api/users")
    notifs_data, _          = gw_get("/api/notifications")

    services = health_data.get("services", []) if health_data else []
    PAGE_REQUESTS.labels("/", "200").inc()

    return render_template(
        "index.html",
        services=services,
        records=(records_data or {}).get("records", []),
        records_source=(records_data or {}).get("source", "error"),
        users=(users_data or {}).get("users", []),
        notifications=(notifs_data or {}).get("notifications", []),
        pod_name=os.getenv("POD_NAME", "local"),
        node_name=os.getenv("NODE_NAME", "local"),
        gateway_url=GATEWAY_URL,
        health_err=health_err,
    )

@app.route("/api/records", methods=["GET", "POST"])
def proxy_records():
    if request.method == "POST":
        r = requests.post(f"{GATEWAY_URL}/api/records", json=request.get_json(), timeout=5)
        return jsonify(r.json()), r.status_code
    data, err = gw_get("/api/records")
    return jsonify(data or {"error": err})

@app.route("/api/users", methods=["GET", "POST"])
def proxy_users():
    if request.method == "POST":
        r = requests.post(f"{GATEWAY_URL}/api/users", json=request.get_json(), timeout=5)
        return jsonify(r.json()), r.status_code
    data, err = gw_get("/api/users")
    return jsonify(data or {"error": err})

@app.route("/api/notifications", methods=["GET", "POST"])
def proxy_notifications():
    if request.method == "POST":
        r = requests.post(f"{GATEWAY_URL}/api/notifications", json=request.get_json(), timeout=5)
        return jsonify(r.json()), r.status_code
    data, err = gw_get("/api/notifications")
    return jsonify(data or {"error": err})

@app.route("/api/stress")
def proxy_stress():
    n = request.args.get("n", 8000)
    data, err = gw_get(f"/api/stress?n={n}", timeout=30)
    return jsonify(data or {"error": err})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
