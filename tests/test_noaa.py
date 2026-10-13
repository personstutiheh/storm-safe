from storm_safe.noaa import rows_to_dicts, flare_class, num, last_valid

def test_rows_to_dicts_header_format():
    data = [["time_tag", "speed"], ["t1", "400"], ["t2", None]]
    assert rows_to_dicts(data)[0] == {"time_tag": "t1", "speed": "400"}

def test_last_valid_skips_nulls():
    rows = [{"speed": "400", "time_tag": "t1"}, {"speed": None, "time_tag": "t2"}]
    assert last_valid(rows, "speed") == (400.0, "t1")

def test_flare_class():
    assert flare_class(2e-5).startswith("M")
    assert flare_class(None) is None

def test_num_bad_input():
    assert num("abc") is None