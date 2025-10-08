import pytest
from cronbot.db import Database
from cronbot.services.confronts import ConfrontService

pytestmark = pytest.mark.asyncio

@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")

@pytest.fixture
async def svc(db_path):
    return ConfrontService(Database(db_path))

async def test_confront_crud(svc):
    gid = 10
    cid = await svc.add(
        guild_id=gid,
        target_user_id=100,
        counter_reaction="🔥",
        created_by=42,
        trigger_reaction="👍",
    )
    assert isinstance(cid, int) and cid > 0

    rows = await svc.list(gid)
    assert len(rows) == 1
    r = rows[0]
    assert r["id"] == cid
    assert r["target_user_id"] == 100
    assert r["counter_reaction"] == "🔥"
    assert r["trigger_reaction"] == "👍"

    ok = await svc.remove(gid, cid)
    assert ok is True
    assert await svc.list(gid) == []
