"""Priority ranker + dependency DAG utilities.

priority = 0.45*urgency + 0.25*dep_weight + 0.15*staleness + 0.15*pin_boost
dep_order is assigned by topo-sort so the UI can render 1→2→3 chains.
"""
from __future__ import annotations

import time
from src.tasks.models import Task

URGENT_WORDS = ("urgent", "asap", "now", "today", "deadline", "blocking", "must")


def urgency_of(task: Task) -> float:
    text = f"{task.title} {task.source_text}".lower()
    hits = sum(1 for w in URGENT_WORDS if w in text)
    return min(1.0, 0.3 + 0.25 * hits)


def topo_order(tasks: list[Task]) -> list[Task]:
    """Topological sort by deps; assigns dep_order (1-based) per chain."""
    by_id = {t.id: t for t in tasks}
    order: list[Task] = []
    seen: set[str] = set()

    def visit(t: Task, stack: set[str]) -> None:
        if t.id in seen or t.id in stack:
            return
        stack.add(t.id)
        for d in t.deps:
            if d in by_id:
                visit(by_id[d], stack)
        stack.remove(t.id)
        seen.add(t.id)
        order.append(t)

    for t in tasks:
        visit(t, set())
    for i, t in enumerate(order, 1):
        t.dep_order = i
    return order


def rank(tasks: list[Task], now: float | None = None) -> list[Task]:
    now = now or time.time()
    ordered = topo_order(tasks)
    depth = {t.id: i for i, t in enumerate(ordered)}
    for t in ordered:
        staleness = min(1.0, (now - t.last_active) / 86400)  # 1 day → 1.0
        t.priority = round(
            0.45 * urgency_of(t)
            + 0.25 * (1 - depth[t.id] / max(1, len(ordered)))  # deps-first
            + 0.15 * staleness
            + 0.15 * (1.0 if t.pinned else 0.0),
            3,
        )
    return sorted(ordered, key=lambda t: -t.priority)
