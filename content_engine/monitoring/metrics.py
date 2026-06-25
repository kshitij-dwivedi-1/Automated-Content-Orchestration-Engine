"""In-process metrics collector for task and platform outcomes."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field


@dataclass(slots=True)
class MetricsCollector:
    """Track task counters, duration, stage latency, and platform publishes."""

    tasks_total: int = 0
    tasks_succeeded: int = 0
    tasks_failed: int = 0
    total_duration_seconds: float = 0.0
    stage_latencies: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    platform_publish_counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def record_task(self, duration_seconds: float, status: str, platform_results: list[dict[str, object]]) -> None:
        """Record completed task metrics.

        Args:
            duration_seconds: End-to-end task duration.
            status: Final task status.
            platform_results: Publish results from the task.

        Returns:
            None.
        """

        self.tasks_total += 1
        self.total_duration_seconds += duration_seconds
        if status == "succeeded":
            self.tasks_succeeded += 1
        else:
            self.tasks_failed += 1
        for result in platform_results:
            if result.get("success"):
                self.platform_publish_counts[str(result.get("platform"))] += 1

    def record_stage_latency(self, stage: str, duration_seconds: float) -> None:
        """Record a pipeline stage latency.

        Args:
            stage: Pipeline stage name.
            duration_seconds: Stage duration.

        Returns:
            None.
        """

        self.stage_latencies[stage].append(duration_seconds)

    def get_summary(self) -> dict[str, object]:
        """Return a serializable metrics summary.

        Returns:
            Metrics summary dictionary.
        """

        avg_duration = self.total_duration_seconds / self.tasks_total if self.tasks_total else 0.0
        avg_stage_latencies = {
            stage: round(sum(values) / len(values), 3) if values else 0.0
            for stage, values in self.stage_latencies.items()
        }
        return {
            "tasks_total": self.tasks_total,
            "tasks_succeeded": self.tasks_succeeded,
            "tasks_failed": self.tasks_failed,
            "avg_duration_seconds": round(avg_duration, 3),
            "stage_latencies": avg_stage_latencies,
            "platform_publish_counts": dict(self.platform_publish_counts),
        }

