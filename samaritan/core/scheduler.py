"""
scheduler.py - Async task scheduler for Veritas.

Pure asyncio, no external dependencies.
Persists tasks to SQLite at ~/.veritas/scheduler.db.

Schedule formats:
  "every 5m"       - every 5 minutes
  "every 1h"       - every hour
  "every 30s"      - every 30 seconds
  "daily at 09:00" - daily at 09:00 local time
  "hourly"         - every hour
  "on startup"     - once on startup only

Usage:
  scheduler = TaskScheduler(db_path="~/.veritas/scheduler.db")
  scheduler.register("heartbeat", "every 5m", my_async_fn)
  asyncio.create_task(scheduler.run_loop())
"""

from __future__ import annotations

import asyncio
import logging
import re
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class ScheduledTask:
    name: str
    schedule: str
    fn: Callable
    last_run: float = 0.0
    next_run: float = field(default_factory=time.time)
    enabled: bool = True


class TaskScheduler:
    """
    Async task scheduler backed by SQLite persistence.
    """

    def __init__(self, db_path: str = "~/.veritas/scheduler.db", guardian=None):
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.guardian = guardian
        self._tasks: dict[str, ScheduledTask] = {}
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scheduled_tasks (
                    name       TEXT PRIMARY KEY,
                    schedule   TEXT NOT NULL,
                    last_run   REAL NOT NULL DEFAULT 0,
                    next_run   REAL NOT NULL DEFAULT 0,
                    enabled    INTEGER NOT NULL DEFAULT 1
                )
            """)
            conn.commit()

    def _save_task(self, task: ScheduledTask):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO scheduled_tasks (name, schedule, last_run, next_run, enabled) VALUES (?,?,?,?,?)",
                (task.name, task.schedule, task.last_run, task.next_run, int(task.enabled)),
            )
            conn.commit()

    def _load_task_state(self, name: str) -> Optional[dict]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT last_run, next_run, enabled FROM scheduled_tasks WHERE name=?",
                (name,),
            ).fetchone()
        if row:
            return {"last_run": row[0], "next_run": row[1], "enabled": bool(row[2])}
        return None

    def register(self, name: str, schedule: str, fn: Callable) -> ScheduledTask:
        """Register a task. Restores state from DB if available."""
        task = ScheduledTask(name=name, schedule=schedule, fn=fn)
        saved = self._load_task_state(name)
        if saved:
            task.last_run = saved["last_run"]
            task.next_run = saved["next_run"]
            task.enabled  = saved["enabled"]
        else:
            task.next_run = self._compute_next_run(schedule, 0)
        self._tasks[name] = task
        self._save_task(task)
        logger.info("Scheduler: registered '%s' (%s)", name, schedule)
        return task

    def disable(self, name: str):
        if name in self._tasks:
            self._tasks[name].enabled = False
            self._save_task(self._tasks[name])

    def enable(self, name: str):
        if name in self._tasks:
            self._tasks[name].enabled = True
            self._save_task(self._tasks[name])

    def _parse_interval_seconds(self, schedule: str) -> Optional[float]:
        """Parse 'every Ns/Nm/Nh' → seconds."""
        m = re.match(r"every\s+(\d+\.?\d*)\s*(s|sec|seconds?|m|min|minutes?|h|hr|hours?)", schedule.strip(), re.I)
        if not m:
            if schedule.strip().lower() in ("hourly",):
                return 3600.0
            return None
        val, unit = float(m.group(1)), m.group(2).lower()
        if unit.startswith("s"): return val
        if unit.startswith("m"): return val * 60
        if unit.startswith("h"): return val * 3600
        return None

    def _compute_next_run(self, schedule: str, last_run: float) -> float:
        now = time.time()
        interval = self._parse_interval_seconds(schedule)
        if interval is not None:
            if last_run == 0:
                return now
            return max(now, last_run + interval)

        # "daily at HH:MM"
        m = re.match(r"daily\s+at\s+(\d{1,2}):(\d{2})", schedule.strip(), re.I)
        if m:
            hour, minute = int(m.group(1)), int(m.group(2))
            today = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
            ts = today.timestamp()
            if ts <= now:
                ts += 86400
            return ts

        if schedule.strip().lower() == "on startup":
            return now if last_run == 0 else float("inf")

        return now + 3600  # fallback

    async def run_loop(self):
        """Main scheduler loop. Call with asyncio.create_task(scheduler.run_loop())."""
        logger.info("TaskScheduler: run loop started (%d tasks)", len(self._tasks))
        while True:
            now = time.time()
            for name, task in list(self._tasks.items()):
                if not task.enabled or now < task.next_run:
                    continue
                logger.info("Scheduler: running task '%s'", name)
                try:
                    if asyncio.iscoroutinefunction(task.fn):
                        await task.fn()
                    else:
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(None, task.fn)
                except Exception as e:
                    logger.error("Scheduler task '%s' failed: %s", name, e)
                task.last_run = now
                task.next_run = self._compute_next_run(task.schedule, now)
                self._save_task(task)
            await asyncio.sleep(10)
