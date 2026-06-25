"""Custom exceptions for the Automated Content Orchestration Engine."""

from __future__ import annotations


class ContentEngineError(Exception):
    """Base exception for all content engine errors."""


class ContentGenerationError(ContentEngineError):
    """Raised when all LLM content generation attempts fail."""


class PipelineStageError(ContentEngineError):
    """Raised when a pipeline stage fails."""


class PublishError(ContentEngineError):
    """Raised when publishing fails for a platform."""


class ConfigurationError(ContentEngineError):
    """Raised when configuration is invalid."""


class SchedulerConfigError(ContentEngineError):
    """Raised when scheduled task configuration cannot be parsed."""

