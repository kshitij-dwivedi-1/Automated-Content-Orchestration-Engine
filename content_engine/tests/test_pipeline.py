"""Tests for pipeline behavior."""

from __future__ import annotations

import pytest

from content_engine.monitoring.alerts import AlertManager
from content_engine.monitoring.metrics import MetricsCollector
from content_engine.orchestrator.pipeline import Pipeline, PipelineContext
from content_engine.publishers.base import PublishResult, Publisher


class FakeAlertManager:
    """Collect alerts sent by the pipeline."""

    def __init__(self) -> None:
        """Initialize alert collection."""

        self.alerts: list[tuple[int | str, str, str, str]] = []

    async def alert(self, task_id: int | str, stage: str, error_message: str, severity: str) -> None:
        """Collect alert details.

        Args:
            task_id: Task identifier.
            stage: Stage name.
            error_message: Error text.
            severity: Severity.

        Returns:
            None.
        """

        self.alerts.append((task_id, stage, error_message, severity))


class FakePublisher(Publisher):
    """Publisher that returns a configured result."""

    def __init__(self, result: PublishResult) -> None:
        """Initialize fake publisher.

        Args:
            result: Publish result to return.
        """

        self.result = result

    async def publish(self, content: str, metadata: dict[str, object]) -> PublishResult:
        """Return configured publish result.

        Args:
            content: Ignored content.
            metadata: Ignored metadata.

        Returns:
            Configured result.
        """

        return self.result


async def fake_generate(_topic: str, _keywords: list[str], _tone: str, _word_count: int) -> str:
    """Return generated content.

    Args:
        _topic: Ignored topic.
        _keywords: Ignored keywords.
        _tone: Ignored tone.
        _word_count: Ignored word count.

    Returns:
        Fake content.
    """

    return "# Heading\n\nThis content mentions automation."


def fake_optimize(content: str, _keywords: list[str]) -> dict[str, object]:
    """Return optimized content.

    Args:
        content: Generated content.
        _keywords: Ignored keywords.

    Returns:
        SEO optimization result.
    """

    return {"score": 88, "optimized_content": content, "keyword_density": {}}


@pytest.mark.asyncio
async def test_pipeline_success() -> None:
    alerts = FakeAlertManager()
    pipeline = Pipeline(
        generator=fake_generate,
        optimizer=fake_optimize,
        publishers={"wordpress": FakePublisher(PublishResult(platform="wordpress", success=True, url="https://example.com"))},
        alert_manager=alerts,  # type: ignore[arg-type]
        metrics=MetricsCollector(),
    )

    result = await pipeline.run(PipelineContext(task_id=1, topic="Topic", keywords=["automation"], platforms=["wordpress"]))

    assert result.status == "succeeded"
    assert result.seo_score == 88
    assert result.publish_results[0]["success"] is True
    assert alerts.alerts == []


@pytest.mark.asyncio
async def test_pipeline_failure_alerts_and_skips_remaining_stages() -> None:
    async def broken_generate(_topic: str, _keywords: list[str], _tone: str, _word_count: int) -> str:
        """Raise during generation.

        Args:
            _topic: Ignored topic.
            _keywords: Ignored keywords.
            _tone: Ignored tone.
            _word_count: Ignored word count.

        Returns:
            Never returns.
        """

        raise RuntimeError("generation failed")

    alerts = FakeAlertManager()
    pipeline = Pipeline(
        generator=broken_generate,
        optimizer=fake_optimize,
        publishers={"wordpress": FakePublisher(PublishResult(platform="wordpress", success=True))},
        alert_manager=alerts,  # type: ignore[arg-type]
        metrics=MetricsCollector(),
    )

    result = await pipeline.run(PipelineContext(task_id=1, topic="Topic", keywords=["automation"], platforms=["wordpress"]))

    assert result.status == "failed"
    assert result.publish_results == []
    assert alerts.alerts[0][1] == "generate"

