import aiosqlite, os
from typing import AsyncIterator

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS crons (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  guild_id INTEGER NOT NULL,
  channel_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  preset TEXT NOT NULL,
  time_h INTEGER NOT NULL,
  time_m INTEGER NOT NULL,
  tz TEXT NOT NULL,
  text TEXT NOT NULL,
  targetUser INTEGER,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS phrases (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  guild_id INTEGER NOT NULL,
  text TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS guild_settings (
  guild_id INTEGER PRIMARY KEY,
  default_channel_id INTEGER
);

CREATE TABLE IF NOT EXISTS confronts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  guild_id INTEGER NOT NULL,
  target_user_id INTEGER NOT NULL,
  trigger_reaction TEXT,
  counter_reaction TEXT NOT NULL,
  created_by INTEGER NOT NULL,
  created_at TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    async def connect(self) -> aiosqlite.Connection:
        db = await aiosqlite.connect(self.path)
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA foreign_keys=ON;")
        await db.executescript(CREATE_SQL)
        await db.commit()
        return db

    async def iter_crons(self, guild_id: int | None = None) -> AsyncIterator[aiosqlite.Row]:
        db = await self.connect()
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM crons" + (" WHERE guild_id = ?" if guild_id else "")
        params = (guild_id,) if guild_id else ()
        async with db.execute(query, params) as cur:
            async for row in cur:
                yield row
        await db.close()
