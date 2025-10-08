import pytest
from cronbot.services.reminders import parse_hhmm

@pytest.mark.parametrize("s,expected", [
    ("00:00", (0,0)),
    ("09:05", (9,5)),
    ("23:59", (23,59)),
])
def test_parse_hhmm_ok(s, expected):
    assert parse_hhmm(s) == expected

@pytest.mark.parametrize("s", ["24:00", "12:60", "ab:cd", "9:00", "09-00", "0900", "", " 12:00 "])
def test_parse_hhmm_bad(s):
    with pytest.raises(ValueError):
        parse_hhmm(s)
