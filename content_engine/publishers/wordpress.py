"""WordPress REST API publisher."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp
import structlog

from content_engine.config.settings import Settings
from content_engine.constants import HTTP_RATE_LIMIT, LOG_EVENT_PUBLISH_RESPONSE, PLATFORM_WORDPRESS, WORDPRESS_POSTS_PATH
from content_engine.publishers.base import PublishResult, Publisher


class WordPressPublisher(Publisher):
    """Publish content through the WordPress REST API."""

    def __init__(
        self,
        settings: Settings,
        session: aiohttp.ClientSession | None = None,
        logger: structlog.BoundLogger | None = None,
    ) -> None:
        """Initialize the WordPress publisher.

        Args:
            settings: Application settings.
            session: Optional aiohttp session.
            logger: Optional structured logger.
        """

        self.settings = settings
        self.session = session
        self.logger = logger or structlog.get_logger(__name__)

    async def publish(self, content: str, metadata: dict[str, Any]) -> PublishResult:
        """Publish a WordPress post.

        Args:
            content: Content to publish.
            metadata: Publish metadata such as title and status.

        Returns:
            PublishResult describing the outcome.
        """

        if not self.settings.WORDPRESS_URL or not self.settings.WORDPRESS_USER or not self.settings.WORDPRESS_APP_PASSWORD:
            return PublishResult(platform=PLATFORM_WORDPRESS, success=False, error="WordPress credentials are incomplete.")
        url = f"{self.settings.WORDPRESS_URL.rstrip('/')}{WORDPRESS_POSTS_PATH}"
        payload = {
            "title": metadata.get("title") or metadata.get("topic") or "Generated Content",
            "content": content,
            "status": metadata.get("status", "draft"),
        }
        auth = aiohttp.BasicAuth(
            self.settings.WORDPRESS_USER,
            self.settings.WORDPRESS_APP_PASSWORD.get_secret_value(),
        )
        return await self._post(url, payload, auth=auth)

    async def _post(self, url: str, payload: dict[str, Any], auth: aiohttp.BasicAuth) -> PublishResult:
        """POST payload to WordPress with rate-limit retry.

        Args:
            url: Endpoint URL.
            payload: JSON payload.
            auth: Basic authentication object.

        Returns:
            PublishResult describing the outcome.
        """

        session = self.session or aiohttp.ClientSession()
        close_session = self.session is None
        try:
            for attempt in range(1, self.settings.MAX_RETRIES + 1):
                async with session.post(url, json=payload, auth=auth) as response:
                    body = await response.json(content_type=None)
                    self.logger.info(LOG_EVENT_PUBLISH_RESPONSE, platform=PLATFORM_WORDPRESS, status=response.status)
                    if response.status in {200, 201}:
                        return PublishResult(platform=PLATFORM_WORDPRESS, success=True, url=body.get("link"))
                    if response.status == HTTP_RATE_LIMIT and attempt < self.settings.MAX_RETRIES:
                        await asyncio.sleep(self.settings.RETRY_DELAY_SECONDS * attempt)
                        continue
                    return PublishResult(platform=PLATFORM_WORDPRESS, success=False, error=str(body))
        except Exception as exc:
            return PublishResult(platform=PLATFORM_WORDPRESS, success=False, error=str(exc))
        finally:
            if close_session:
                await session.close()

