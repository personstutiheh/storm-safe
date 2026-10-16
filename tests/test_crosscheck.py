import pytest
from storm_safe import crosscheck

def test_extracts_verified_blocks():
    text = crosscheck.MODEL.read_text()
    assert "raise_orbit_big" in crosscheck.extract_block(text, r"mtype\s*=\s*")
    assert "inline apply" in crosscheck.extract_block(text, r"inline\s+apply\s*\(")
    assert "bad = true" in crosscheck.extract_block(text, r"inline\s+violates\s*\(")

def test_program_builds_and_parser_reads_output():
    prog = crosscheck.build_program(crosscheck.make_cases(3, 1))
    assert "active proctype oracle" in prog
    out = "CASE 0\n  STEP 1 enter_safe_mode\n  ADD hibernate_payload\n  END safe 0 85 60\n"
    c = crosscheck.parse(out)[0]
    assert c["accepted"] == [True] and c["added"] == ["hibernate_payload"]
    assert c["end"] == {"mode": "safe", "payload_on": False, "power": 85, "fuel": 60}

@pytest.mark.skipif(not crosscheck.spin_available(), reason="SPIN not available")
def test_python_guard_matches_promela_model():
    rep = crosscheck.run(n=200, seed=1)
    assert rep["mismatches"] == []
    for rule in ("R1", "R2", "R3", "R4", "R5"):
        assert rep["coverage"][rule] > 0

@pytest.mark.skipif(not crosscheck.spin_available(), reason="SPIN not available")
def test_more_than_255_cases_do_not_wrap():
    rep = crosscheck.run(n=300, seed=2)
    assert rep["cases"] == 300 and rep["mismatches"] == []