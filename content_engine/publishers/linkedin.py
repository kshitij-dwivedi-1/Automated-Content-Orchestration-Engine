"""LinkedIn REST API publisher."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp
import structlog

from content_engine.config.settings import Settings
from content_engine.constants import HTTP_RATE_LIMIT, LINKEDIN_UGC_POSTS_PATH, LOG_EVENT_PUBLISH_RESPONSE, PLATFORM_LINKEDIN
from content_engine.publishers.base import PublishResult, Publisher


class LinkedInPublisher(Publisher):
    """Publish content to LinkedIn UGC posts."""

    def __init__(
        self,
        settings: Settings,
        base_url: str = "https://api.linkedin.com",
        session: aiohttp.ClientSession | None = None,
        logger: structlog.BoundLogger | None = None,
    ) -> None:
        """Initialize the LinkedIn publisher.

        Args:
            settings: Application settings.
            base_url: LinkedIn API base URL.
            session: Optional aiohttp session.
            logger: Optional structured logger.
        """

        self.settings = settings
        self.base_url = base_url.rstrip("/")
        self.session = session
        self.logger = logger or structlog.get_logger(__name__)

    async def publish(self, content: str, metadata: dict[str, Any]) -> PublishResult:
        """Publish a LinkedIn UGC post.

        Args:
            content: Content to publish.
            metadata: Publish metadata.

        Returns:
            PublishResult describing the outcome.
        """

        author = str(metadata.get("linkedin_author_urn") or self.settings.LINKEDIN_AUTHOR_URN or "")
        if not self.settings.LINKEDIN_ACCESS_TOKEN or not author:
            return PublishResult(platform=PLATFORM_LINKEDIN, success=False, error="LinkedIn token or author URN is missing.")
        payload = {
            "author": author,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": content},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }
        headers = {
            "Authorization": f"Bearer {self.settings.LINKEDIN_ACCESS_TOKEN.get_secret_value()}",
            "X-Restli-Protocol-Version": "2.0.0",
        }
        return await self._post(f"{self.base_url}{LINKEDIN_UGC_POSTS_PATH}", payload, headers)

    async def _post(self, url: str, payload: dict[str, Any], headers: dict[str, str]) -> PublishResult:
        """POST payload to LinkedIn with rate-limit retry.

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
                    body_text = await response.text()
                    self.logger.info(LOG_EVENT_PUBLISH_RESPONSE, platform=PLATFORM_LINKEDIN, status=response.status)
                    if response.status in {200, 201, 202}:
                        post_id = response.headers.get("x-restli-id")
                        return PublishResult(platform=PLATFORM_LINKEDIN, success=True, url=post_id)
                    if response.status == HTTP_RATE_LIMIT and attempt < self.settings.MAX_RETRIES:
                        await asyncio.sleep(self.settings.RETRY_DELAY_SECONDS * attempt)
                        continue
                    return PublishResult(platform=PLATFORM_LINKEDIN, success=False, error=body_text)
        except Exception as exc:
            return PublishResult(platform=PLATFORM_LINKEDIN, success=False, error=str(exc))
        finally:
            if close_session:
                await session.close()

