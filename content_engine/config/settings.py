"""Configuration models and environment loading."""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from content_engine.constants import (
    DEFAULT_DATABASE_PATH,
    DEFAULT_FALLBACK_MODEL,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_DELAY_SECONDS,
    DEFAULT_TASKS_FILE,
    DEFAULT_WORKER_COUNT,
)
from content_engine.exceptions import ConfigurationError


class SMTPConfig(BaseModel):
    """SMTP configuration for email alerts."""

    host: str | None = None
    port: int = 587
    username: str | None = None
    password: SecretStr | None = None
    start_tls: bool = True
    sender: str | None = None


@dataclass(slots=True)
class TaskConfig:
    """User-defined content task configuration.

    Args:
        topic: Content topic to generate.
        keywords: SEO keywords to target.
        platforms: Destination platform names.
        tone: Writing tone for the generated draft.
        word_count: Target word count.
        schedule_time: APScheduler-style schedule string.
    """

    topic: str
    keywords: list[str]
    platforms: list[str]
    tone: str = "professional"
    word_count: int = 800
    schedule_time: str = "interval:hours=24"


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env.

    Returns:
        Settings populated from environment variables, .env, and defaults.
    """

    OPENAI_API_KEY: SecretStr | None = None
    FALLBACK_MODEL: str = DEFAULT_FALLBACK_MODEL
    MAX_RETRIES: int = DEFAULT_MAX_RETRIES
    RETRY_DELAY_SECONDS: float = DEFAULT_RETRY_DELAY_SECONDS

    WORDPRESS_URL: str | None = None
    WORDPRESS_USER: str | None = None
    WORDPRESS_APP_PASSWORD: SecretStr | None = None

    TWITTER_BEARER_TOKEN: SecretStr | None = None
    LINKEDIN_ACCESS_TOKEN: SecretStr | None = None
    LINKEDIN_AUTHOR_URN: str | None = None

    SLACK_WEBHOOK_URL: str | None = None
    ALERT_EMAIL: str | None = None
    SMTP_CONFIG: SMTPConfig = Field(default_factory=SMTPConfig)

    CONTENT_WORKERS: int = DEFAULT_WORKER_COUNT
    DATABASE_PATH: str = DEFAULT_DATABASE_PATH
    TASKS_FILE: str = DEFAULT_TASKS_FILE

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )


def task_config_from_mapping(data: dict[str, object]) -> TaskConfig:
    """Create a TaskConfig from YAML or API input.

    Args:
        data: Mapping with task configuration fields.

    Returns:
        Parsed TaskConfig instance.
    """

    topic = str(data.get("topic", "")).strip()
    if not topic:
        raise ConfigurationError("Task topic is required.")
    keywords = data.get("keywords") or []
    platforms = data.get("platforms") or []
    if isinstance(keywords, str):
        keywords = [item.strip() for item in keywords.split(",") if item.strip()]
    if isinstance(platforms, str):
        platforms = [item.strip() for item in platforms.split(",") if item.strip()]
    if not isinstance(keywords, list):
        raise ConfigurationError("Task keywords must be a list or comma-separated string.")
    if not isinstance(platforms, list):
        raise ConfigurationError("Task platforms must be a list or comma-separated string.")
    return TaskConfig(
        topic=topic,
        keywords=[str(keyword).strip() for keyword in keywords if str(keyword).strip()],
        platforms=[str(platform).strip() for platform in platforms if str(platform).strip()],
        tone=str(data.get("tone", "professional")),
        word_count=int(data.get("word_count", 800)),
        schedule_time=str(data.get("schedule_time", "interval:hours=24")),
    )


def task_configs_from_yaml_root(raw: object) -> list[TaskConfig]:
    """Parse supported tasks.yaml root shapes into task configs.

    Args:
        raw: YAML root object. Supported shapes are a top-level task list or a
            mapping with a ``tasks`` list.

    Returns:
        Parsed task configurations.
    """

    if raw is None:
        return []
    if isinstance(raw, dict):
        items = raw.get("tasks", [])
    elif isinstance(raw, list):
        items = raw
    else:
        raise ConfigurationError("tasks.yaml must contain a list or a top-level tasks list.")
    if not isinstance(items, list):
        raise ConfigurationError("tasks.yaml must contain a list or a top-level tasks list.")
    configs: list[TaskConfig] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ConfigurationError(f"Task at index {index} must be a mapping.")
        configs.append(task_config_from_mapping(item))
    return configs


def task_config_to_mapping(task: TaskConfig) -> dict[str, object]:
    """Convert a TaskConfig into a YAML-friendly mapping.

    Args:
        task: Task configuration to serialize.

    Returns:
        Dictionary representation.
    """

    return {
        "topic": task.topic,
        "keywords": task.keywords,
        "platforms": task.platforms,
        "tone": task.tone,
        "word_count": task.word_count,
        "schedule_time": task.schedule_time,
    }
