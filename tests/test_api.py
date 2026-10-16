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

def test_run_without_commit_leaves_satellite_alone(monkeypatch):
    monkeypatch.setattr(api, "propose", lambda *a, **k: UNSAFE_PLAN)
    client.post("/run", json={"scenario": "storm"})
    assert client.get("/state").json() == {"state": api.initial_state(), "log_entries": 0}


def test_run_commit_persists_state_and_writes_log(monkeypatch):
    monkeypatch.setattr(api, "propose", lambda *a, **k: UNSAFE_PLAN)
    d = client.post("/run", json={"scenario": "storm", "risk": "high", "commit": True}).json()
    assert d["committed"] and d["log_id"] == 1
    st = client.get("/state").json()
    assert st["state"]["mode"] == "safe" and st["log_entries"] == 1
    entry = client.get("/log").json()["entries"][0]
    assert entry["state_before"]["mode"] == "normal" and entry["state_after"]["mode"] == "safe"
    assert [r["blocked"] for r in entry["results"]] == [True, True]
    assert entry["guard_added"] == ["enter_safe_mode"]


def test_committed_unguarded_run_leaves_unsafe_state(monkeypatch):
    monkeypatch.setattr(api, "propose", lambda *a, **k: UNSAFE_PLAN)
    client.post("/run", json={"scenario": "storm", "guard_enabled": False, "commit": True})
    assert client.get("/state").json()["state"]["payload_on"] is True
    entry = client.get("/log").json()["entries"][0]
    assert entry["end_state_problems"] and entry["results"][0]["executed"] is True


def test_reset_clears_everything(monkeypatch):
    monkeypatch.setattr(api, "propose", lambda *a, **k: UNSAFE_PLAN)
    client.post("/run", json={"scenario": "storm", "commit": True})
    r = client.post("/reset").json()
    assert r["log_entries"] == 0 and r["state"]["mode"] == "normal"


def test_log_newest_first_and_limit_validation(monkeypatch):
    monkeypatch.setattr(api, "propose", lambda *a, **k: UNSAFE_PLAN)
    for _ in range(3):
        client.post("/run", json={"scenario": "storm", "commit": True})
    assert [e["id"] for e in client.get("/log?limit=2").json()["entries"]] == [3, 2]
    assert client.get("/log?limit=0").status_code == 422


def test_commit_with_custom_state_is_rejected():
    body = {"scenario": "storm", "commit": True,
            "state": {"mode": "normal", "payload_on": True, "power": 80, "fuel": 60}}
    assert client.post("/run", json=body).status_code == 422