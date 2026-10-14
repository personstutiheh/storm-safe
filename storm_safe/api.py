import time
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from storm_safe.noaa import get_snapshot
from storm_safe.advisories import get_advisories
from storm_safe.commands import validate_command
from storm_safe.guard import initial_state, conditions_from_snapshot, check_sequence

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

STORM_CONDITIONS = {"high_radiation": True, "severe_storm": True}
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