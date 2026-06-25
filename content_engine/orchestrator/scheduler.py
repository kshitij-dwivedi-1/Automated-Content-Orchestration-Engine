"""APScheduler integration for YAML-defined content tasks."""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

import structlog
import yaml
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from content_engine.config.settings import TaskConfig, task_configs_from_yaml_root
from content_engine.constants import LOG_EVENT_SCHEDULER_RELOADED
from content_engine.exceptions import ConfigurationError, SchedulerConfigError
from content_engine.orchestrator.engine import OrchestrationEngine


class TaskScheduler:
    """Schedule task submissions from a hot-reloaded YAML file."""

    def __init__(
        self,
        engine: OrchestrationEngine,
        tasks_file: str,
        scheduler: AsyncIOScheduler | None = None,
        logger: structlog.BoundLogger | None = None,
    ) -> None:
        """Initialize scheduler.

        Args:
            engine: Orchestration engine used to enqueue tasks.
            tasks_file: Path to tasks.yaml.
            scheduler: Optional APScheduler instance.
            logger: Optional structured logger.
        """

        self.engine = engine
        self.tasks_file = Path(tasks_file)
        self.scheduler = scheduler or AsyncIOScheduler()
        self.logger = logger or structlog.get_logger(__name__)
        self._last_mtime: float | None = None

    async def start(self) -> None:
        """Start scheduler and hot-reload watcher.

        Returns:
            None.
        """

        await self.reload()
        self.scheduler.add_job(lambda: asyncio.create_task(self.reload_if_changed()), IntervalTrigger(seconds=10), id="tasks_yaml_hot_reload", replace_existing=True)
        self.scheduler.start()
        self.log_next_runs()

    async def shutdown(self) -> None:
        """Stop the underlying scheduler.

        Returns:
            None.
        """

        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    async def reload_if_changed(self) -> None:
        """Reload tasks when the YAML file modification time changes.

        Returns:
            None.
        """

        if not self.tasks_file.exists():
            return
        mtime = self.tasks_file.stat().st_mtime
        if self._last_mtime is None or mtime != self._last_mtime:
            await self.reload()

    async def reload(self) -> None:
        """Load YAML tasks and schedule them.

        Returns:
            None.
        """

        tasks = await asyncio.to_thread(self.load_tasks)
        for job in list(self.scheduler.get_jobs()):
            if job.id.startswith("content_task_"):
                self.scheduler.remove_job(job.id)
        for index, task in enumerate(tasks):
            self.scheduler.add_job(
                lambda task_config=task: asyncio.create_task(self.engine.submit(task_config)),
                self._parse_trigger(task.schedule_time),
                id=f"content_task_{index}",
                replace_existing=True,
            )
        self._last_mtime = self.tasks_file.stat().st_mtime if self.tasks_file.exists() else None
        self.logger.info(LOG_EVENT_SCHEDULER_RELOADED, task_count=len(tasks))

    def load_tasks(self) -> list[TaskConfig]:
        """Load task configurations from YAML.

        Returns:
            List of task configs.
        """

        if not self.tasks_file.exists():
            return []
        with self.tasks_file.open("r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}
        try:
            return task_configs_from_yaml_root(raw)
        except ConfigurationError as exc:
            raise SchedulerConfigError(str(exc)) from exc

    def log_next_runs(self) -> None:
        """Log the next five scheduled runs.

        Returns:
            None.
        """

        jobs = sorted((job for job in self.scheduler.get_jobs() if job.next_run_time), key=lambda job: job.next_run_time)
        for job in jobs[:5]:
            self.logger.info("scheduled_run", job_id=job.id, next_run_time=job.next_run_time.isoformat())

    @staticmethod
    def _parse_trigger(schedule_time: str) -> CronTrigger | IntervalTrigger | DateTrigger:
        """Parse schedule string into an APScheduler trigger.

        Args:
            schedule_time: Schedule expression.

        Returns:
            APScheduler trigger.
        """

        if schedule_time.startswith("cron:"):
            return CronTrigger(**TaskScheduler._parse_kwargs(schedule_time.removeprefix("cron:")))
        if schedule_time.startswith("interval:"):
            return IntervalTrigger(**TaskScheduler._parse_kwargs(schedule_time.removeprefix("interval:")))
        return DateTrigger(run_date=datetime.fromisoformat(schedule_time))

    @staticmethod
    def _parse_kwargs(text: str) -> dict[str, object]:
        """Parse comma-separated key=value trigger arguments.

        Args:
            text: Trigger argument string.

        Returns:
            Parsed keyword arguments.
        """

        raw_values: dict[str, str] = {}
        current_key: str | None = None
        for part in text.split(","):
            part = part.strip()
            if not part:
                continue
            if "=" in part:
                key, value = part.split("=", 1)
                current_key = key.strip()
                if not current_key:
                    raise SchedulerConfigError("Schedule argument key cannot be empty.")
                raw_values[current_key] = value.strip()
                continue
            if current_key is None:
                raise SchedulerConfigError(f"Invalid schedule argument: {part}")
            raw_values[current_key] = f"{raw_values[current_key]},{part}"
        values: dict[str, object] = {}
        for key, value in raw_values.items():
            values[key] = int(value) if value.isdigit() else value
        return values
