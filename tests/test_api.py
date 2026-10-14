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

def test_check_blocks_unsafe_command_in_storm():
    body = {"scenario": "storm", "commands": [
        {"name": "activate_payload"},
        {"name": "enter_safe_mode"},
    ]}
    r = client.post("/check", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["safe"] is False
    assert [x["accepted"] for x in data["results"]] == [False, True]
    assert data["results"][0]["violations"][0]["rule"] == "R1"

def test_check_rejects_invalid_command():
    r = client.post("/check", json={"commands": [{"name": "fire_lasers"}]})
    assert r.status_code == 422

def test_check_rejects_unknown_scenario():
    r = client.post("/check", json={"scenario": "nope", "commands": [{"name": "no_action"}]})
    assert r.status_code == 422