"""Tests for YAML loading and schedule parsing."""

from __future__ import annotations

import pytest
from apscheduler.triggers.cron import CronTrigger

from content_engine.config.settings import task_configs_from_yaml_root
from content_engine.exceptions import ConfigurationError, SchedulerConfigError
from content_engine.orchestrator.scheduler import TaskScheduler


def test_task_configs_from_yaml_root_accepts_top_level_list() -> None:
    tasks = task_configs_from_yaml_root(
        [
            {
                "topic": "Weekly content calendar",
                "keywords": "content calendar, weekly plan",
                "platforms": "twitter, linkedin",
            }
        ]
    )

    assert tasks[0].topic == "Weekly content calendar"
    assert tasks[0].keywords == ["content calendar", "weekly plan"]
    assert tasks[0].platforms == ["twitter", "linkedin"]


def test_task_configs_from_yaml_root_rejects_missing_topic() -> None:
    with pytest.raises(ConfigurationError, match="Task topic is required"):
        task_configs_from_yaml_root({"tasks": [{"keywords": ["seo"], "platforms": ["wordpress"]}]})


def test_parse_trigger_allows_comma_list_values() -> None:
    trigger = TaskScheduler._parse_trigger("cron:day_of_week=mon,wed,fri,hour=10,minute=30")

    assert isinstance(trigger, CronTrigger)
    fields = {field.name: str(field) for field in trigger.fields}
    assert fields["day_of_week"] == "mon,wed,fri"
    assert fields["hour"] == "10"
    assert fields["minute"] == "30"


def test_parse_kwargs_rejects_bare_schedule_value() -> None:
    with pytest.raises(SchedulerConfigError, match="Invalid schedule argument"):
        TaskScheduler._parse_kwargs("mon,wed")
