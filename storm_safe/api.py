import time
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from storm_safe.noaa import get_snapshot
from storm_safe.advisories import get_advisories
from storm_safe.commands import validate_command
from storm_safe.guard import initial_state, conditions_from_snapshot, check_sequence, run_unguarded, end_state_problems
from storm_safe.agent import propose, RISK_TEXT
from storm_safe.scenarios import STORM_SNAPSHOT

app=FastAPI(title="Storm-Safe")
_cache = {}

def cached(key, fn, ttl):
    """
    Reuse a result for `ttl` seconds so we don't hammer NOAA/Tavily
    """
    now=time.time()
    if key in _cache and now - _cache[key][0]<ttl:
        return _cache[key][1]
    value = fn()
    _cache[key] = (now, value)
    return value

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/snapshot")
def snapshot():
    return cached("snapshot", get_snapshot, ttl=60)

@app.get("/advisories")
def advisories():
    return cached("advisories", get_advisories, ttl=600)

STORM_CONDITIONS = conditions_from_snapshot(STORM_SNAPSHOT)
STATE_KEYS = {"mode", "payload_on", "power", "fuel"}

class CheckRequest(BaseModel):
    commands: list[dict]
    scenario: str = "live"
    state: dict | None = None

@app.post("/check")
def check(req: CheckRequest):
    if not req.commands:
        raise HTTPException(422, detail=["commands must not be empty"])
    errors = []
    for i, c in enumerate(req.commands):
        errors += [f"command {i + 1}: {e}" for e in validate_command(c)]
    if errors:
        raise HTTPException(422, detail=errors)

    if req.scenario == "storm":
        cond = STORM_CONDITIONS
    elif req.scenario == "live":
        cond = conditions_from_snapshot(cached("snapshot", get_snapshot, ttl=60))
    else:
        raise HTTPException(422, detail=["scenario must be 'live' or 'storm'"])

    state = req.state or initial_state()
    if not STATE_KEYS <= set(state):
        raise HTTPException(422, detail=[f"state must contain {sorted(STATE_KEYS)}"])

    result = check_sequence(state, cond, req.commands)
    return {"scenario": req.scenario, "conditions": cond, **result}

class RunRequest(BaseModel):
    scenario: str = "live"        # "live" = current NOAA data, "storm" = SIMULATED severe storm
    risk: str = "medium"          # low | medium | high
    guard_enabled: bool = True    # False = run the agent's plan with no guard (comparison)
    state: dict | None = None

@app.post("/run")
def run(req: RunRequest):
    if req.scenario not in ("live", "storm"):
        raise HTTPException(422, detail=["scenario must be 'live' or 'storm'"])
    if req.risk not in RISK_TEXT:
        raise HTTPException(422, detail=[f"risk must be one of {list(RISK_TEXT)}"])
    state = req.state or initial_state()
    if not STATE_KEYS <= set(state):
        raise HTTPException(422, detail=[f"state must contain {sorted(STATE_KEYS)}"])

    if req.scenario == "storm":
        snapshot, advisories = STORM_SNAPSHOT, []
    else:
        snapshot = cached("snapshot", get_snapshot, ttl=60)
        advisories = cached("advisories", get_advisories, ttl=600).get("results", [])
    cond = conditions_from_snapshot(snapshot)

    agent = propose(snapshot, advisories, state, risk=req.risk)
    commands = agent["proposal"]["commands"] if agent["proposal"] else []

    if req.guard_enabled:
        outcome = check_sequence(state, cond, commands)
        final = outcome["final_state"]
    else:
        outcome = run_unguarded(state, cond, commands)
        final = outcome["final_state"]

    return {
        "scenario": req.scenario,
        "simulated": bool(snapshot.get("simulated")),
        "risk": req.risk,
        "guard_enabled": req.guard_enabled,
        "conditions": cond,
        "snapshot": snapshot,
        "agent": {"proposal": agent["proposal"], "errors": agent["errors"],
                  "attempts": agent["attempts"]},
        "outcome": outcome,
        "final_state": final,
        "end_state_problems": end_state_problems(final, cond),
    }