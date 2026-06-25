"""Tests for SQLite task persistence."""

from __future__ import annotations

from content_engine.config.settings import TaskConfig
from content_engine.storage.task_store import TaskStore


async def test_task_store_persists_task_lifecycle(tmp_path) -> None:
    store = TaskStore(str(tmp_path / "tasks.db"))
    await store.migrate()

    task_id = await store.create_task(
        TaskConfig(
            topic="SEO briefs",
            keywords=["seo brief"],
            platforms=["wordpress"],
        )
    )
    await store.update_task(
        task_id,
        status="succeeded",
        seo_score=91,
        publish_results=[{"platform": "wordpress", "success": True, "url": "https://example.com/post"}],
        errors=[],
        completed_at="2026-06-25T00:00:00+00:00",
    )

    task = await store.get_task(task_id)
    rows = await store.list_tasks(limit=10)

    assert task is not None
    assert task["topic"] == "SEO briefs"
    assert task["status"] == "succeeded"
    assert task["seo_score"] == 91
    assert task["publish_results"][0]["platform"] == "wordpress"
    assert rows[0]["id"] == task_id
