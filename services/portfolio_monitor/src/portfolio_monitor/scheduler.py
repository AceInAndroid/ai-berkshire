from __future__ import annotations

import asyncio
import time
from datetime import datetime, time as wall_time
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from .service import PortfolioMonitorService


class MonitorScheduler:
    def __init__(self, service: PortfolioMonitorService):
        self.service = service
        self.timezone = ZoneInfo(service.config.runtime.timezone)
        self.scheduler = BlockingScheduler(timezone=self.timezone)

    def configure(self) -> None:
        self.scheduler.add_job(self._run_scan, CronTrigger(day_of_week="mon-fri", hour=9, minute=15), id="preopen")
        self.scheduler.add_job(self._run_intraday, "cron", day_of_week="mon-fri", minute="*/5", hour="9-15", id="intraday")
        self.scheduler.add_job(self._run_scan, CronTrigger(day_of_week="mon-fri", hour=15, minute=20), id="close")
        self.scheduler.add_job(self._run_scan, CronTrigger(day_of_week="fri", hour=16, minute=0), id="weekly")
        self.scheduler.add_job(self._retry_pending, "interval", minutes=10, id="retry_pending")

    def start(self) -> None:
        self.configure()
        self.scheduler.start()

    def _run_intraday(self) -> None:
        now = datetime.now(self.timezone).time()
        morning = wall_time(9, 25) <= now <= wall_time(11, 35)
        afternoon = wall_time(12, 55) <= now <= wall_time(15, 10)
        if morning or afternoon:
            self._run_scan()

    def _run_scan(self) -> None:
        started = time.perf_counter()
        run_id = self.service.database.scheduler_start("market_scan")
        try:
            result = asyncio.run(self.service.scan())
            self.service.database.scheduler_finish(
                run_id, "completed", (time.perf_counter() - started) * 1000,
                {"data_as_of": result["data_as_of"], "recommendation_count": len(result["recommendations"])},
            )
        except Exception as error:
            self.service.database.scheduler_finish(
                run_id, "failed", (time.perf_counter() - started) * 1000, {"error": str(error)}
            )
            raise

    def _retry_pending(self) -> None:
        asyncio.run(self.service.alerts.retry_pending())
