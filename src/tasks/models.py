"""Task / Project data models (pydantic)."""
from __future__ import annotations

import time
import uuid
from enum import Enum
from pydantic import BaseModel, Field


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


class Status(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in-progress"
    IN_REVIEW = "in-review"
    DONE = "done"
    SNOOZED = "snoozed"


class Link(BaseModel):
    kind: str  # agent-session | file | url | pr | branch
    label: str
    ref: str


class Task(BaseModel):
    id: str = Field(default_factory=lambda: _id("task"))
    title: str
    category: str = "general"
    project_id: str | None = None
    status: Status = Status.OPEN
    priority: float = 0.5  # 0..1, computed by ranker
    deps: list[str] = Field(default_factory=list)  # task ids that must finish first
    dep_order: int | None = None  # 1→2→3 position within its chain
    estimate_min: int = 25
    elapsed_s: int = 0
    pinned: bool = False
    links: list[Link] = Field(default_factory=list)
    source_text: str = ""  # transcript snippet it came from
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    last_active: float = Field(default_factory=time.time)

    @property
    def progress(self) -> float:
        if self.estimate_min <= 0:
            return 0.0
        return min(1.0, self.elapsed_s / (self.estimate_min * 60))


class Project(BaseModel):
    id: str = Field(default_factory=lambda: _id("proj"))
    name: str
    category: str = "general"
    goal: str = ""
    task_ids: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


class Idea(BaseModel):
    id: str = Field(default_factory=lambda: _id("idea"))
    title: str
    detail: str = ""
    tier: str = "C"  # S A B C D F
    scores: dict[str, float] = Field(default_factory=dict)
    verdict: str = ""
    next_step: str = ""
    created_at: float = Field(default_factory=time.time)
