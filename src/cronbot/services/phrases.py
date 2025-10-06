from datetime import datetime
import aiosqlite
from ..db import Database
import random

class PhraseService:
    def __init__(self, db: Database):
        self.db = db

    async def add_phrase(self, guild_id: int, text: str) -> int:
        db = await self.db.connect()
        try:
            await db.execute(
                "INSERT INTO phrases (guild_id, text, created_at) VALUES (?, ?, ?)",
                (guild_id, text, datetime.utcnow().isoformat())
            )
            await db.commit()
            cur = await db.execute("SELECT last_insert_rowid()")
            rid = (await cur.fetchone())[0]
            return int(rid)
        finally:
            await db.close()

    async def list_phrases(self, guild_id: int) -> list[aiosqlite.Row]:
        db = await self.db.connect()
        try:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT id, text FROM phrases WHERE guild_id = ? ORDER BY id", (guild_id,))
            return await cur.fetchall()
        finally:
            await db.close()

    async def delete_phrase(self, guild_id: int, pid: int) -> bool:
        db = await self.db.connect()
        try:
            cur = await db.execute("DELETE FROM phrases WHERE id = ? AND guild_id = ?", (pid, guild_id))
            await db.commit()
            return cur.rowcount > 0
        finally:
            await db.close()

    async def get_random(self, guild_id: int) -> str | None:
        db = await self.db.connect()
        try:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT text FROM phrases WHERE guild_id = ?", (guild_id,))
            rows = await cur.fetchall()
            if not rows:
                return None
            import random
            return random.choice(rows)["text"]
        finally:
            await db.close()

    async def seed_if_empty(self, guild_id: int, phrases: list[str]) -> int:
        """Вернёт сколько вставили."""
        db = await self.db.connect()
        try:
            cur = await db.execute("SELECT COUNT(*) FROM phrases WHERE guild_id = ?", (guild_id,))
            (count,) = await cur.fetchone()
            if count:
                return 0
            now = datetime.utcnow().isoformat()
            await db.executemany(
                "INSERT INTO phrases (guild_id, text, created_at) VALUES (?, ?, ?)",
                [(guild_id, p, now) for p in phrases if p.strip()]
            )
            await db.commit()
            return len([p for p in phrases if p.strip()])
        finally:
            await db.close()
