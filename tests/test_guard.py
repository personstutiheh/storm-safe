from storm_safe.guard import (initial_state, conditions_from_snapshot, check_command, check_sequence, apply, enforce_response)

CALM = {"high_radiation": False, "severe_storm": False}
STORM = {"high_radiation": True, "severe_storm": True}

def rules(state, cond, cmd):
    return [v["rule"] for v in check_command(state, cond, cmd)]

def test_r1_payload_blocked_in_radiation():
    s = apply(initial_state(), {"name": "hibernate_payload"})
    assert rules(s, STORM, {"name": "activate_payload"}) == ["R1"]
    assert rules(s, CALM, {"name": "activate_payload"}) == []

def test_r2_no_orbit_raise_in_safe_mode():
    s = apply(initial_state(), {"name": "enter_safe_mode"})
    assert "R2" in rules(s, CALM, {"name": "raise_orbit", "params": {"delta_km": 1}})

def test_r3_fuel_reserve():
    ok = {"name": "raise_orbit", "params": {"delta_km": 5}}
    too_much = {"name": "raise_orbit", "params": {"delta_km": 25}}
    assert rules(initial_state(), CALM, ok) == []
    assert "R3" in rules(initial_state(), CALM, too_much)

def test_r4_storm_requires_safe_mode_for_reorient():
    cmd = {"name": "reorient_panels", "params": {"angle_deg": 10}}
    assert rules(initial_state(), STORM, cmd) == ["R4"]
    safe = apply(initial_state(), {"name": "enter_safe_mode"})
    assert rules(safe, STORM, cmd) == []

def test_r5_power_floor():
    low = {"mode": "degraded", "payload_on": True, "power": 20, "fuel": 60}
    assert "R5" in rules(low, CALM, {"name": "activate_payload"})

def test_r6_adds_safe_mode_in_severe_storm():
    out = check_sequence(initial_state(), STORM, [{"name": "no_action"}])
    assert [a["command"]["name"] for a in out["guard_added"]] == ["enter_safe_mode"]
    assert out["final_state"]["mode"] == "safe"
    assert out["final_state"]["payload_on"] is False

def test_r6_hibernates_payload_in_radiation_only():
    cond = {"high_radiation": True, "severe_storm": False}
    out = check_sequence(initial_state(), cond, [{"name": "no_action"}])
    assert [a["command"]["name"] for a in out["guard_added"]] == ["hibernate_payload"]
    assert out["final_state"]["payload_on"] is False
    assert out["final_state"]["mode"] == "normal"

def test_r6_adds_nothing_when_calm():
    out = check_sequence(initial_state(), CALM, [{"name": "no_action"}])
    assert out["guard_added"] == []

def test_r6_no_duplicate_when_agent_already_safe():
    out = check_sequence(initial_state(), STORM, [{"name": "enter_safe_mode"}])
    assert out["guard_added"] == []

def test_r6_added_commands_never_violate_other_rules():
    for cond in (STORM, {"high_radiation": True, "severe_storm": False}):
        added, _ = enforce_response(initial_state(), cond)
        s = initial_state()
        for a in added:
            assert check_command(s, cond, a["command"]) == []
            s = apply(s, a["command"])

def test_sequence_blocks_bad_and_keeps_good():
    cmds = [
        {"name": "activate_payload"},
        {"name": "enter_safe_mode"},
        {"name": "reorient_panels", "params": {"angle_deg": 5}},
    ]
    out = check_sequence(initial_state(), STORM, cmds)
    assert [r["accepted"] for r in out["results"]] == [False, True, True]
    assert out["safe"] is False
    assert out["final_state"]["mode"] == "safe"

def test_missing_data_is_treated_as_dangerous():
    c = conditions_from_snapshot({"scales": None, "proton": None, "kp": None})
    assert c["high_radiation"] and c["severe_storm"]

def test_calm_snapshot():
    snap = {"scales": {"G": 0, "S": 0, "R": 0},
            "proton": {"flux_ge10MeV": 0.2}, "kp": {"value": 2.3}}
    assert conditions_from_snapshot(snap) == CALM

def test_g3_snapshot_is_severe():
    snap = {"scales": {"G": 3, "S": 0, "R": 0},
            "proton": {"flux_ge10MeV": 0.2}, "kp": {"value": 7}}
    assert conditions_from_snapshot(snap)["severe_storm"] is True