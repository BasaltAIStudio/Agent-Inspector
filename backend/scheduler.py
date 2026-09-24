"""
Background monitoring scheduler for AgentInspector.
Runs periodic Monitor checks and TrendTracker updates for all active agents.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from backend.database import SessionLocal, Agent, SchedulerRun
from backend.monitoring import Monitor, TrendTracker

logger = logging.getLogger("agentinspector.scheduler")


class MonitoringScheduler:
    def __init__(self, interval_seconds: Optional[int] = None):
        self.interval_seconds = interval_seconds or int(os.getenv("SCHEDULER_INTERVAL_SECONDS", "300"))
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def _record_run(self, db: Session, job_type: str, status: str, error: Optional[str] = None) -> None:
        run = SchedulerRun(
            job_type=job_type,
            last_run_at=datetime.now(timezone.utc),
            status=status,
            error=error,
        )
        db.add(run)
        db.commit()

    async def _run_monitor_checks(self) -> None:
        db = SessionLocal()
        try:
            agents = db.query(Agent).all()
            for agent in agents:
                try:
                    monitor = Monitor(db)
                    monitor.run_checks(agent.id)
                    logger.info("Monitor checks completed for agent %s", agent.id)
                except Exception as e:
                    logger.error("Monitor checks failed for agent %s: %s", agent.id, e)
            await self._record_run(db, "monitor_checks", "success")
        except Exception as e:
            await self._record_run(db, "monitor_checks", "failed", str(e))
            logger.error("Monitor checks batch failed: %s", e)
        finally:
            db.close()

    async def _run_trend_tracker(self) -> None:
        db = SessionLocal()
        try:
            agents = db.query(Agent).all()
            for agent in agents:
                try:
                    tracker = TrendTracker(db)
                    tracker.daily_scores(agent.id)
                    tracker.category_trends(agent.id)
                    logger.info("TrendTracker updates completed for agent %s", agent.id)
                except Exception as e:
                    logger.error("TrendTracker update failed for agent %s: %s", agent.id, e)
            await self._record_run(db, "trend_tracker", "success")
        except Exception as e:
            await self._record_run(db, "trend_tracker", "failed", str(e))
            logger.error("TrendTracker batch failed: %s", e)
        finally:
            db.close()

    async def _run_all(self) -> None:
        await self._run_monitor_checks()
        await self._run_trend_tracker()

    async def _loop(self) -> None:
        while self._running:
            await self._run_all()
            await asyncio.sleep(self.interval_seconds)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("Scheduler started with interval %ds", self.interval_seconds)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Scheduler stopped")

    async def run_once(self) -> None:
        await self._run_all()


scheduler = MonitoringScheduler()
