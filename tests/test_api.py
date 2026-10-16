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

UNSAFE_PLAN = {"proposal": {"reasoning": "r", "commands": [
    {"name": "activate_payload"},
    {"name": "reorient_panels", "params": {"angle_deg": 5}},
]}, "errors": [], "raw": "", "attempts": 1}


def test_run_guarded_ends_safe(monkeypatch):
    monkeypatch.setattr(api, "propose", lambda *a, **k: UNSAFE_PLAN)
    r = client.post("/run", json={"scenario": "storm", "risk": "high"})
    d = r.json()
    assert r.status_code == 200 and d["simulated"] is True
    assert d["final_state"]["mode"] == "safe" and d["final_state"]["payload_on"] is False
    assert d["end_state_problems"] == []
    assert [x["accepted"] for x in d["outcome"]["results"]] == [False, False]

def test_run_unguarded_ends_unsafe(monkeypatch):
    monkeypatch.setattr(api, "propose", lambda *a, **k: UNSAFE_PLAN)
    d = client.post("/run", json={"scenario": "storm", "guard_enabled": False}).json()
    assert d["outcome"]["violation_count"] >= 2
    assert d["final_state"]["payload_on"] is True
    assert d["end_state_problems"]

def test_run_agent_failure_guard_still_enforces_safe_state(monkeypatch):
    fail = {"proposal": None, "errors": ["model call failed"], "raw": "", "attempts": 2}
    monkeypatch.setattr(api, "propose", lambda *a, **k: fail)
    d = client.post("/run", json={"scenario": "storm"}).json()
    assert d["final_state"]["mode"] == "safe"
    assert d["agent"]["proposal"] is None

def test_run_rejects_bad_risk_and_scenario():
    assert client.post("/run", json={"risk": "reckless"}).status_code == 422
    assert client.post("/run", json={"scenario": "nope"}).status_code == 422