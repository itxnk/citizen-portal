import os
import hashlib
import logging
import functools
import requests
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "desc-dev-secret-2026")

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000")
POD_NAME    = os.getenv("POD_NAME", "local")
NODE_NAME   = os.getenv("NODE_NAME", "local")

PAGE_REQUESTS = Counter("frontend_requests_total", "Frontend page requests", ["path", "status"])

_DEFAULT_PW = hashlib.sha256(b"desc2026").hexdigest()
_pw: dict[str, str] = {
    "ahmed.khan@desc.gov.pk":   _DEFAULT_PW,
    "fatima.bibi@desc.gov.pk":  _DEFAULT_PW,
    "tariq@desc.gov.pk":        _DEFAULT_PW,
    "zainab@desc.gov.pk":       _DEFAULT_PW,
    "imran.gul@desc.gov.pk":    _DEFAULT_PW,
}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def gw_get(path: str, timeout: int = 5):
    try:
        r = requests.get(f"{GATEWAY_URL}{path}", timeout=timeout)
        r.raise_for_status()
        return r.json(), None
    except requests.RequestException as e:
        logger.error("Gateway %s failed: %s", path, e)
        return None, str(e)


def require_login(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if "user_email" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def require_admin(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if "user_email" not in session:
            return redirect(url_for("login"))
        if session.get("user_role") not in ("admin", "officer"):
            flash("Access restricted to administrators.", "error")
            return redirect(url_for("portal"))
        return f(*args, **kwargs)
    return wrapper


# ─── Public routes ────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "desc-frontend"})


@app.route("/metrics")
def metrics():
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}


@app.route("/")
def index():
    if "user_email" in session:
        return redirect(url_for("portal"))
    PAGE_REQUESTS.labels("/", "200").inc()
    return render_template("landing.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_email" in session:
        return redirect(url_for("portal"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        pw    = request.form.get("password", "")
        users_data, err = gw_get("/api/users")
        if err or not users_data:
            flash("Service unavailable. Please try again.", "error")
            return render_template("login.html")
        match = next((u for u in users_data.get("users", []) if u["email"].lower() == email), None)
        if not match:
            flash("No account found with that email.", "error")
            return render_template("login.html")
        stored = _pw.get(email, _DEFAULT_PW)
        if _hash(pw) != stored:
            flash("Incorrect password.", "error")
            return render_template("login.html")
        session["user_name"]  = match["name"]
        session["user_email"] = match["email"]
        session["user_role"]  = match["role"]
        PAGE_REQUESTS.labels("/login", "200").inc()
        if match["role"] in ("admin", "officer"):
            return redirect(url_for("admin"))
        return redirect(url_for("portal"))
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_email" in session:
        return redirect(url_for("portal"))
    if request.method == "POST":
        name  = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        pw    = request.form.get("password", "")
        role  = request.form.get("role", "citizen")
        if role not in ("citizen", "officer"):
            role = "citizen"
        if not name or not email or not pw:
            flash("All fields are required.", "error")
            return render_template("register.html")
        try:
            r = requests.post(
                f"{GATEWAY_URL}/api/users",
                json={"name": name, "email": email, "role": role},
                timeout=5,
            )
            if r.status_code not in (200, 201):
                flash(r.json().get("detail", "Registration failed."), "error")
                return render_template("register.html")
            user = r.json()
        except requests.RequestException as e:
            flash(f"Service unavailable: {e}", "error")
            return render_template("register.html")
        _pw[email] = _hash(pw)
        session["user_name"]  = user.get("name", name)
        session["user_email"] = user.get("email", email)
        session["user_role"]  = user.get("role", role)
        flash(f"Welcome, {name}! Your account has been created.", "success")
        PAGE_REQUESTS.labels("/register", "201").inc()
        return redirect(url_for("portal"))
    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ─── Citizen portal ───────────────────────────────────────────────────────────

@app.route("/portal")
@require_login
def portal():
    records_data, _ = gw_get("/api/records")
    notifs_data,  _ = gw_get("/api/notifications")
    PAGE_REQUESTS.labels("/portal", "200").inc()
    return render_template(
        "portal.html",
        records=(records_data or {}).get("records", []),
        notifications=(notifs_data or {}).get("notifications", []),
        user_name=session["user_name"],
        user_email=session["user_email"],
        user_role=session["user_role"],
    )


# ─── Admin panel ─────────────────────────────────────────────────────────────

@app.route("/admin")
@require_admin
def admin():
    health_data, _ = gw_get("/api/health")
    records_data, _ = gw_get("/api/records")
    users_data,   _ = gw_get("/api/users")
    notifs_data,  _ = gw_get("/api/notifications")
    PAGE_REQUESTS.labels("/admin", "200").inc()
    return render_template(
        "admin.html",
        services=(health_data or {}).get("services", []),
        records=(records_data or {}).get("records", []),
        records_source=(records_data or {}).get("source", "unknown"),
        users=(users_data or {}).get("users", []),
        notifications=(notifs_data or {}).get("notifications", []),
        pod_name=POD_NAME,
        node_name=NODE_NAME,
        gateway_url=GATEWAY_URL,
        user_name=session["user_name"],
        user_role=session["user_role"],
    )


# ─── API proxies ──────────────────────────────────────────────────────────────

@app.route("/api/records", methods=["GET", "POST"])
@require_login
def proxy_records():
    if request.method == "POST":
        r = requests.post(f"{GATEWAY_URL}/api/records", json=request.get_json(), timeout=5)
        return jsonify(r.json()), r.status_code
    data, err = gw_get("/api/records")
    return jsonify(data or {"error": err})


@app.route("/api/users", methods=["GET", "POST"])
@require_admin
def proxy_users():
    if request.method == "POST":
        r = requests.post(f"{GATEWAY_URL}/api/users", json=request.get_json(), timeout=5)
        return jsonify(r.json()), r.status_code
    data, err = gw_get("/api/users")
    return jsonify(data or {"error": err})


@app.route("/api/notifications", methods=["GET", "POST"])
@require_login
def proxy_notifications():
    if request.method == "POST":
        if session.get("user_role") not in ("admin", "officer"):
            return jsonify({"error": "Forbidden"}), 403
        r = requests.post(f"{GATEWAY_URL}/api/notifications", json=request.get_json(), timeout=5)
        return jsonify(r.json()), r.status_code
    data, err = gw_get("/api/notifications")
    return jsonify(data or {"error": err})


@app.route("/api/stress")
@require_admin
def proxy_stress():
    n = request.args.get("n", 8000)
    data, err = gw_get(f"/api/stress?n={n}", timeout=30)
    return jsonify(data or {"error": err})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
