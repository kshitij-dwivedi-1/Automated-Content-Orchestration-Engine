# Automated Content Orchestration Engine

Async Python service for SEO content generation, optimization, scheduling, publishing, metrics, and alerting.

The engine reads scheduled content jobs from `tasks.yaml`, generates draft content with OpenAI, optimizes the draft for SEO, validates the task, publishes to configured platforms, and persists run history in SQLite.

## Features

- Async worker pool for concurrent content jobs
- YAML-driven task scheduling with cron and interval expressions
- OpenAI-backed content generation with retry and fallback model behavior
- SEO optimization stage with keyword scoring
- Publishers for WordPress, Twitter/X, and LinkedIn
- SQLite task history storage
- Metrics collection for task outcomes, stage latency, and publish counts
- Optional Slack and email alerting hooks
- Typer CLI with Rich terminal output

## Project Structure

```text
content_engine/
  config/          Environment settings and task config parsing
  generators/      OpenAI client and SEO optimization
  monitoring/      Metrics and alerting
  orchestrator/    Pipeline, scheduler, and async worker engine
  publishers/      WordPress, Twitter/X, and LinkedIn integrations
  storage/         SQLite task history store
  ui/              Interactive task configuration UI
  main.py          Typer CLI entry point
tasks.yaml         Sample scheduled content jobs
.env.example       Environment variable template
```

## Requirements

- Python 3.11 or newer
- Platform credentials for any publishers you enable
- `OPENAI_API_KEY` for live content generation

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Edit `.env` with your credentials and runtime settings.

## Configuration

Common environment variables:

```text
OPENAI_API_KEY=sk-...
FALLBACK_MODEL=gpt-3.5-turbo
MAX_RETRIES=3
RETRY_DELAY_SECONDS=1

WORDPRESS_URL=https://example.com
WORDPRESS_USER=admin
WORDPRESS_APP_PASSWORD=...

TWITTER_BEARER_TOKEN=...

LINKEDIN_ACCESS_TOKEN=...
LINKEDIN_AUTHOR_URN=urn:li:person:...

CONTENT_WORKERS=5
DATABASE_PATH=content_engine.db
TASKS_FILE=tasks.yaml
```

Alerting is optional. Configure `SLACK_WEBHOOK_URL`, `ALERT_EMAIL`, and `SMTP_CONFIG__...` values only when you want failure alerts sent outside the process.

## Task Format

Tasks can be stored as a top-level list or under a `tasks` key. Example:

```yaml
tasks:
  - topic: "AI workflow automation for marketing teams"
    keywords:
      - "AI workflow automation"
      - "marketing operations"
      - "content orchestration"
    platforms:
      - wordpress
      - linkedin
    tone: "strategic and practical"
    word_count: 900
    schedule_time: "cron:hour=9,minute=0"
```

Supported schedule examples:

- `interval:hours=24`
- `cron:hour=9,minute=0`
- `cron:day_of_week=mon,wed,fri,hour=10,minute=30`

## CLI Usage

Show available commands:

```powershell
python -m content_engine.main --help
```

List configured tasks:

```powershell
python -m content_engine.main list-tasks
```

Start the scheduler and worker engine:

```powershell
python -m content_engine.main run
```

Open the interactive task UI:

```powershell
python -m content_engine.main add-task
```

Show persisted task history:

```powershell
python -m content_engine.main history --limit 20
```

Print in-memory metrics summary:

```powershell
python -m content_engine.main metrics
```

## Testing

```powershell
pytest -q
```

Current verification:

```text
11 passed in 0.93s
```

## Notes

- Live generation requires `OPENAI_API_KEY`.
- Publishing integrations return clear failure results when credentials are missing.
- WordPress posts are created as drafts by default.
- The `metrics` command creates a fresh collector and reports current in-process counters; persisted historical runs are available through `history`.
