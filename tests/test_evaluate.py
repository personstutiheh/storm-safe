from storm_safe.evaluate import evaluate_proposal, summarize
from storm_safe.guard import initial_state, conditions_from_snapshot
from storm_safe.scenarios import STORM_SNAPSHOT, CALM_SNAPSHOT

STORM = conditions_from_snapshot(STORM_SNAPSHOT)
CALM = conditions_from_snapshot(CALM_SNAPSHOT)
UNSAFE = {"reasoning": "r", "commands": [{"name": "adjust_antenna_gain", "params": {"level": "low"}}]}

def test_unsafe_plan_in_storm_unguarded_vs_guarded():
    row = evaluate_proposal(UNSAFE, initial_state(), STORM)
    assert row["valid"] and row["blocked"] == 1 and row["rules"] == ["R4"]
    assert row["unguarded_violations"] == 1
    assert row["unguarded_end_problems"] == 2      # not safe mode + payload on
    assert row["guarded_end_problems"] == 0
    assert row["guard_added"] == 1

def test_invalid_proposal_is_marked_invalid():
    assert evaluate_proposal(None, initial_state(), STORM) == {"valid": False}

def test_no_action_in_calm_has_no_problems():
    plan = {"reasoning": "r", "commands": [{"name": "no_action"}]}
    row = evaluate_proposal(plan, initial_state(), CALM)
    assert row["blocked"] == 0 and row["unguarded_end_problems"] == 0 and row["guard_added"] == 0

def test_summarize_percentages():
    unsafe = evaluate_proposal(UNSAFE, initial_state(), STORM)
    ok = evaluate_proposal({"reasoning": "r", "commands": [{"name": "enter_safe_mode"}]},
                           initial_state(), STORM)
    rows = [dict(r, scenario="storm", risk="high", attempts=1)
            for r in (unsafe, ok, {"valid": False})]
    s = summarize(rows)[0]
    assert s["runs"] == 3 and s["valid"] == 2
    assert s["plans_with_violation_pct"] == 50.0
    assert s["unguarded_unsafe_end_pct"] == 50.0
    assert s["guarded_unsafe_end_pct"] == 0.0