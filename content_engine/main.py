"""Typer CLI entrypoint and runtime bootstrap."""

from __future__ import annotations

import asyncio
import signal
from collections.abc import Callable

import structlog
import typer
from rich.console import Console
from rich.table import Table

from content_engine.config.settings import Settings
from content_engine.constants import (
    APP_NAME,
    MSG_ENGINE_STARTING,
    MSG_ENGINE_STOPPING,
    PLATFORM_LINKEDIN,
    PLATFORM_TWITTER,
    PLATFORM_WORDPRESS,
)
from content_engine.generators.llm_client import LLMClient
from content_engine.generators.seo_optimizer import optimize
from content_engine.monitoring.alerts import AlertManager
from content_engine.monitoring.metrics import MetricsCollector
from content_engine.orchestrator.engine import OrchestrationEngine
from content_engine.orchestrator.pipeline import Pipeline
from content_engine.orchestrator.scheduler import TaskScheduler
from content_engine.publishers.linkedin import LinkedInPublisher
from content_engine.publishers.twitter import TwitterPublisher
from content_engine.publishers.wordpress import WordPressPublisher
from content_engine.storage.task_store import TaskStore
from content_engine.ui.config_ui import ConfigUI

app = typer.Typer(help=APP_NAME)
console = Console()


def configure_logging() -> None:
    """Configure JSON structured logging.

    Returns:
        None.
    """

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(20),
        cache_logger_on_first_use=True,
    )


def build_runtime(settings: Settings) -> tuple[OrchestrationEngine, TaskScheduler, TaskStore, MetricsCollector]:
    """Build runtime dependencies.

    Args:
        settings: Application settings.

    Returns:
        Engine, scheduler, task store, and metrics collector.
    """

    logger = structlog.get_logger(__name__)
    metrics = MetricsCollector()
    task_store = TaskStore(settings.DATABASE_PATH)
    llm_client = LLMClient(settings)
    alert_manager = AlertManager(settings)
    publishers = {
        PLATFORM_WORDPRESS: WordPressPublisher(settings),
        PLATFORM_TWITTER: TwitterPublisher(settings),
        PLATFORM_LINKEDIN: LinkedInPublisher(settings),
    }
    pipeline = Pipeline(
        generator=llm_client.generate_content,
        optimizer=optimize,
        publishers=publishers,
        alert_manager=alert_manager,
        metrics=metrics,
        logger=logger,
    )
    engine = OrchestrationEngine(
        pipeline=pipeline,
        task_store=task_store,
        metrics=metrics,
        worker_count=settings.CONTENT_WORKERS,
        logger=logger,
    )
    scheduler = TaskScheduler(engine=engine, tasks_file=settings.TASKS_FILE, logger=logger)
    return engine, scheduler, task_store, metrics


@app.command()
def run() -> None:
    """Start the orchestration engine and scheduler.

    Returns:
        None.
    """

    asyncio.run(_run_async())


async def _run_async() -> None:
    """Async implementation for the run command.

    Returns:
        None.
    """

    configure_logging()
    settings = Settings()
    engine, scheduler, task_store, _metrics = build_runtime(settings)
    await task_store.migrate()
    logger = structlog.get_logger(__name__)
    logger.info("engine_starting", message=MSG_ENGINE_STARTING)
    await engine.start()
    await scheduler.start()
    stop_event = asyncio.Event()
    _install_signal_handlers(stop_event.set)
    await stop_event.wait()
    logger.info("engine_stopping", message=MSG_ENGINE_STOPPING)
    await scheduler.shutdown()
    await engine.stop(drain=True)


@app.command("add-task")
def add_task() -> None:
    """Launch the interactive config UI to add or edit a task.

    Returns:
        None.
    """

    asyncio.run(_config_ui_async())


@app.command("list-tasks")
def list_tasks() -> None:
    """Show scheduled tasks from tasks.yaml.

    Returns:
        None.
    """

    settings = Settings()
    ui = ConfigUI(settings.TASKS_FILE)
    asyncio.run(ui.view_scheduled_tasks())


@app.command()
def history(limit: int = typer.Option(20, help="Number of task runs to show.")) -> None:
    """Show persisted task history.

    Args:
        limit: Number of task rows to display.

    Returns:
        None.
    """

    asyncio.run(_history_async(limit))


@app.command()
def metrics() -> None:
    """Print current metrics summary.

    Returns:
        None.
    """

    metrics_collector = MetricsCollector()
    console.print_json(data=metrics_collector.get_summary())


async def _config_ui_async() -> None:
    """Run the interactive config UI with storage initialized.

    Returns:
        None.
    """

    settings = Settings()
    task_store = TaskStore(settings.DATABASE_PATH)
    await task_store.migrate()
    await ConfigUI(settings.TASKS_FILE, task_store=task_store, metrics=MetricsCollector()).run()


async def _history_async(limit: int) -> None:
    """Render task history table.

    Args:
        limit: Number of rows.

    Returns:
        None.
    """

    settings = Settings()
    task_store = TaskStore(settings.DATABASE_PATH)
    await task_store.migrate()
    rows = await task_store.list_tasks(limit=limit)
    table = Table(title="Task History")
    table.add_column("ID")
    table.add_column("Topic")
    table.add_column("Status")
    table.add_column("SEO")
    table.add_column("Completed")
    for row in rows:
        table.add_row(str(row["id"]), row["topic"], row["status"], str(row.get("seo_score") or ""), str(row.get("completed_at") or ""))
    console.print(table)


def _install_signal_handlers(on_stop: Callable[[], None]) -> None:
    """Install SIGINT/SIGTERM handlers.

    Args:
        on_stop: Callback invoked on signal.

    Returns:
        None.
    """

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, on_stop)
        except NotImplementedError:
            signal.signal(sig, lambda *_args: on_stop())


if __name__ == "__main__":
    app()

