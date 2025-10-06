import pytest

from cronbot.services.reminders import parse_hhmm, ReminderService, PRESETS
from cronbot.db import Database

def test_parse_hhmm_ok():
    assert parse_hhmm("09:00") == (9, 0)

@pytest.mark.parametrize("bad", ["9:00", "24:00", "10:60", "aa:bb", ""])
def test_parse_hhmm_bad(bad):
    with pytest.raises(ValueError):
        parse_hhmm(bad)

@pytest.mark.asyncio
async def test_service_add_list(tmp_path):
    db = Database(tmp_path / "t.db")
    srv = ReminderService(db, "Europe/Tallinn")
    rid = await srv.add_cron(1, 2, 3, "everyday", "08:15", "ping")
    rows = await srv.list_crons(1)
    assert any(r["id"] == rid for r in rows)
