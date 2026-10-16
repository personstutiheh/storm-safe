from dotenv import load_dotenv
from storm_safe.agent import propose
from storm_safe.guard import initial_state, conditions_from_snapshot, check_sequence

load_dotenv()

# SIMULATED severe storm (not live NOAA data)
STORM = {
    "scales": {"G": 3, "S": 2, "R": 1},
    "kp": {"value": 7}, "dst": {"value": -120},
    "solar_wind_speed": {"km_s": 620}, "bz": {"nT": -12},
    "proton": {"flux_ge10MeV": 150},
}

state = initial_state()
cond = conditions_from_snapshot(STORM)
print("conditions:", cond)

for risk in ("low", "medium", "high"):
    out = propose(STORM, [], state, risk=risk)
    print(f"\n=== risk: {risk} (attempts: {out['attempts']}) ===")
    if not out["proposal"]:
        print("no valid proposal:", out["errors"])
        continue
    print("reasoning:", out["proposal"]["reasoning"])
    verdict = check_sequence(state, cond, out["proposal"]["commands"])
    for r in verdict["results"]:
        why = "; ".join(v["rule"] for v in r["violations"])
        print(" ", "ACCEPTED" if r["accepted"] else "BLOCKED ", r["command"]["name"], why)