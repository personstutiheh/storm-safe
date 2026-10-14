from storm_safe.advisories import trim
from storm_safe.advisories import clean
from storm_safe.advisories import rank
from storm_safe.advisories import relevant, strip_boilerplate, trim

def test_trim_caps_text_and_keeps_fields():
    out = trim([{"title": "T", "url": "u", "content": "x" * 900}], max_chars=500)
    assert len(out[0]["snippet"]) == 500
    assert out[0]["title"] == "T"

def test_trim_handles_missing_content():
    assert trim([{"title": "T"}])[0]["snippet"] == ""

def test_clean_keeps_text_after_unclosed_link():
    assert "Forecasters expect" in clean("By: Z [](  Forecasters expect a storm")

def test_rank_puts_official_first_and_rejects_spoofs():
    rs = [
        {"url": "https://blog.example.com/x"},
        {"url": "https://noaa.gov.fake-site.com/y"},
        {"url": "http://www.spaceweather.gov/news/z"},
    ]
    assert rank(rs)[0]["url"].endswith("/news/z")
    assert rank(rs)[-1]["url"].startswith("https://noaa.gov.fake")

def test_relevant_rejects_offtopic_nasa_page():
    assert not relevant({"title": "Hatch Closed on Crew-13", "content": "The Solar System ... Starliner"})
    assert relevant({"title": "G3 geomagnetic storm", "content": ""})

def test_strip_boilerplate():
    assert strip_boilerplate("nav nav published: Sat. SWPC has issued a G3") == "Sat. SWPC has issued a G3"

def test_trim_labels_source_type():
    out = trim([{"url": "https://www.spaceweather.gov/x", "content": "a"},
                {"url": "https://blog.example.com/y", "content": "b"}])
    assert [o["source_type"] for o in out] == ["official", "news"]