import pytest
from cronbot.db import Database
from cronbot.services.phrases import PhraseService

pytestmark = pytest.mark.asyncio

@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")

@pytest.fixture
async def svc(db_path):
    return PhraseService(Database(db_path))

async def test_add_list_delete_phrase(svc):
    gid = 111
    pid = await svc.add_phrase(gid, "hello world")
    assert isinstance(pid, int) and pid > 0

    rows = await svc.list_phrases(gid)
    assert len(rows) == 1
    assert rows[0]["text"] == "hello world"

    ok = await svc.delete_phrase(gid, pid)
    assert ok is True
    rows2 = await svc.list_phrases(gid)
    assert rows2 == []

async def test_random_phrase(svc):
    gid = 222
    assert await svc.get_random(gid) is None
    await svc.add_phrase(gid, "a")
    await svc.add_phrase(gid, "b")
    await svc.add_phrase(gid, "c")
    val = await svc.get_random(gid)
    assert val in {"a", "b", "c"}

async def test_seed_if_empty(svc):
    gid = 333
    inserted = await svc.seed_if_empty(gid, ["x", "y", "  ", "z"])
    assert inserted == 3
    # second call should be no-op
    again = await svc.seed_if_empty(gid, ["1", "2"])
    assert again == 0
