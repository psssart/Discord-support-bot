from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import aiosqlite

from ..db import Database

class ConfrontService:
    def __init__(self, db: Database):
        self.db = db

    async def add(self, guild_id: int, target_user_id: int, counter_reaction: str, created_by: int, trigger_reaction: Optional[str] = None) -> int:
        db = await self.db.connect()
        try:
            cur = await db.execute(
                """INSERT INTO confronts (guild_id, target_user_id, trigger_reaction, counter_reaction, created_by, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (guild_id, target_user_id, trigger_reaction, counter_reaction, created_by, datetime.now(timezone.utc).isoformat())
            )
            await db.commit()
            return cur.lastrowid
        finally:
            await db.close()

    async def list(self, guild_id: int) -> List[aiosqlite.Row]:
        db = await self.db.connect()
        db.row_factory = aiosqlite.Row
        try:
            cur = await db.execute(
                "SELECT id, guild_id, target_user_id, trigger_reaction, counter_reaction, created_by, created_at "
                "FROM confronts WHERE guild_id = ? ORDER BY id ASC",
                (guild_id,)
            )
            return await cur.fetchall()
        finally:
            await db.close()

    async def remove(self, guild_id: int, confront_id: int) -> bool:
        db = await self.db.connect()
        try:
            cur = await db.execute("DELETE FROM confronts WHERE guild_id = ? AND id = ?", (guild_id, confront_id))
            await db.commit()
            return cur.rowcount > 0
        finally:
            await db.close()

    async def get_for_guild(self, guild_id: int) -> List[aiosqlite.Row]:
        return await self.list(guild_id)
