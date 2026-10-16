FUEL_RESERVE = 20
POWER_FLOOR = 15
FUEL_PER_KM = 2
ANTENNA_POWER = {"low": 5, "normal": 0, "high": -10}

def initial_state():
    return {"mode": "normal", "payload_on": True, "power": 80, "fuel": 60}

def conditions_from_snapshot(snap):
    """Reduce a NOAA snapshot to the two flags the rules use.
    Missing data is treated as the dangerous case (fail-safe)."""
    scales = (snap or {}).get("scales") or {}
    proton = ((snap or {}).get("proton") or {}).get("flux_ge10MeV")
    kp = ((snap or {}).get("kp") or {}).get("value")
    g, s = scales.get("G"), scales.get("S")

    radiation_unknown = s is None and proton is None
    storm_unknown = g is None and kp is None
    return {
        "high_radiation": radiation_unknown or (s or 0) >= 2 or (proton or 0) >= 100,
        "severe_storm": storm_unknown or (g or 0) >= 3 or (kp or 0) >= 7,
    }

def apply(state, cmd):
    """Return the new state after a command (does not modify the old one)."""
    s = dict(state)
    name, p = cmd["name"], cmd.get("params") or {}
    if name == "enter_safe_mode":
        s["mode"], s["payload_on"] = "safe", False
        s["power"] += 5
    elif name == "hibernate_payload":
        s["payload_on"] = False
        s["power"] += 10
    elif name == "activate_payload":
        s["payload_on"] = True
        s["power"] -= 15
    elif name == "reorient_panels":
        s["power"] -= 3
    elif name == "adjust_antenna_gain":
        s["power"] += ANTENNA_POWER[p["level"]]
    elif name == "raise_orbit":
        s["fuel"] -= p["delta_km"] * FUEL_PER_KM
        s["power"] -= 5
    s["power"] = round(max(0, min(100, s["power"])), 1)
    s["fuel"] = round(max(0, min(100, s["fuel"])), 1)
    if s["mode"] == "normal" and s["power"] < 40:
        s["mode"] = "degraded"
    return s

def check_command(state, cond, cmd):
    """Return a list of rule violations for one command in this state."""
    name = cmd["name"]
    after = apply(state, cmd)
    v = []
    if name == "activate_payload" and cond["high_radiation"]:
        v.append({"rule": "R1", "message": "Payload cannot be activated during high radiation."})
    if name == "raise_orbit" and state["mode"] == "safe":
        v.append({"rule": "R2", "message": "Orbit raise is not allowed in safe mode."})
    if name == "raise_orbit" and after["fuel"] < FUEL_RESERVE:
        v.append({"rule": "R3", "message": f"Burn would leave fuel below the reserve of {FUEL_RESERVE}."})
    if name in ("reorient_panels", "adjust_antenna_gain") and cond["severe_storm"] and state["mode"] != "safe":
        v.append({"rule": "R4", "message": "During a severe storm this command is only allowed in safe mode."})
    if after["power"] < POWER_FLOOR:
        v.append({"rule": "R5", "message": f"Power would fall below the floor of {POWER_FLOOR}."})
    return v

def enforce_response(state, cond):
    """R6: required response. Returns (commands the guard must add, resulting state)."""
    added, current = [], dict(state)
    if cond["severe_storm"] and current["mode"] != "safe":
        cmd = {"name": "enter_safe_mode"}
        added.append({"command": cmd, "rule": "R6",
                      "message": "Severe storm: satellite must end in safe mode."})
        current = apply(current, cmd)
    if cond["high_radiation"] and current["payload_on"]:
        cmd = {"name": "hibernate_payload"}
        added.append({"command": cmd, "rule": "R6",
                      "message": "High radiation: payload must be off."})
        current = apply(current, cmd)
    return added, current

def check_sequence(state, cond, commands):
    """Check commands in order. Blocked commands are skipped; accepted ones
    change the state that later commands are checked against."""
    results, approved, current = [], [], dict(state)
    for cmd in commands:
        violations = check_command(current, cond, cmd)
        results.append({"command": cmd, "accepted": not violations, "violations": violations})
        if not violations:
            approved.append(cmd)
            current = apply(current, cmd)
    added, final = enforce_response(current, cond)
    return {
        "safe": all(r["accepted"] for r in results),
        "results": results,
        "approved": approved,
        "guard_added": added,
        "executed": approved + [a["command"] for a in added],
        "final_state": final,
    }

def end_state_problems(state, cond):
    """R6 conditions that the final state fails."""
    problems = []
    if cond["severe_storm"] and state["mode"] != "safe":
        problems.append("Severe storm but satellite is not in safe mode (R6).")
    if cond["high_radiation"] and state["payload_on"]:
        problems.append("High radiation but payload is still on (R6).")
    return problems

def run_unguarded(state, cond, commands):
    """No guard: execute everything, record which rules would have been broken."""
    results, current = [], dict(state)
    for cmd in commands:
        violations = check_command(current, cond, cmd)
        current = apply(current, cmd)
        results.append({"command": cmd, "executed": True, "violations": violations})
    return {
        "results": results,
        "violation_count": sum(len(r["violations"]) for r in results),
        "final_state": current,
    }