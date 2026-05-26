"""
Notification Service tests — asyncpg and redis patched during lifespan.
"""
import sys
import os
import importlib.util

import prometheus_client
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

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


_svc = _load("_notification_svc_main", os.path.join(_SVC_DIR, "main.py"))


class _AsyncCtx:
    def __init__(self, val):
        self._val = val

    async def __aenter__(self):
        return self._val

    async def __aexit__(self, *_):
        pass


def _make_mock_pool(rows=None):
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=rows or [])
    conn.fetchrow = AsyncMock(return_value=None)
    conn.execute = AsyncMock()
    conn.fetchval = AsyncMock(return_value=1)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_AsyncCtx(conn))
    pool.close = AsyncMock()
    return pool, conn


def _make_mock_redis():
    r = MagicMock()
    r.publish = AsyncMock(return_value=1)
    r.ping = AsyncMock(return_value=True)
    r.close = AsyncMock()
    return r


@pytest.fixture
def test_client():
    pool, conn = _make_mock_pool()
    redis = _make_mock_redis()
    with patch("asyncpg.create_pool", new=AsyncMock(return_value=pool)), \
         patch("redis.asyncio.from_url", return_value=redis):
        with TestClient(_svc.app) as client:
            yield client, pool, conn, redis


class TestNotificationEndpoints:
    def test_list_notifications_200(self, test_client):
        client, *_ = test_client
        r = client.get("/notifications")
        assert r.status_code == 200
        assert "notifications" in r.json()

    def test_health_ok(self, test_client):
        client, *_ = test_client
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_ready_with_working_deps(self, test_client):
        client, *_ = test_client
        r = client.get("/ready")
        assert r.status_code == 200

    def test_metrics_endpoint(self, test_client):
        client, *_ = test_client
        r = client.get("/metrics")
        assert r.status_code == 200
        assert "text/plain" in r.headers.get("content-type", "")

    def test_create_notification_201_and_publishes(self, test_client):
        client, _, conn, redis = test_client
        conn.fetchrow = AsyncMock(return_value={
            "id": 1, "title": "Test", "message": "Test msg",
            "type": "info", "created_at": "2026-01-01T00:00:00",
        })
        r = client.post("/notifications", json={
            "title": "Test", "message": "Test message", "type": "info",
        })
        assert r.status_code == 201
        redis.publish.assert_awaited_once()

    def test_create_notification_invalid_type_422(self, test_client):
        client, *_ = test_client
        r = client.post("/notifications", json={
            "title": "Bad", "message": "msg", "type": "not_a_valid_type",
        })
        assert r.status_code == 422
