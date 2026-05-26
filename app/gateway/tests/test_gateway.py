"""
Gateway tests — httpx.AsyncClient is patched during lifespan so no real network calls.
"""
import sys
import os
import importlib.util

import prometheus_client
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

# ── Load this service's main.py under a unique module name ───────────────────
# spec_from_file_location avoids sys.modules['main'] collisions when all
# services are tested in the same pytest process.
_HERE = os.path.dirname(os.path.abspath(__file__))
_SVC_DIR = os.path.dirname(_HERE)


def _load(unique_name: str, path: str):
    if unique_name in sys.modules:
        return sys.modules[unique_name]
    for _c in list(prometheus_client.REGISTRY._collector_to_names):
        try:
            prometheus_client.REGISTRY.unregister(_c)
        except Exception:
            pass
    if _SVC_DIR not in sys.path:
        sys.path.insert(0, _SVC_DIR)
    spec = importlib.util.spec_from_file_location(unique_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[unique_name] = mod
    spec.loader.exec_module(mod)
    return mod


_svc = _load("_gateway_main", os.path.join(_SVC_DIR, "main.py"))


def _mock_response(status_code: int = 200, json_body: dict | None = None):
    m = MagicMock()
    m.status_code = status_code
    m.json.return_value = json_body or {}
    m.text = str(json_body or {})
    m.content = b"{}"
    m.headers = {"content-type": "application/json"}
    return m


@pytest.fixture
def http_mock():
    mock = MagicMock()
    mock.request = AsyncMock(return_value=_mock_response(200, {"status": "ok"}))
    mock.get = AsyncMock(return_value=_mock_response(200, {"status": "ok"}))
    mock.aclose = AsyncMock()
    with patch("httpx.AsyncClient", return_value=mock):
        with TestClient(_svc.app) as client:
            yield client, mock


class TestHealthEndpoint:
    def test_simple_health_returns_200(self, http_mock):
        client, _ = http_mock
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_aggregate_health_returns_keys(self, http_mock):
        client, mock = http_mock
        mock.get = AsyncMock(return_value=_mock_response(200, {"status": "ok"}))
        r = client.get("/api/health")
        assert r.status_code == 200
        assert "overall" in r.json()
        assert "services" in r.json()


class TestProxyRoutes:
    def test_get_users_proxied(self, http_mock):
        client, mock = http_mock
        mock.request = AsyncMock(return_value=_mock_response(200, {"users": []}))
        r = client.get("/api/users")
        assert r.status_code == 200

    def test_get_records_proxied(self, http_mock):
        client, mock = http_mock
        mock.request = AsyncMock(return_value=_mock_response(200, {"records": []}))
        r = client.get("/api/records")
        assert r.status_code == 200

    def test_get_notifications_proxied(self, http_mock):
        client, mock = http_mock
        mock.request = AsyncMock(return_value=_mock_response(200, {"notifications": []}))
        r = client.get("/api/notifications")
        assert r.status_code == 200

    def test_stress_proxied(self, http_mock):
        client, mock = http_mock
        mock.request = AsyncMock(
            return_value=_mock_response(200, {"primes_found": 1229, "upper_limit": 10000})
        )
        r = client.get("/api/stress?n=100")
        assert r.status_code == 200

    def test_info_endpoint(self, http_mock):
        client, _ = http_mock
        r = client.get("/api/info")
        assert r.status_code == 200
        assert "gateway" in r.json()

    def test_metrics_endpoint(self, http_mock):
        client, _ = http_mock
        r = client.get("/metrics")
        assert r.status_code == 200
        assert "text/plain" in r.headers.get("content-type", "")
