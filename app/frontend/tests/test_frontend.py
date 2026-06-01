"""
Frontend (Flask) tests — all gateway requests are mocked.
Auth-guarded routes are tested by injecting session data directly.
"""
import sys
import os
import importlib.util

import pytest
from unittest.mock import MagicMock, patch

_HERE = os.path.dirname(os.path.abspath(__file__))
_SVC_DIR = os.path.dirname(_HERE)

os.environ.setdefault("GATEWAY_URL", "http://gateway:8000")
os.environ.setdefault("SECRET_KEY", "test-secret")


def _load(unique_name: str, path: str):
    if unique_name in sys.modules:
        return sys.modules[unique_name]
    if _SVC_DIR not in sys.path:
        sys.path.insert(0, _SVC_DIR)
    spec = importlib.util.spec_from_file_location(unique_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[unique_name] = mod
    spec.loader.exec_module(mod)
    return mod


_svc = _load("_frontend_app", os.path.join(_SVC_DIR, "app.py"))


def _gw_mock(url, **kwargs):
    path = url.replace("http://gateway:8000", "")
    body = {
        "/api/health":        {"overall": "healthy", "services": [{"service": "gateway", "status": "healthy", "url": "http://gateway:8000"}]},
        "/api/records":       {"records": [], "source": "database"},
        "/api/users":         {"users": [{"id": 1, "name": "Ahmed Khan", "email": "ahmed.khan@desc.gov.pk", "role": "admin", "created_at": "2026-01-01"}]},
        "/api/notifications": {"notifications": []},
    }.get(path, {})
    m = MagicMock()
    m.status_code = 200
    m.json.return_value = body
    m.raise_for_status = MagicMock()
    return m


@pytest.fixture
def client():
    _svc.app.config["TESTING"] = True
    _svc.app.config["WTF_CSRF_ENABLED"] = False
    with _svc.app.test_client() as c:
        yield c


def _login_citizen(client):
    with client.session_transaction() as s:
        s["user_name"]  = "Test Citizen"
        s["user_email"] = "citizen@test.com"
        s["user_role"]  = "citizen"


def _login_admin(client):
    with client.session_transaction() as s:
        s["user_name"]  = "Ahmed Khan"
        s["user_email"] = "ahmed.khan@desc.gov.pk"
        s["user_role"]  = "admin"


class TestPublicRoutes:
    def test_health_endpoint(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.get_json()["status"] == "ok"

    def test_metrics_endpoint(self, client):
        r = client.get("/metrics")
        assert r.status_code == 200

    def test_landing_page_renders(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert b"Citizen Services" in r.data

    def test_landing_redirects_when_logged_in(self, client):
        _login_citizen(client)
        r = client.get("/")
        assert r.status_code == 302
        assert "/portal" in r.headers["Location"]

    def test_login_page_renders(self, client):
        r = client.get("/login")
        assert r.status_code == 200
        assert b"Sign In" in r.data

    def test_register_page_renders(self, client):
        r = client.get("/register")
        assert r.status_code == 200
        assert b"Create Account" in r.data


class TestAuth:
    def test_login_success_citizen(self, client):
        _svc._pw["citizen@test.com"] = _svc._hash("testpass")
        with patch(f"{_svc.__name__}.requests.get", side_effect=lambda url, **kw: _gw_mock(
            url.replace("http://gateway:8000", ""),
            users=[{"id": 99, "name": "Test Citizen", "email": "citizen@test.com", "role": "citizen", "created_at": "2026-01-01"}]
        ) if "/api/users" in url else _gw_mock(url)):
            # Mock returning citizen user
            mock = MagicMock()
            mock.status_code = 200
            mock.json.return_value = {"users": [{"id": 99, "name": "Test Citizen", "email": "citizen@test.com", "role": "citizen", "created_at": "2026-01-01"}]}
            mock.raise_for_status = MagicMock()
            with patch(f"{_svc.__name__}.requests.get", return_value=mock):
                r = client.post("/login", data={"email": "citizen@test.com", "password": "testpass"})
        assert r.status_code == 302
        assert "/portal" in r.headers["Location"]

    def test_login_bad_password(self, client):
        mock = MagicMock()
        mock.status_code = 200
        mock.json.return_value = {"users": [{"id": 1, "name": "Ahmed Khan", "email": "ahmed.khan@desc.gov.pk", "role": "admin", "created_at": "2026-01-01"}]}
        mock.raise_for_status = MagicMock()
        with patch(f"{_svc.__name__}.requests.get", return_value=mock):
            r = client.post("/login", data={"email": "ahmed.khan@desc.gov.pk", "password": "wrong"})
        assert r.status_code == 200
        assert b"Incorrect password" in r.data

    def test_login_unknown_email(self, client):
        mock = MagicMock()
        mock.status_code = 200
        mock.json.return_value = {"users": []}
        mock.raise_for_status = MagicMock()
        with patch(f"{_svc.__name__}.requests.get", return_value=mock):
            r = client.post("/login", data={"email": "nobody@test.com", "password": "desc2026"})
        assert r.status_code == 200
        assert b"No account found" in r.data

    def test_logout_clears_session(self, client):
        _login_citizen(client)
        r = client.get("/logout")
        assert r.status_code == 302
        r2 = client.get("/portal")
        assert r2.status_code == 302
        assert "/login" in r2.headers["Location"]


class TestCitizenPortal:
    def test_portal_requires_login(self, client):
        r = client.get("/portal")
        assert r.status_code == 302
        assert "/login" in r.headers["Location"]

    def test_portal_renders_for_citizen(self, client):
        _login_citizen(client)
        with patch(f"{_svc.__name__}.requests.get", side_effect=_gw_mock):
            r = client.get("/portal")
        assert r.status_code == 200
        assert b"My Records" in r.data
        assert b"Notifications" in r.data

    def test_portal_has_no_technical_info(self, client):
        _login_citizen(client)
        with patch(f"{_svc.__name__}.requests.get", side_effect=_gw_mock):
            r = client.get("/portal")
        assert b"pod_name" not in r.data
        assert b"kubectl" not in r.data
        assert b"k6" not in r.data

    def test_proxy_records_get_requires_login(self, client):
        r = client.get("/api/records")
        assert r.status_code == 302

    def test_proxy_records_get_for_citizen(self, client):
        _login_citizen(client)
        with patch(f"{_svc.__name__}.requests.get", side_effect=_gw_mock):
            r = client.get("/api/records")
        assert r.status_code == 200
        assert "records" in r.get_json()

    def test_proxy_notifications_get_for_citizen(self, client):
        _login_citizen(client)
        with patch(f"{_svc.__name__}.requests.get", side_effect=_gw_mock):
            r = client.get("/api/notifications")
        assert r.status_code == 200
        assert "notifications" in r.get_json()

    def test_citizen_cannot_access_admin(self, client):
        _login_citizen(client)
        with patch(f"{_svc.__name__}.requests.get", side_effect=_gw_mock):
            r = client.get("/admin")
        assert r.status_code == 302
        assert "/portal" in r.headers["Location"]

    def test_citizen_cannot_post_users(self, client):
        _login_citizen(client)
        r = client.post("/api/users", json={"name": "X", "email": "x@x.com", "role": "citizen"},
                        content_type="application/json")
        assert r.status_code == 302  # redirected by require_admin


class TestAdminPanel:
    def test_admin_page_renders(self, client):
        _login_admin(client)
        with patch(f"{_svc.__name__}.requests.get", side_effect=_gw_mock):
            r = client.get("/admin")
        assert r.status_code == 200
        assert b"Admin Panel" in r.data

    def test_admin_page_has_service_health(self, client):
        _login_admin(client)
        with patch(f"{_svc.__name__}.requests.get", side_effect=_gw_mock):
            r = client.get("/admin")
        assert b"gateway" in r.data.lower()

    def test_admin_page_has_stress_section(self, client):
        _login_admin(client)
        with patch(f"{_svc.__name__}.requests.get", side_effect=_gw_mock):
            r = client.get("/admin")
        assert b"Stress" in r.data

    def test_proxy_users_get_for_admin(self, client):
        _login_admin(client)
        with patch(f"{_svc.__name__}.requests.get", side_effect=_gw_mock):
            r = client.get("/api/users")
        assert r.status_code == 200
        assert "users" in r.get_json()

    def test_proxy_stress_admin_only(self, client):
        _login_admin(client)
        _stress_resp = MagicMock(status_code=200, json=lambda: {"primes_found": 25}, raise_for_status=MagicMock())
        with patch(f"{_svc.__name__}.requests.get", return_value=_stress_resp):
            r = client.get("/api/stress?n=100")
        assert r.status_code == 200

    def test_stress_blocked_for_citizen(self, client):
        _login_citizen(client)
        r = client.get("/api/stress?n=100")
        assert r.status_code == 302
