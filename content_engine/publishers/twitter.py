"""Twitter/X API v2 publisher."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp
import structlog

from content_engine.config.settings import Settings
from content_engine.constants import HTTP_RATE_LIMIT, LOG_EVENT_PUBLISH_RESPONSE, PLATFORM_TWITTER, TWITTER_CHARACTER_LIMIT, TWITTER_TWEETS_PATH
from content_engine.publishers.base import PublishResult, Publisher


class TwitterPublisher(Publisher):
    """Publish content as Twitter/X posts."""

    def __init__(
        self,
        settings: Settings,
        base_url: str = "https://api.twitter.com",
        session: aiohttp.ClientSession | None = None,
        logger: structlog.BoundLogger | None = None,
    ) -> None:
        """Initialize the Twitter publisher.

        Args:
            settings: Application settings.
            base_url: Twitter API base URL.
            session: Optional aiohttp session.
            logger: Optional structured logger.
        """

        self.settings = settings
        self.base_url = base_url.rstrip("/")
        self.session = session
        self.logger = logger or structlog.get_logger(__name__)

    async def publish(self, content: str, metadata: dict[str, Any]) -> PublishResult:
        """Publish a tweet.

        Args:
            content: Content to publish.
            metadata: Publish metadata.

        Returns:
            PublishResult describing the outcome.
        """

        if not self.settings.TWITTER_BEARER_TOKEN:
            return PublishResult(platform=PLATFORM_TWITTER, success=False, error="Twitter bearer token is missing.")
        text = content[: TWITTER_CHARACTER_LIMIT - 1].rstrip() + "…" if len(content) > TWITTER_CHARACTER_LIMIT else content
        headers = {"Authorization": f"Bearer {self.settings.TWITTER_BEARER_TOKEN.get_secret_value()}"}
        return await self._post(f"{self.base_url}{TWITTER_TWEETS_PATH}", {"text": text}, headers=headers)

    async def _post(self, url: str, payload: dict[str, Any], headers: dict[str, str]) -> PublishResult:
        """POST payload to Twitter with rate-limit retry.

        Args:
            url: Endpoint URL.
            payload: JSON payload.
            headers: Request headers.

        Returns:
            PublishResult describing the outcome.
        """

        session = self.session or aiohttp.ClientSession()
        close_session = self.session is None
        try:
            for attempt in range(1, self.settings.MAX_RETRIES + 1):
                async with session.post(url, json=payload, headers=headers) as response:
                    body = await response.json(content_type=None)
                    self.logger.info(LOG_EVENT_PUBLISH_RESPONSE, platform=PLATFORM_TWITTER, status=response.status)
                    if response.status in {200, 201}:
                        tweet_id = body.get("data", {}).get("id")
                        url_value = f"https://twitter.com/i/web/status/{tweet_id}" if tweet_id else None
                        return PublishResult(platform=PLATFORM_TWITTER, success=True, url=url_value)
                    if response.status == HTTP_RATE_LIMIT and attempt < self.settings.MAX_RETRIES:
                        await asyncio.sleep(self.settings.RETRY_DELAY_SECONDS * attempt)
                        continue
                    return PublishResult(platform=PLATFORM_TWITTER, success=False, error=str(body))
        except Exception as exc:
            return PublishResult(platform=PLATFORM_TWITTER, success=False, error=str(exc))
        finally:
            if close_session:
                await session.close()

