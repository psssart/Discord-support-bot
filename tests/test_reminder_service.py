import pytest
from datetime import timedelta
from cronbot.db import Database
from cronbot.services.reminders import ReminderService
from zoneinfo import ZoneInfo

pytestmark = pytest.mark.asyncio

@pytest.fixture
def tz_str():
    return "Europe/Tallinn"

@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")

@pytest.fixture
async def svc(db_path, tz_str):
    db = Database(db_path)
    return ReminderService(db, tz_str)

async def test_when_after_minutes(svc, tz_str):
    t0 = svc.when_after_minutes(1)
    # Check tz and roughly +1 minute
    assert t0.tzinfo == ZoneInfo(tz_str)
    delta = (t0 - t0.astimezone(ZoneInfo(tz_str))).total_seconds()
    assert abs(delta) < 1  # same tz
    assert 55 <= (t0 - svc.when_after_minutes(0)).total_seconds() <= 65  # monotonic-ish

async def test_add_list_delete_cron_roundtrip(svc, db_path, tz_str):
    # add
    cid = await svc.add_cron(
        guild_id=123,
        channel_id=456,
        user_id=789,
        preset="weekdays",
        time="10:15",
        text="Standup time",
        targetUser=None,
    )
    assert isinstance(cid, int) and cid > 0

    # list
    rows = await svc.list_crons(123)
    assert len(rows) == 1
    r = rows[0]
    assert r["id"] == cid
    assert r["preset"] == "weekdays"
    assert r["time_h"] == 10 and r["time_m"] == 15
    assert r["text"] == "Standup time"
    assert r["tz"] == tz_str
    assert r["channel_id"] == 456 and r["user_id"] == 789

    # delete
    deleted = await svc.delete_cron(123, cid)
    assert deleted is True
    rows2 = await svc.list_crons(123)
    assert rows2 == []
