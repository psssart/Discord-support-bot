from dataclasses import dataclass

@dataclass(frozen=True)
class CronEntry:
    id: int
    guild_id: int
    channel_id: int
    user_id: int
    preset: str
    time_h: int
    time_m: int
    tz: str
    text: str

