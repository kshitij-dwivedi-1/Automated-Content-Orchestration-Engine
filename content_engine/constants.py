"""Shared constants for the Automated Content Orchestration Engine."""

from __future__ import annotations

APP_NAME = "Automated Content Orchestration Engine"

PRIMARY_MODEL = "gpt-4o"
DEFAULT_FALLBACK_MODEL = "gpt-3.5-turbo"
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY_SECONDS = 1.0
DEFAULT_WORKER_COUNT = 5
DEFAULT_DATABASE_PATH = "content_engine.db"
DEFAULT_TASKS_FILE = "tasks.yaml"

STAGE_GENERATE = "generate"
STAGE_SEO_OPTIMIZE = "seo_optimize"
STAGE_VALIDATE = "validate"
STAGE_PUBLISH = "publish"
STAGE_NOTIFY = "notify"

STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_SUCCEEDED = "succeeded"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"

PLATFORM_WORDPRESS = "wordpress"
PLATFORM_TWITTER = "twitter"
PLATFORM_LINKEDIN = "linkedin"

WORDPRESS_POSTS_PATH = "/wp-json/wp/v2/posts"
TWITTER_TWEETS_PATH = "/2/tweets"
LINKEDIN_UGC_POSTS_PATH = "/v2/ugcPosts"

LOG_EVENT_RETRY = "retry_scheduled"
LOG_EVENT_STAGE_COMPLETED = "stage_completed"
LOG_EVENT_STAGE_FAILED = "stage_failed"
LOG_EVENT_PUBLISH_RESPONSE = "publish_response"
LOG_EVENT_SCHEDULER_RELOADED = "scheduler_reloaded"

MSG_NO_TASKS = "No scheduled tasks found."
MSG_ENGINE_STARTING = "Starting engine and scheduler."
MSG_ENGINE_STOPPING = "Stopping engine and draining queued work."
MSG_TASK_ADDED = "Task added."
MSG_INVALID_PLATFORM = "Unsupported platform requested."
MSG_MISSING_CONTENT = "Generated content is empty."
MSG_MISSING_KEYWORDS = "At least one keyword is required."
MSG_ALERT_SUBJECT = "Content pipeline failure"

HTTP_RATE_LIMIT = 429
TWITTER_CHARACTER_LIMIT = 280
ALERT_TIMEOUT_SECONDS = 30

