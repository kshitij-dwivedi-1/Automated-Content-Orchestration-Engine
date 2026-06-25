"""Async task engine backed by asyncio.Queue."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import UTC, datetime

import structlog

from content_engine.config.settings import TaskConfig
from content_engine.constants import STATUS_FAILED, STATUS_RUNNING
from content_engine.monitoring.metrics import MetricsCollector
from content_engine.orchestrator.pipeline import Pipeline, PipelineContext
from content_engine.storage.task_store import TaskStore


@dataclass(slots=True)
class QueuedTask:
    """Queued task item."""

    task_id: int
    config: TaskConfig


class OrchestrationEngine:
    """Manage task queue workers and persist outcomes."""

    def __init__(
        self,
        pipeline: Pipeline,
        task_store: TaskStore,
        metrics: MetricsCollector,
        worker_count: int = 5,
        logger: structlog.BoundLogger | None = None,
    ) -> None:
        """Initialize the orchestration engine.

        Args:
            pipeline: Content pipeline.
            task_store: Persistent task store.
            metrics: Metrics collector.
            worker_count: Number of concurrent workers.
            logger: Optional structured logger.
        """

        self.pipeline = pipeline
        self.task_store = task_store
        self.metrics = metrics
        self.worker_count = worker_count
        self.logger = logger or structlog.get_logger(__name__)
        self.queue: asyncio.Queue[QueuedTask] = asyncio.Queue()
        self._workers: list[asyncio.Task[None]] = []
        self._stopping = asyncio.Event()

    async def start(self) -> None:
        """Start worker pool.

        Returns:
            None.
        """

        self._stopping.clear()
        self._workers = [asyncio.create_task(self._worker(index), name=f"content-worker-{index}") for index in range(self.worker_count)]

    async def submit(self, task_config: TaskConfig) -> int:
        """Persist and enqueue a task.

        Args:
            task_config: Task configuration.

        Returns:
            Created task identifier.
        """

        task_id = await self.task_store.create_task(task_config)
        await self.queue.put(QueuedTask(task_id=task_id, config=task_config))
        self.logger.info("task_queued", task_id=task_id, topic=task_config.topic)
        return task_id

    async def stop(self, drain: bool = True) -> None:
        """Stop workers, optionally draining queued work first.

        Args:
            drain: Whether to wait for queued tasks to finish.

        Returns:
            None.
        """

        if drain:
            await self.queue.join()
        self._stopping.set()
        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)

    async def _worker(self, index: int) -> None:
        """Run one queue worker.

        Args:
            index: Worker index.

        Returns:
            None.
        """

        while not self._stopping.is_set():
            task = await self.queue.get()
            try:
                await self._process(task)
            except Exception as exc:
                self.logger.error("worker_task_error", worker=index, task_id=task.task_id, error=str(exc))
                await self.task_store.update_task(
                    task.task_id,
                    status=STATUS_FAILED,
                    errors=[{"stage": "worker", "error": str(exc)}],
                    completed_at=datetime.now(UTC).isoformat(),
                )
            finally:
                self.queue.task_done()

    async def _process(self, task: QueuedTask) -> None:
        """Process a queued task through the pipeline.

        Args:
            task: Queued task.

        Returns:
            None.
        """

        await self.task_store.update_task(task.task_id, status=STATUS_RUNNING)
        started = time.perf_counter()
        context = PipelineContext(
            task_id=task.task_id,
            topic=task.config.topic,
            keywords=task.config.keywords,
            platforms=task.config.platforms,
            tone=task.config.tone,
            word_count=task.config.word_count,
        )
        result = await self.pipeline.run(context)
        duration = time.perf_counter() - started
        self.metrics.record_task(duration, result.status, result.publish_results)
        await self.task_store.update_task(
            task.task_id,
            status=result.status,
            seo_score=result.seo_score,
            publish_results=result.publish_results,
            errors=result.errors,
            completed_at=datetime.now(UTC).isoformat(),
        )
        self.logger.info("task_completed", task_id=task.task_id, status=result.status, duration_seconds=duration)

