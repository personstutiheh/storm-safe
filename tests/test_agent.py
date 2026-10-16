import json
from types import SimpleNamespace
import pytest
from storm_safe.agent import propose, user_prompt, system_prompt

GOOD = json.dumps({"reasoning": "r", "commands": [{"name": "enter_safe_mode"}]})

def fake_client(*replies):
    replies = list(replies)
    def create(**kw):
        text = replies.pop(0)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))

STATE = {"mode": "normal", "payload_on": True, "power": 80, "fuel": 60}

def test_valid_first_try():
    out = propose({}, [], STATE, client=fake_client(GOOD), model="m")
    assert out["proposal"] and out["attempts"] == 1

def test_retry_after_garbage():
    out = propose({}, [], STATE, client=fake_client("sure, safe mode!", GOOD), model="m")
    assert out["proposal"] and out["attempts"] == 2

def test_gives_up_after_retries():
    out = propose({}, [], STATE, client=fake_client("no", "still no"), model="m")
    assert out["proposal"] is None and out["errors"]

def test_strips_think_block():
    out = propose({}, [], STATE, client=fake_client("<think>hmm</think>" + GOOD), model="m")
    assert out["proposal"]

def test_risk_text_in_prompt_and_bad_risk_rejected():
    assert "Prioritise mission output" in user_prompt({}, [], STATE, "high")
    with pytest.raises(ValueError):
        propose({}, [], STATE, risk="reckless", client=fake_client(GOOD))

def test_official_outranks_news_instruction_present():
    assert "outrank news" in system_prompt()