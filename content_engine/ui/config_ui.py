"""Interactive CLI/YAML configuration editor."""

from __future__ import annotations

import asyncio
from pathlib import Path

import questionary
import yaml
from rich.console import Console
from rich.table import Table

from content_engine.config.settings import TaskConfig, task_configs_from_yaml_root, task_config_to_mapping
from content_engine.constants import MSG_NO_TASKS, MSG_TASK_ADDED
from content_engine.monitoring.metrics import MetricsCollector
from content_engine.storage.task_store import TaskStore


class ConfigUI:
    """Questionary and Rich powered configuration UI."""

    def __init__(
        self,
        tasks_file: str,
        task_store: TaskStore | None = None,
        metrics: MetricsCollector | None = None,
        console: Console | None = None,
    ) -> None:
        """Initialize the config UI.

        Args:
            tasks_file: YAML tasks file path.
            task_store: Optional task history store.
            metrics: Optional metrics collector.
            console: Optional Rich console.
        """

        self.tasks_file = Path(tasks_file)
        self.task_store = task_store
        self.metrics = metrics
        self.console = console or Console()

    async def run(self) -> None:
        """Launch the interactive menu.

        Returns:
            None.
        """

        actions = {
            "Add new content task": self.add_new_content_task,
            "View scheduled tasks": self.view_scheduled_tasks,
            "View task history": self.view_task_history,
            "Edit tasks.yaml visually": self.edit_tasks_yaml,
            "View live metrics summary": self.view_metrics_summary,
            "Exit": None,
        }
        while True:
            choice = questionary.select("Choose an action", choices=list(actions)).ask()
            if choice in (None, "Exit"):
                return
            handler = actions[choice]
            if handler:
                await handler()

    async def add_new_content_task(self) -> None:
        """Prompt for a new task and write it to tasks.yaml.

        Returns:
            None.
        """

        task = TaskConfig(
            topic=questionary.text("Topic").ask() or "",
            keywords=_split_csv(questionary.text("Keywords, comma separated").ask() or ""),
            platforms=questionary.checkbox("Platforms", choices=["wordpress", "twitter", "linkedin"]).ask() or [],
            tone=questionary.text("Tone", default="professional").ask() or "professional",
            word_count=int(questionary.text("Word count", default="800").ask() or "800"),
            schedule_time=questionary.text("Schedule", default="interval:hours=24").ask() or "interval:hours=24",
        )
        tasks = await self._load_tasks()
        tasks.append(task)
        await self._write_tasks(tasks)
        self.console.print(MSG_TASK_ADDED)

    async def view_scheduled_tasks(self) -> None:
        """Render scheduled YAML tasks.

        Returns:
            None.
        """

        tasks = await self._load_tasks()
        if not tasks:
            self.console.print(MSG_NO_TASKS)
            return
        table = Table(title="Scheduled Tasks")
        table.add_column("Topic")
        table.add_column("Keywords")
        table.add_column("Platforms")
        table.add_column("Schedule")
        for task in tasks:
            table.add_row(task.topic, ", ".join(task.keywords), ", ".join(task.platforms), task.schedule_time)
        self.console.print(table)

    async def view_task_history(self) -> None:
        """Render last 20 persisted task runs.

        Returns:
            None.
        """

        if not self.task_store:
            self.console.print("Task history is unavailable without a task store.")
            return
        rows = await self.task_store.list_tasks(limit=20)
        table = Table(title="Task History")
        table.add_column("ID")
        table.add_column("Topic")
        table.add_column("Status")
        table.add_column("SEO")
        table.add_column("Completed")
        for row in rows:
            table.add_row(str(row["id"]), row["topic"], row["status"], str(row.get("seo_score") or ""), str(row.get("completed_at") or ""))
        self.console.print(table)

    async def edit_tasks_yaml(self) -> None:
        """Prompt for replacing an existing scheduled task.

        Returns:
            None.
        """

        tasks = await self._load_tasks()
        if not tasks:
            self.console.print(MSG_NO_TASKS)
            return
        choices = [f"{index + 1}. {task.topic}" for index, task in enumerate(tasks)]
        selected = questionary.select("Task to edit", choices=choices).ask()
        if not selected:
            return
        index = int(selected.split(".", 1)[0]) - 1
        current = tasks[index]
        tasks[index] = TaskConfig(
            topic=questionary.text("Topic", default=current.topic).ask() or current.topic,
            keywords=_split_csv(questionary.text("Keywords", default=", ".join(current.keywords)).ask() or ""),
            platforms=questionary.checkbox("Platforms", choices=["wordpress", "twitter", "linkedin"], default=current.platforms).ask() or current.platforms,
            tone=questionary.text("Tone", default=current.tone).ask() or current.tone,
            word_count=int(questionary.text("Word count", default=str(current.word_count)).ask() or current.word_count),
            schedule_time=questionary.text("Schedule", default=current.schedule_time).ask() or current.schedule_time,
        )
        await self._write_tasks(tasks)
        self.console.print("Task updated.")

    async def view_metrics_summary(self) -> None:
        """Render current in-memory metrics.

        Returns:
            None.
        """

        if not self.metrics:
            self.console.print("Metrics are unavailable in this command context.")
            return
        self.console.print_json(data=self.metrics.get_summary())

    async def _load_tasks(self) -> list[TaskConfig]:
        """Load YAML task definitions.

        Returns:
            List of task configs.
        """

        return await asyncio.to_thread(self._load_tasks_sync)

    def _load_tasks_sync(self) -> list[TaskConfig]:
        """Synchronously load YAML task definitions.

        Returns:
            List of task configs.
        """

        if not self.tasks_file.exists():
            return []
        with self.tasks_file.open("r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}
        return task_configs_from_yaml_root(raw)

    async def _write_tasks(self, tasks: list[TaskConfig]) -> None:
        """Write YAML task definitions.

        Args:
            tasks: Tasks to write.

        Returns:
            None.
        """

        await asyncio.to_thread(self._write_tasks_sync, tasks)

    def _write_tasks_sync(self, tasks: list[TaskConfig]) -> None:
        """Synchronously write YAML task definitions.

        Args:
            tasks: Tasks to write.

        Returns:
            None.
        """

        self.tasks_file.parent.mkdir(parents=True, exist_ok=True)
        with self.tasks_file.open("w", encoding="utf-8") as handle:
            yaml.safe_dump({"tasks": [task_config_to_mapping(task) for task in tasks]}, handle, sort_keys=False)


def _split_csv(value: str) -> list[str]:
    """Split comma-separated prompt input.

    Args:
        value: Raw comma-separated text.

    Returns:
        Trimmed values.
    """

    return [item.strip() for item in value.split(",") if item.strip()]


async def launch_config_ui(
    tasks_file: str,
    task_store: TaskStore | None = None,
    metrics: MetricsCollector | None = None,
) -> None:
    """Launch the config UI.

    Args:
        tasks_file: YAML tasks path.
        task_store: Optional task history store.
        metrics: Optional metrics collector.

    Returns:
        None.
    """

    await ConfigUI(tasks_file=tasks_file, task_store=task_store, metrics=metrics).run()
