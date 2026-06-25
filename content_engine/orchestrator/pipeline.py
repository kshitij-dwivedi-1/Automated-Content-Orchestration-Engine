"""Pipeline stage definitions for content generation through publishing."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog

from content_engine.constants import (
    MSG_MISSING_CONTENT,
    MSG_MISSING_KEYWORDS,
    STAGE_GENERATE,
    STAGE_NOTIFY,
    STAGE_PUBLISH,
    STAGE_SEO_OPTIMIZE,
    STAGE_VALIDATE,
    STATUS_FAILED,
    STATUS_RUNNING,
    STATUS_SUCCEEDED,
)
from content_engine.exceptions import PipelineStageError
from content_engine.monitoring.alerts import AlertManager
from content_engine.monitoring.metrics import MetricsCollector
from content_engine.publishers.base import Publisher


GenerateFn = Callable[[str, list[str], str, int], Awaitable[str]]
OptimizeFn = Callable[[str, list[str]], dict[str, object]]


@dataclass(slots=True)
class PipelineContext:
    """Shared state passed through pipeline stages."""

    task_id: int
    topic: str
    keywords: list[str]
    platforms: list[str]
    tone: str = "professional"
    word_count: int = 800
    raw_content: str | None = None
    optimized_content: str | None = None
    seo_score: int | None = None
    publish_results: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    status: str = STATUS_RUNNING
    timestamps: dict[str, float] = field(default_factory=dict)


class Pipeline:
    """Run content tasks through generate, optimize, validate, publish, notify."""

    def __init__(
        self,
        generator: GenerateFn,
        optimizer: OptimizeFn,
        publishers: dict[str, Publisher],
        alert_manager: AlertManager,
        metrics: MetricsCollector,
        logger: structlog.BoundLogger | None = None,
    ) -> None:
        """Initialize the pipeline.

        Args:
            generator: Async content generation function.
            optimizer: SEO optimization function.
            publishers: Platform publisher registry.
            alert_manager: Alert manager.
            metrics: Metrics collector.
            logger: Optional structured logger.
        """

        self.generator = generator
        self.optimizer = optimizer
        self.publishers = publishers
        self.alert_manager = alert_manager
        self.metrics = metrics
        self.logger = logger or structlog.get_logger(__name__)
        self.stages = [
            self.generate,
            self.seo_optimize,
            self.validate,
            self.publish,
            self.notify,
        ]

    async def run(self, context: PipelineContext) -> PipelineContext:
        """Run all pipeline stages until success or failure.

        Args:
            context: Initial pipeline context.

        Returns:
            Final pipeline context.
        """

        for stage in self.stages:
            stage_name = stage.__name__
            start = time.perf_counter()
            try:
                context = await stage(context)
                duration = time.perf_counter() - start
                context.timestamps[stage_name] = duration
                self.metrics.record_stage_latency(stage_name, duration)
                self.logger.info("stage_completed", task_id=context.task_id, stage=stage_name, duration_seconds=duration)
                if context.status == STATUS_FAILED:
                    break
            except Exception as exc:
                duration = time.perf_counter() - start
                context.timestamps[stage_name] = duration
                self.metrics.record_stage_latency(stage_name, duration)
                await self._mark_failed(context, stage_name, exc)
                break
        if context.status != STATUS_FAILED:
            context.status = STATUS_SUCCEEDED
        return context

    async def generate(self, context: PipelineContext) -> PipelineContext:
        """Generate raw draft content.

        Args:
            context: Pipeline context.

        Returns:
            Updated context.
        """

        context.raw_content = await self.generator(context.topic, context.keywords, context.tone, context.word_count)
        return context

    async def seo_optimize(self, context: PipelineContext) -> PipelineContext:
        """Optimize generated content for SEO.

        Args:
            context: Pipeline context.

        Returns:
            Updated context.
        """

        if not context.raw_content:
            raise PipelineStageError(MSG_MISSING_CONTENT)
        result = self.optimizer(context.raw_content, context.keywords)
        context.optimized_content = str(result["optimized_content"])
        context.seo_score = int(result["score"])
        return context

    async def validate(self, context: PipelineContext) -> PipelineContext:
        """Validate content before publishing.

        Args:
            context: Pipeline context.

        Returns:
            Updated context.
        """

        if not context.optimized_content:
            raise PipelineStageError(MSG_MISSING_CONTENT)
        if not context.keywords:
            raise PipelineStageError(MSG_MISSING_KEYWORDS)
        if not context.platforms:
            raise PipelineStageError("At least one platform is required.")
        return context

    async def publish(self, context: PipelineContext) -> PipelineContext:
        """Publish optimized content to requested platforms.

        Args:
            context: Pipeline context.

        Returns:
            Updated context.
        """

        assert context.optimized_content is not None
        for platform in context.platforms:
            publisher = self.publishers.get(platform)
            if not publisher:
                context.errors.append({"stage": STAGE_PUBLISH, "platform": platform, "error": "Unsupported platform."})
                continue
            result = await publisher.publish(context.optimized_content, {"topic": context.topic, "title": context.topic})
            result_dict = result.as_dict()
            context.publish_results.append(result_dict)
            if not result.success:
                context.errors.append({"stage": STAGE_PUBLISH, "platform": platform, "error": result.error})
        if context.publish_results and any(result.get("success") for result in context.publish_results):
            return context
        if context.errors:
            raise PipelineStageError("Publishing failed for all requested platforms.")
        return context

    async def notify(self, context: PipelineContext) -> PipelineContext:
        """Finalize successful task notification hooks.

        Args:
            context: Pipeline context.

        Returns:
            Updated context.
        """

        context.timestamps[STAGE_NOTIFY] = context.timestamps.get(STAGE_NOTIFY, 0.0)
        return context

    async def _mark_failed(self, context: PipelineContext, stage: str, exc: Exception) -> None:
        """Mark context failed and send alert.

        Args:
            context: Pipeline context.
            stage: Failed stage name.
            exc: Exception that caused failure.

        Returns:
            None.
        """

        context.status = STATUS_FAILED
        error = {
            "stage": stage,
            "error": str(exc),
            "timestamp": datetime.now(UTC).isoformat(),
        }
        context.errors.append(error)
        self.logger.error("stage_failed", task_id=context.task_id, stage=stage, error=str(exc))
        await self.alert_manager.alert(context.task_id, stage, str(exc), severity="high")

