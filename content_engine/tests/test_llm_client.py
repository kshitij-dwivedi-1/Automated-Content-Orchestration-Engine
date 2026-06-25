"""Tests for the async LLM client."""

from __future__ import annotations

import pytest

from content_engine.config.settings import Settings
from content_engine.exceptions import ContentGenerationError
from content_engine.generators.llm_client import LLMClient


class FakeChatCompletions:
    """Fake chat completions client with scripted responses."""

    def __init__(self, outcomes: list[object]) -> None:
        """Initialize fake outcomes.

        Args:
            outcomes: Exceptions or responses returned in order.
        """

        self.outcomes = outcomes
        self.calls: list[str] = []

    async def create(self, **kwargs: object) -> dict[str, object]:
        """Return or raise the next scripted outcome.

        Args:
            kwargs: Completion request parameters.

        Returns:
            Fake completion response.
        """

        self.calls.append(str(kwargs["model"]))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome  # type: ignore[return-value]


async def no_sleep(_delay: float) -> None:
    """Avoid retry delays in tests.

    Args:
        _delay: Ignored delay.

    Returns:
        None.
    """


@pytest.mark.asyncio
async def test_generate_content_retries_then_succeeds() -> None:
    settings = Settings(MAX_RETRIES=2, RETRY_DELAY_SECONDS=0, OPENAI_API_KEY="test")
    fake = FakeChatCompletions([RuntimeError("temporary"), {"choices": [{"message": {"content": "Generated draft"}}]}])
    client = LLMClient(settings=settings, chat_completions=fake, sleep=no_sleep)

    result = await client.generate_content("Topic", ["keyword"], "clear", 500)

    assert result == "Generated draft"
    assert fake.calls == ["gpt-4o", "gpt-4o"]


@pytest.mark.asyncio
async def test_generate_content_uses_fallback_after_primary_failures() -> None:
    settings = Settings(MAX_RETRIES=1, RETRY_DELAY_SECONDS=0, OPENAI_API_KEY="test", FALLBACK_MODEL="fallback")
    fake = FakeChatCompletions([RuntimeError("primary"), {"choices": [{"message": {"content": "Fallback draft"}}]}])
    client = LLMClient(settings=settings, chat_completions=fake, sleep=no_sleep)

    result = await client.generate_content("Topic", ["keyword"], "clear", 500)

    assert result == "Fallback draft"
    assert fake.calls == ["gpt-4o", "fallback"]


@pytest.mark.asyncio
async def test_generate_content_raises_when_all_attempts_fail() -> None:
    settings = Settings(MAX_RETRIES=1, RETRY_DELAY_SECONDS=0, OPENAI_API_KEY="test", FALLBACK_MODEL="fallback")
    fake = FakeChatCompletions([RuntimeError("primary"), RuntimeError("fallback")])
    client = LLMClient(settings=settings, chat_completions=fake, sleep=no_sleep)

    with pytest.raises(ContentGenerationError):
        await client.generate_content("Topic", ["keyword"], "clear", 500)

