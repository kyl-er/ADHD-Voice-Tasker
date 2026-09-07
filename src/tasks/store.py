"""SQLite store + in-memory pub/sub. Every mutation emits an event dict
that the API server broadcasts over WebSocket to all UIs (no polling)."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Callable

from src.tasks.models import Idea, Project, Task

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ideas (id TEXT PRIMARY KEY, data TEXT NOT NULL);
"""


class Store:
    def __init__(self, path: str | Path = "./data/tasks.db"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._subs: list[Callable[[dict], None]] = []
        with self._conn() as c:
            c.executescript(SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    # -- pub/sub -----------------------------------------------------
    def subscribe(self, fn: Callable[[dict], None]) -> None:
        self._subs.append(fn)

    def _emit(self, event: dict) -> None:
        for fn in self._subs:
            fn(event)

    # -- tasks -------------------------------------------------------
    def save_task(self, task: Task) -> Task:
        with self._conn() as c:
            c.execute("INSERT OR REPLACE INTO tasks VALUES (?, ?)",
                      (task.id, task.model_dump_json()))
        self._emit({"type": "task.upsert", "task": task.model_dump()})
        return task

    def get_task(self, task_id: str) -> Task | None:
        with self._conn() as c:
            row = c.execute("SELECT data FROM tasks WHERE id=?", (task_id,)).fetchone()
        return Task.model_validate_json(row[0]) if row else None

    def list_tasks(self, status: str | None = None) -> list[Task]:
        with self._conn() as c:
            rows = c.execute("SELECT data FROM tasks").fetchall()
        tasks = [Task.model_validate_json(r[0]) for r in rows]
        if status:
            tasks = [t for t in tasks if t.status == status]
        return sorted(tasks, key=lambda t: (-t.priority, t.created_at))

    def save_project(self, proj: Project) -> Project:
        with self._conn() as c:
            c.execute("INSERT OR REPLACE INTO projects VALUES (?, ?)",
                      (proj.id, proj.model_dump_json()))
        self._emit({"type": "project.upsert", "project": proj.model_dump()})
        return proj

    def list_projects(self) -> list[Project]:
        with self._conn() as c:
            rows = c.execute("SELECT data FROM projects").fetchall()
        return [Project.model_validate_json(r[0]) for r in rows]

    # -- ideas -------------------------------------------------------
    def save_idea(self, idea: Idea) -> Idea:
        with self._conn() as c:
            c.execute("INSERT OR REPLACE INTO ideas VALUES (?, ?)",
                      (idea.id, idea.model_dump_json()))
        self._emit({"type": "idea.upsert", "idea": idea.model_dump()})
        return idea

    def list_ideas(self) -> list[Idea]:
        order = {"S": 0, "A": 1, "B": 2, "C": 3, "D": 4, "F": 5}
        with self._conn() as c:
            rows = c.execute("SELECT data FROM ideas").fetchall()
        ideas = [Idea.model_validate_json(r[0]) for r in rows]
        return sorted(ideas, key=lambda i: (order.get(i.tier, 3), i.created_at))
