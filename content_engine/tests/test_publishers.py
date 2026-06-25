"""Tests for publisher implementations."""

from __future__ import annotations

import pytest

from content_engine.config.settings import Settings
from content_engine.publishers.twitter import TwitterPublisher


class FakeResponse:
    """Async context manager response for aiohttp-like tests."""

    def __init__(self, status: int, body: dict[str, object]) -> None:
        """Initialize fake response.

        Args:
            status: HTTP status code.
            body: JSON body.
        """

        self.status = status
        self.body = body

    async def __aenter__(self) -> "FakeResponse":
        """Enter response context.

        Returns:
            This response.
        """

        return self

    async def __aexit__(self, *_args: object) -> None:
        """Exit response context.

        Args:
            *_args: Ignored exception details.

        Returns:
            None.
        """

    async def json(self, content_type: str | None = None) -> dict[str, object]:
        """Return fake JSON body.

        Args:
            content_type: Ignored content type.

        Returns:
            Fake JSON body.
        """

        return self.body


class FakeSession:
    """Fake aiohttp session."""

    def __init__(self) -> None:
        """Initialize fake session."""

        self.payloads: list[dict[str, object]] = []
        self.closed = False

    def post(self, _url: str, json: dict[str, object], headers: dict[str, str]) -> FakeResponse:
        """Collect payload and return success.

        Args:
            _url: Ignored URL.
            json: Request payload.
            headers: Request headers.

        Returns:
            Fake response.
        """

        self.payloads.append(json)
        assert headers["Authorization"].startswith("Bearer ")
        return FakeResponse(201, {"data": {"id": "123"}})

    async def close(self) -> None:
        """Close fake session.

        Returns:
            None.
        """

        self.closed = True


@pytest.mark.asyncio
async def test_twitter_publisher_truncates_to_character_limit() -> None:
    settings = Settings(TWITTER_BEARER_TOKEN="token", MAX_RETRIES=1)
    session = FakeSession()
    publisher = TwitterPublisher(settings=settings, session=session)  # type: ignore[arg-type]

    result = await publisher.publish("x" * 500, {})

    assert result.success is True
    assert len(str(session.payloads[0]["text"])) == 280
    assert result.url == "https://twitter.com/i/web/status/123"

