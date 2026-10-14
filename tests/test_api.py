from fastapi.testclient import TestClient
from storm_safe import api

client = TestClient(api.app)

def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}

def test_snapshot_is_cached(monkeypatch):
    api._cache.clear()
    calls = []
    monkeypatch.setattr(api, "get_snapshot", lambda: calls.append(1) or {"ok": True})
    client.get("/snapshot")
    client.get("/snapshot")
    assert len(calls) == 1