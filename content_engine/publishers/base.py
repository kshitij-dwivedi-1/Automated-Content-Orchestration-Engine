"""Publisher abstraction and shared publish result."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(slots=True)
class PublishResult:
    """Result of a publishing attempt."""

    platform: str
    success: bool
    url: str | None = None
    error: str | None = None
    timestamp: str = ""

    def __post_init__(self) -> None:
        """Populate timestamp when omitted.

        Returns:
            None.
        """

        if not self.timestamp:
            self.timestamp = datetime.now(UTC).isoformat()

    def as_dict(self) -> dict[str, Any]:
        """Convert publish result to a serializable dictionary.

        Returns:
            Dictionary representation.
        """

        return {
            "platform": self.platform,
            "success": self.success,
            "url": self.url,
            "error": self.error,
            "timestamp": self.timestamp,
        }


class Publisher(ABC):
    """Abstract base publisher."""

    @abstractmethod
    async def publish(self, content: str, metadata: dict[str, Any]) -> PublishResult:
        """Publish content to a platform.

        Args:
            content: Content to publish.
            metadata: Platform-specific metadata.

        Returns:
            PublishResult with success or failure details.
        """

