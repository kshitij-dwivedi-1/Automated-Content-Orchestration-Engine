"""SQLite-backed task queue state persistence."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import aiosqlite

from content_engine.config.settings import TaskConfig
from content_engine.constants import STATUS_QUEUED


class TaskStore:
    """Persist content task state in SQLite."""

    def __init__(self, database_path: str) -> None:
        """Initialize task store.

        Args:
            database_path: SQLite database path.
        """

        self.database_path = database_path

    async def migrate(self) -> None:
        """Create database tables if they do not exist.

        Returns:
            None.
        """

        async with aiosqlite.connect(self.database_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    seo_score INTEGER,
                    publish_results_json TEXT,
                    error_json TEXT
                )
                """
            )
            await db.commit()

    async def create_task(self, task: TaskConfig) -> int:
        """Create a persisted task row.

        Args:
            task: Task configuration.

        Returns:
            New task identifier.
        """

        now = datetime.now(UTC).isoformat()
        async with aiosqlite.connect(self.database_path) as db:
            cursor = await db.execute(
                "INSERT INTO tasks (topic, status, created_at) VALUES (?, ?, ?)",
                (task.topic, STATUS_QUEUED, now),
            )
            await db.commit()
            return int(cursor.lastrowid)

    async def update_task(
        self,
        task_id: int,
        status: str,
        seo_score: int | None = None,
        publish_results: list[dict[str, Any]] | None = None,
        errors: list[dict[str, Any]] | None = None,
        completed_at: str | None = None,
    ) -> None:
        """Update task state and output fields.

        Args:
            task_id: Task identifier.
            status: Task status.
            seo_score: Optional SEO score.
            publish_results: Optional publish results.
            errors: Optional error list.
            completed_at: Optional completion timestamp.

        Returns:
            None.
        """

        async with aiosqlite.connect(self.database_path) as db:
            await db.execute(
                """
                UPDATE tasks
                SET status = ?, completed_at = ?, seo_score = ?,
                    publish_results_json = ?, error_json = ?
                WHERE id = ?
                """,
                (
                    status,
                    completed_at,
                    seo_score,
                    json.dumps(publish_results or []),
                    json.dumps(errors or []),
                    task_id,
                ),
            )
            await db.commit()

    async def get_task(self, task_id: int) -> dict[str, Any] | None:
        """Fetch one task by identifier.

        Args:
            task_id: Task identifier.

        Returns:
            Task row dictionary or None.
        """

        async with aiosqlite.connect(self.database_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            row = await cursor.fetchone()
        return self._row_to_dict(row) if row else None

    async def list_tasks(self, status_filter: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
        """List tasks, optionally filtered by status.

        Args:
            status_filter: Optional status filter.
            limit: Optional maximum row count.

        Returns:
            Task row dictionaries.
        """

        query = "SELECT * FROM tasks"
        params: list[Any] = []
        if status_filter:
            query += " WHERE status = ?"
            params.append(status_filter)
        query += " ORDER BY id DESC"
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        async with aiosqlite.connect(self.database_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
        return [self._row_to_dict(row) for row in rows]

    @staticmethod
    def _row_to_dict(row: aiosqlite.Row) -> dict[str, Any]:
        """Convert SQLite row to a dictionary.

        Args:
            row: SQLite row.

        Returns:
            Decoded task dictionary.
        """

        data = dict(row)
        data["publish_results"] = json.loads(data.pop("publish_results_json") or "[]")
        data["errors"] = json.loads(data.pop("error_json") or "[]")
        return data

