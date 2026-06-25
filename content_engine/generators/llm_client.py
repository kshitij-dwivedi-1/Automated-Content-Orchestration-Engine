"""Async LLM client with retry and fallback behavior."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, Protocol

import structlog

from content_engine.config.settings import Settings
from content_engine.constants import LOG_EVENT_RETRY, PRIMARY_MODEL
from content_engine.exceptions import ContentGenerationError


class ChatCompletionClient(Protocol):
    """Protocol for testable chat completion clients."""

    async def create(self, **kwargs: Any) -> Any:
        """Create a chat completion.

        Args:
            kwargs: Provider-specific completion parameters.

        Returns:
            Provider completion response.
        """


SleepFn = Callable[[float], Awaitable[None]]


class LLMClient:
    """OpenAI-backed asynchronous content generator."""

    def __init__(
        self,
        settings: Settings,
        chat_completions: ChatCompletionClient | None = None,
        sleep: SleepFn = asyncio.sleep,
        logger: structlog.BoundLogger | None = None,
    ) -> None:
        """Initialize the LLM client.

        Args:
            settings: Application settings.
            chat_completions: Optional injected chat completions client.
            sleep: Async sleep function used for retries.
            logger: Optional structured logger.
        """

        self.settings = settings
        self._sleep = sleep
        self.logger = logger or structlog.get_logger(__name__)
        self._chat_completions = chat_completions

    async def generate_content(
        self,
        topic: str,
        keywords: list[str],
        tone: str,
        word_count: int,
    ) -> str:
        """Generate SEO-focused content through primary and fallback models.

        Args:
            topic: Content topic.
            keywords: Keywords to include.
            tone: Desired tone.
            word_count: Target word count.

        Returns:
            Generated content text.

        Raises:
            ContentGenerationError: If every model attempt fails.
        """

        last_error: Exception | None = None
        for model in (PRIMARY_MODEL, self.settings.FALLBACK_MODEL):
            try:
                return await self._generate_with_retries(model, topic, keywords, tone, word_count)
            except Exception as exc:
                last_error = exc
                self.logger.warning(
                    "model_failed",
                    model=model,
                    timestamp=datetime.now(UTC).isoformat(),
                    error=str(exc),
                )
        raise ContentGenerationError(f"Content generation failed: {last_error}") from last_error

    async def _generate_with_retries(
        self,
        model: str,
        topic: str,
        keywords: list[str],
        tone: str,
        word_count: int,
    ) -> str:
        """Generate content with exponential retry backoff.

        Args:
            model: Model name to use.
            topic: Content topic.
            keywords: Keywords to include.
            tone: Desired tone.
            word_count: Target word count.

        Returns:
            Generated content text.
        """

        last_error: Exception | None = None
        attempts = max(1, self.settings.MAX_RETRIES)
        for attempt in range(1, attempts + 1):
            try:
                response = await self._chat().create(
                    model=model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are an expert SEO content strategist. "
                                "Return polished publish-ready prose with clear headings."
                            ),
                        },
                        {
                            "role": "user",
                            "content": (
                                f"Write about: {topic}\n"
                                f"Tone: {tone}\n"
                                f"Target words: {word_count}\n"
                                f"Keywords: {', '.join(keywords)}"
                            ),
                        },
                    ],
                    temperature=0.7,
                )
                content = self._extract_text(response)
                if content:
                    return content
                raise ContentGenerationError("LLM response did not contain text.")
            except Exception as exc:
                last_error = exc
                if attempt == attempts:
                    break
                delay = self.settings.RETRY_DELAY_SECONDS * (2 ** (attempt - 1))
                self.logger.warning(
                    LOG_EVENT_RETRY,
                    model=model,
                    attempt=attempt,
                    next_attempt=attempt + 1,
                    delay_seconds=delay,
                    timestamp=datetime.now(UTC).isoformat(),
                    error=str(exc),
                )
                await self._sleep(delay)
        raise ContentGenerationError(f"{model} failed after {attempts} attempts: {last_error}") from last_error

    def _chat(self) -> ChatCompletionClient:
        """Return an injected or lazily constructed chat completion client.

        Returns:
            Chat completion client.
        """

        if self._chat_completions is not None:
            return self._chat_completions
        if self.settings.OPENAI_API_KEY is None:
            raise ContentGenerationError("OPENAI_API_KEY is required for content generation.")
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self.settings.OPENAI_API_KEY.get_secret_value())
        self._chat_completions = client.chat.completions
        return self._chat_completions

    @staticmethod
    def _extract_text(response: Any) -> str:
        """Extract text from an OpenAI chat completion response.

        Args:
            response: Provider response object or dictionary.

        Returns:
            Response text if present, otherwise an empty string.
        """

        if isinstance(response, dict):
            choices = response.get("choices", [])
            if not choices:
                return ""
            message = choices[0].get("message", {})
            return str(message.get("content", "")).strip()
        choices = getattr(response, "choices", [])
        if not choices:
            return ""
        message = getattr(choices[0], "message", None)
        return str(getattr(message, "content", "") or "").strip()


async def generate_content(
    topic: str,
    keywords: list[str],
    tone: str,
    word_count: int,
    settings: Settings | None = None,
    chat_completions: ChatCompletionClient | None = None,
) -> str:
    """Generate content using default settings or injected dependencies.

    Args:
        topic: Content topic.
        keywords: Keywords to include.
        tone: Desired tone.
        word_count: Target word count.
        settings: Optional application settings.
        chat_completions: Optional injected chat completions client.

    Returns:
        Generated content text.
    """

    client = LLMClient(settings or Settings(), chat_completions=chat_completions)
    return await client.generate_content(topic, keywords, tone, word_count)

