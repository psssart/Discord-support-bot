from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from zoneinfo import ZoneInfo
from typing import Callable

class Scheduler:
    def __init__(self, tz: str):
        self.tz = ZoneInfo(tz)
        self._sch = AsyncIOScheduler(timezone=self.tz)

    def start(self) -> None:
        if not self._sch.running:
            self._sch.start()

    def stop(self) -> None:
        if self._sch.running:
            self._sch.shutdown(wait=False)

    def add_cron(self, job_id: str, send_fn: Callable, *, hour: int, minute: int, expr: dict, payload: dict):
        try:
            self._sch.remove_job(job_id)
        except Exception:
            pass
        trig = CronTrigger(hour=hour, minute=minute, timezone=self.tz, **expr)
        self._sch.add_job(send_fn, trig, id=job_id, kwargs=payload)

    def add_once(self, send_fn: Callable, run_at, payload: dict):
        self._sch.add_job(send_fn, DateTrigger(run_date=run_at), kwargs=payload)

    def remove(self, job_id: str):
        try:
            self._sch.remove_job(job_id)
        except Exception:
            pass
