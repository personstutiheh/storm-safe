import time
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from storm_safe.noaa import get_snapshot
from storm_safe.advisories import get_advisories
from storm_safe.commands import validate_command
from storm_safe.guard import initial_state, conditions_from_snapshot, check_sequence, run_unguarded, end_state_problems
from storm_safe.agent import propose, RISK_TEXT
from storm_safe.scenarios import STORM_SNAPSHOT
from storm_safe.store import Store

app=FastAPI(title="Storm-Safe")
store = Store()
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
    state: dict | None = None     # custom starting state (cannot be combined with commit)
    commit: bool = False          # True = update the persistent satellite and write the log

def _log_entry(req, snapshot, cond, agent, outcome, state_before, final, problems):
    proposal = agent["proposal"]
    results = []
    for r in outcome["results"]:
        executed = r.get("accepted", True)   # unguarded results have no "accepted" key
        results.append({
            "command": r["command"]["name"],
            "executed": executed,
            "blocked": req.guard_enabled and not executed,
            "rules": [v["rule"] for v in r["violations"]],
        })
    return {
        "scenario": req.scenario,
        "simulated": bool(snapshot.get("simulated")),
        "risk": req.risk,
        "guard_enabled": req.guard_enabled,
        "conditions": cond,
        "reasoning": proposal["reasoning"] if proposal else None,
        "agent_errors": agent["errors"],
        "results": results,
        "guard_added": [a["command"]["name"] for a in outcome.get("guard_added", [])],
        "state_before": state_before,
        "state_after": final,
        "end_state_problems": problems,
    }

@app.post("/run")
def run(req: RunRequest):
    if req.scenario not in ("live", "storm"):
        raise HTTPException(422, detail=["scenario must be 'live' or 'storm'"])
    if req.risk not in RISK_TEXT:
        raise HTTPException(422, detail=[f"risk must be one of {list(RISK_TEXT)}"])
    if req.commit and req.state is not None:
        raise HTTPException(422, detail=["commit=true cannot be combined with a custom state"])
    state = req.state or store.get_state()
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
    else:
        outcome = run_unguarded(state, cond, commands)
    final = outcome["final_state"]
    problems = end_state_problems(final, cond)

    log_id = None
    if req.commit:
        entry = store.append(
            _log_entry(req, snapshot, cond, agent, outcome, state, final, problems),
            new_state=final)
        log_id = entry["id"]

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
        "state_before": state,
        "final_state": final,
        "end_state_problems": problems,
        "committed": req.commit,
        "log_id": log_id,
    }


@app.get("/state")
def get_state():
    return {"state": store.get_state(), "log_entries": store.count()}


@app.get("/log")
def get_log(limit: int = Query(50, ge=1, le=200)):
    return {"entries": store.get_log(limit)}


@app.post("/reset")
def reset():
    store.reset()
    return {"state": store.get_state(), "log_entries": 0}