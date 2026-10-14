import json
import re

COMMANDS = {
    "no_action": {},
    "enter_safe_mode": {},
    "hibernate_payload": {},
    "activate_payload": {},
    "reorient_panels": {"angle_deg": ("number", -90, 90)},
    "adjust_antenna_gain": {"level": ("choice", ["low", "normal", "high"])},
    "raise_orbit": {"delta_km": ("number", 0.1, 50)},
}

MAX_COMMANDS = 5
MAX_REASONING_CHARS = 600

def validate_command(cmd):
    """Return a list of error strings (empty list = valid)."""
    if not isinstance(cmd, dict):
        return ["command must be an object"]
    name = cmd.get("name")
    if name not in COMMANDS:
        return [f"unknown command: {name!r}"]
    params = cmd.get("params") or {}
    if not isinstance(params, dict):
        return [f"{name}: params must be an object"]

    errors = []
    spec = COMMANDS[name]
    for key in params:
        if key not in spec:
            errors.append(f"{name}: unexpected parameter {key!r}")
    for key, rule in spec.items():
        if key not in params:
            errors.append(f"{name}: missing parameter {key!r}")
            continue
        value = params[key]
        if rule[0] == "number":
            ok = isinstance(value, (int, float)) and not isinstance(value, bool)
            if not ok or not (rule[1] <= value <= rule[2]):
                errors.append(f"{name}: {key} must be a number in [{rule[1]}, {rule[2]}]")
        elif rule[0] == "choice" and value not in rule[1]:
            errors.append(f"{name}: {key} must be one of {rule[1]}")
    return errors

def validate_proposal(obj):
    """A proposal is {"reasoning": str, "commands": [command, ...]}."""
    if not isinstance(obj, dict):
        return ["proposal must be an object"]
    errors = []
    reasoning = obj.get("reasoning")
    if not isinstance(reasoning, str) or not reasoning.strip():
        errors.append("reasoning must be a non-empty string")
    elif len(reasoning) > MAX_REASONING_CHARS:
        errors.append(f"reasoning longer than {MAX_REASONING_CHARS} characters")
    cmds = obj.get("commands")
    if not isinstance(cmds, list) or not cmds:
        errors.append("commands must be a non-empty list")
    elif len(cmds) > MAX_COMMANDS:
        errors.append(f"at most {MAX_COMMANDS} commands allowed")
    else:
        for i, c in enumerate(cmds):
            errors += [f"command {i + 1}: {e}" for e in validate_command(c)]
    return errors

def parse_proposal(text):
    """Pull a JSON object out of model text (handles ```json fences).
    Returns (proposal_or_None, errors)."""
    if not isinstance(text, str):
        return None, ["model output is not text"]
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        return None, ["no JSON object found in model output"]
    try:
        obj = json.loads(cleaned[start:end + 1])
    except json.JSONDecodeError as e:
        return None, [f"invalid JSON: {e}"]
    errors = validate_proposal(obj)
    return (obj if not errors else None), errors