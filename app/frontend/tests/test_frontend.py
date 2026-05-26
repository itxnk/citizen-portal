"""
Frontend (Flask) tests — all gateway requests are mocked.
The Flask file is named app.py; we load it via importlib to avoid the
outer 'app/' directory being imported as a package instead.
"""
import sys
import os
import importlib.util

import pytest
from unittest.mock import MagicMock, patch

_HERE = os.path.dirname(os.path.abspath(__file__))
_SVC_DIR = os.path.dirname(_HERE)

os.environ.setdefault("GATEWAY_URL", "http://gateway:8000")


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
        "/api/health":        {"overall": "healthy", "services": []},
        "/api/records":       {"records": [], "source": "database"},
        "/api/users":         {"users": []},
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
    with _svc.app.test_client() as c:
        yield c


class TestFrontendRoutes:
    def test_health_endpoint(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.get_json()["status"] == "ok"

    def test_metrics_endpoint(self, client):
        r = client.get("/metrics")
        assert r.status_code == 200

    def test_index_renders_200(self, client):
        with patch(f"{_svc.__name__}.requests.get", side_effect=_gw_mock):
            r = client.get("/")
        assert r.status_code == 200

    def test_proxy_records_get(self, client):
        with patch(f"{_svc.__name__}.requests.get", side_effect=_gw_mock):
            r = client.get("/api/records")
        assert r.status_code == 200
        assert "records" in r.get_json()

    def test_proxy_users_get(self, client):
        with patch(f"{_svc.__name__}.requests.get", side_effect=_gw_mock):
            r = client.get("/api/users")
        assert r.status_code == 200
        assert "users" in r.get_json()

    def test_proxy_notifications_get(self, client):
        with patch(f"{_svc.__name__}.requests.get", side_effect=_gw_mock):
            r = client.get("/api/notifications")
        assert r.status_code == 200
        assert "notifications" in r.get_json()

    def test_proxy_stress_get(self, client):
        _stress_resp = MagicMock(
            status_code=200,
            json=lambda: {"primes_found": 25, "upper_limit": 100},
            raise_for_status=MagicMock(),
        )
        with patch(f"{_svc.__name__}.requests.get", return_value=_stress_resp):
            r = client.get("/api/stress?n=100")
        assert r.status_code == 200
