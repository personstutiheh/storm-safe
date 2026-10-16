import argparse
import json
import time
from collections import Counter, defaultdict
from pathlib import Path

from storm_safe.agent import propose, get_client
from storm_safe.guard import (initial_state, conditions_from_snapshot,
                              check_sequence, run_unguarded, end_state_problems)
from storm_safe.scenarios import STORM_SNAPSHOT, CALM_SNAPSHOT

SCENARIOS = {"storm": STORM_SNAPSHOT, "calm": CALM_SNAPSHOT}


def evaluate_proposal(proposal, state, cond):
    """Judge one proposal (or None if the agent produced no valid one)."""
    if proposal is None:
        return {"valid": False}
    cmds = proposal["commands"]
    raw = run_unguarded(state, cond, cmds)
    guarded = check_sequence(state, cond, cmds)
    blocked = [r for r in guarded["results"] if not r["accepted"]]
    return {
        "valid": True,
        "commands": [c["name"] for c in cmds],
        "n_commands": len(cmds),
        "blocked": len(blocked),
        "rules": [v["rule"] for r in blocked for v in r["violations"]],
        "unguarded_violations": raw["violation_count"],
        "unguarded_end_problems": len(end_state_problems(raw["final_state"], cond)),
        "guarded_end_problems": len(end_state_problems(guarded["final_state"], cond)),
        "guard_added": len(guarded["guard_added"]),
    }


def summarize(rows):
    """rows: list of dicts with 'scenario', 'risk', 'attempts' + evaluate_proposal fields."""
    groups = defaultdict(list)
    for r in rows:
        groups[(r["scenario"], r["risk"])].append(r)
    out = []
    for (scenario, risk), rs in groups.items():
        valid = [r for r in rs if r["valid"]]
        nv = len(valid) or 1
        total_cmds = sum(r["n_commands"] for r in valid) or 1
        out.append({
            "scenario": scenario, "risk": risk,
            "runs": len(rs), "valid": len(valid),
            "retried": sum(1 for r in rs if r.get("attempts", 1) > 1),
            "plans_with_violation_pct": round(100 * sum(1 for r in valid if r["blocked"]) / nv, 1),
            "commands_blocked_pct": round(100 * sum(r["blocked"] for r in valid) / total_cmds, 1),
            "unguarded_unsafe_end_pct": round(100 * sum(1 for r in valid if r["unguarded_end_problems"]) / nv, 1),
            "guarded_unsafe_end_pct": round(100 * sum(1 for r in valid if r["guarded_end_problems"]) / nv, 1),
            "guard_added_pct": round(100 * sum(1 for r in valid if r["guard_added"]) / nv, 1),
            "rules_hit": dict(Counter(x for r in valid for x in r["rules"])),
        })
    return sorted(out, key=lambda s: (s["scenario"], ["low", "medium", "high"].index(s["risk"])))


def print_table(summary):
    head = f'{"scenario":8} {"risk":6} {"valid":>7} {"viol%":>6} {"blk%":>6} {"unguarded":>10} {"guarded":>8} {"added%":>7}'
    print(head)
    for s in summary:
        print(f'{s["scenario"]:8} {s["risk"]:6} {s["valid"]:>3}/{s["runs"]:<3} '
              f'{s["plans_with_violation_pct"]:>6} {s["commands_blocked_pct"]:>6} '
              f'{s["unguarded_unsafe_end_pct"]:>10} {s["guarded_unsafe_end_pct"]:>8} '
              f'{s["guard_added_pct"]:>7}')
    print("\nviol% = plans with at least one blocked command | blk% = commands blocked")
    print("unguarded/guarded = % of valid plans ending in an unsafe state | added% = plans where the guard added commands")


def main():
    from dotenv import load_dotenv
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--risks", nargs="+", default=["low", "medium", "high"])
    ap.add_argument("--scenarios", nargs="+", default=["storm", "calm"])
    ap.add_argument("--sleep", type=float, default=1.0, help="seconds between calls")
    ap.add_argument("--out", default="data/eval_results.json")
    args = ap.parse_args()

    client, rows = get_client(), []
    state = initial_state()
    for scenario in args.scenarios:
        snap = SCENARIOS[scenario]
        cond = conditions_from_snapshot(snap)
        for risk in args.risks:
            for i in range(args.n):
                out = propose(snap, [], state, risk=risk, client=client)
                row = evaluate_proposal(out["proposal"], state, cond)
                row.update(scenario=scenario, risk=risk, attempts=out["attempts"],
                           errors=out["errors"])
                rows.append(row)
                print(f"{scenario}/{risk} {i + 1}/{args.n}: "
                      f"{'ok' if row['valid'] else 'INVALID ' + str(out['errors'])[:80]}")
                time.sleep(args.sleep)

    summary = summarize(rows)
    print()
    print_table(summary)
    Path(args.out).parent.mkdir(exist_ok=True)
    Path(args.out).write_text(json.dumps({"n": args.n, "summary": summary, "runs": rows}, indent=2))
    print(f"\nsaved {args.out}")


if __name__ == "__main__":
    main()