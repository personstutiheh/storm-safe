from storm_safe.store import Store, MAX_LOG

def test_append_updates_state_and_orders_newest_first():
    s = Store()
    s.append({"x": 1})
    s.append({"x": 2}, new_state={"mode": "safe", "payload_on": False, "power": 90, "fuel": 60})
    assert s.get_state()["mode"] == "safe"
    assert [e["x"] for e in s.get_log()] == [2, 1]
    assert s.get_log(1)[0]["id"] == 2

def test_log_is_capped_and_ids_keep_increasing():
    s = Store()
    for i in range(MAX_LOG + 5):
        s.append({"i": i})
    assert s.count() == MAX_LOG
    assert s.get_log(1)[0]["id"] == MAX_LOG + 5

def test_reset_restores_initial_state_and_clears_log():
    s = Store()
    s.append({"x": 1}, new_state={"mode": "safe", "payload_on": False, "power": 5, "fuel": 1})
    s.reset()
    assert s.count() == 0 and s.get_state()["power"] == 80

def test_get_state_returns_a_copy():
    s = Store()
    s.get_state()["power"] = 0
    assert s.get_state()["power"] == 80