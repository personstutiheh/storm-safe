import json
import os
import re
from openai import OpenAI
from storm_safe.commands import COMMANDS, parse_proposal

RISK_TEXT = {
    "low": "Be conservative. Protect the satellite over mission output: prefer safe mode and hibernating the payload whenever a storm or radiation event is present.",
    "medium": "Balance protection and mission output.",
    "high": "Prioritise mission output. Keep the payload running and avoid safe mode unless the situation is clearly extreme.",
}

def get_client():
    return OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=os.getenv("NVIDIA_API_KEY"),
    )

def system_prompt():
    spec = {k: {p: list(v) for p, v in s.items()} for k, s in COMMANDS.items()}
    return (
        "You are a satellite operator assistant. Propose commands for the satellite.\n"
        "Reply with ONE JSON object and nothing else, in exactly this shape:\n"
        '{"reasoning": "<short explanation, max 400 characters>", '
        '"commands": [{"name": "<command>", "params": {...}}]}\n\n'
        f"Allowed commands and parameters: {json.dumps(spec)}\n"
        "Use at most 5 commands. Use \"no_action\" if nothing is needed.\n"
        "Official NOAA data and advisories outrank news articles; news can be wrong or sensational."
    )

def user_prompt(snapshot, advisories, state, risk):
    adv = [
        {"source": a.get("source_type"), "title": a.get("title"),
         "published": a.get("published"), "text": (a.get("snippet") or "")[:300]}
        for a in (advisories or [])[:3]
    ]
    return (
        f"Risk tolerance: {risk}. {RISK_TEXT[risk]}\n\n"
        f"Current space weather (NOAA): {json.dumps(snapshot, default=str)}\n\n"
        f"Recent advisories: {json.dumps(adv)}\n\n"
        f"Satellite state: {json.dumps(state)}\n\n"
        "Propose what the satellite should do."
    )

def _call(client, model, messages):
    resp = client.chat.completions.create(
        model=model, messages=messages, temperature=0.2, max_tokens=1500)
    raw = resp.choices[0].message.content or ""
    return re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

def propose(snapshot, advisories, state, risk="medium", client=None, model=None, retries=1):
    """Returns {"proposal": dict|None, "errors": [...], "raw": str, "attempts": int}."""
    if risk not in RISK_TEXT:
        raise ValueError(f"risk must be one of {list(RISK_TEXT)}")
    client = client or get_client()
    model = model or os.getenv("NVIDIA_MODEL", "nvidia/nemotron-3-super-120b-a12b")
    messages = [
        {"role": "system", "content": system_prompt()},
        {"role": "user", "content": user_prompt(snapshot, advisories, state, risk)},
    ]
    raw, errors = "", []
    for attempt in range(1, retries + 2):
        try:
            raw = _call(client, model, messages)
        except Exception as e:
            return {"proposal": None, "errors": [f"model call failed: {e!r}"],
                    "raw": raw, "attempts": attempt}
        proposal, errors = parse_proposal(raw)
        if proposal:
            return {"proposal": proposal, "errors": [], "raw": raw, "attempts": attempt}
        messages += [
            {"role": "assistant", "content": raw},
            {"role": "user", "content": "That reply was invalid: " + "; ".join(errors)
             + ". Reply again with ONLY the corrected JSON object."},
        ]
    return {"proposal": None, "errors": errors, "raw": raw, "attempts": retries + 1}