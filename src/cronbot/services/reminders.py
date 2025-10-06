import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import aiosqlite
from ..db import Database

PRESETS = {
    "everyday": {"day_of_week": "*"},
    "weekdays": {"day_of_week": "mon-fri"},
    "weekend": {"day_of_week": "sat,sun"},
    "mon": {"day_of_week": "mon"}, "tue": {"day_of_week": "tue"}, "wed": {"day_of_week": "wed"},
    "thu": {"day_of_week": "thu"}, "fri": {"day_of_week": "fri"}, "sat": {"day_of_week": "sat"}, "sun": {"day_of_week": "sun"},
}

def parse_hhmm(s: str) -> tuple[int,int]:
    if not re.fullmatch(r"\d{2}:\d{2}", s):
        raise ValueError("Формат времени HH:MM")
    h, m = map(int, s.split(":"))
    if not (0 <= h <= 23 and 0 <= m <= 59): raise ValueError("Часы 00–23, минуты 00–59")
    return h, m

class ReminderService:
    def __init__(self, db: Database, tz: str):
        self.db = db
        self.tz = ZoneInfo(tz)

    async def add_cron(self, guild_id:int, channel_id:int, user_id:int, preset:str, time:str, text:str, targetUser:int|None=None) -> int:
        if preset not in PRESETS:
            raise ValueError("Неизвестный preset")
        h, m = parse_hhmm(time)
        db = await self.db.connect()
        try:
            await db.execute(
                "INSERT INTO crons (guild_id, channel_id, user_id, preset, time_h, time_m, tz, text, targetUser, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (guild_id, channel_id, user_id, preset, h, m, self.tz.key, text, targetUser,
                 datetime.utcnow().isoformat())
            )
            await db.commit()
            cur = await db.execute("SELECT last_insert_rowid()")
            rid = (await cur.fetchone())[0]
        finally:
            await db.close()
        return int(rid)

    async def delete_cron(self, guild_id:int, id:int) -> bool:
        db = await self.db.connect()
        try:
            cur = await db.execute("DELETE FROM crons WHERE id = ? AND guild_id = ?", (id, guild_id))
            await db.commit()
            return cur.rowcount > 0
        finally:
            await db.close()

    async def list_crons(self, guild_id:int) -> list[aiosqlite.Row]:
        rows = []
        async for row in self.db.iter_crons(guild_id):
            rows.append(row)
        return rows

    def when_after_minutes(self, minutes:int) -> datetime:
        return datetime.now(self.tz) + timedelta(minutes=minutes)
