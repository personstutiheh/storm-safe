from storm_safe.guard import (initial_state, conditions_from_snapshot,
                              check_command, check_sequence, apply)

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