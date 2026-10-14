from storm_safe.commands import validate_command, validate_proposal, parse_proposal

def test_valid_simple_command():
    assert validate_command({"name": "enter_safe_mode"}) == []

def test_unknown_command_rejected():
    assert validate_command({"name": "fire_lasers"})

def test_param_range_and_type():
    assert validate_command({"name": "raise_orbit", "params": {"delta_km": 5}}) == []
    assert validate_command({"name": "raise_orbit", "params": {"delta_km": 500}})
    assert validate_command({"name": "raise_orbit", "params": {"delta_km": True}})
    assert validate_command({"name": "raise_orbit", "params": {}})

def test_choice_param():
    assert validate_command({"name": "adjust_antenna_gain", "params": {"level": "low"}}) == []
    assert validate_command({"name": "adjust_antenna_gain", "params": {"level": "max"}})

def test_unexpected_param_rejected():
    assert validate_command({"name": "enter_safe_mode", "params": {"x": 1}})

def test_proposal_needs_reasoning_and_commands():
    ok = {"reasoning": "G3 storm, protect payload", "commands": [{"name": "hibernate_payload"}]}
    assert validate_proposal(ok) == []
    assert validate_proposal({"commands": ok["commands"]})
    assert validate_proposal({"reasoning": "x", "commands": []})

def test_parse_handles_code_fence():
    text = '```json\n{"reasoning": "r", "commands": [{"name": "no_action"}]}\n```'
    obj, errors = parse_proposal(text)
    assert errors == [] and obj["commands"][0]["name"] == "no_action"

def test_parse_rejects_garbage():
    assert parse_proposal("I think we should enter safe mode")[0] is None