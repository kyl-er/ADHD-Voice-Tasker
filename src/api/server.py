"""FastAPI backend: REST + WebSocket fan-out to web UI / overlay / TUI.

  GET  /api/tasks            list (ranked)
  POST /api/tasks            create {title, category?, source_text?}
  PATCH /api/tasks/{id}      status/priority/pin/estimate…
  POST /api/tasks/{id}/dispatch {target: hermes|claude-code}
  GET  /api/projects         GET /api/ideas (tier-sorted)
  POST /api/capture          overlay quick-capture {text}
  WS   /ws                   store events + transcript captions
"""
from __future__ import annotations

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from src.config import Settings
from src.tasks.models import Status, Task
from src.tasks.store import Store

app = FastAPI(title="ADHD-Voice-Tasker")
store = Store()
sockets: list[WebSocket] = []


class TaskIn(BaseModel):
    title: str
    category: str = "general"
    source_text: str = ""


class TaskPatch(BaseModel):
    title: str | None = None
    status: Status | None = None
    priority: float | None = None
    pinned: bool | None = None
    estimate_min: int | None = None
    project_id: str | None = None


class DispatchIn(BaseModel):
    target: str  # hermes | claude-code


@app.on_event("startup")
async def _startup() -> None:
    import asyncio

    def forward(event: dict) -> None:
        for ws in list(sockets):
            asyncio.get_event_loop().create_task(ws.send_json(event))

    store.subscribe(forward)


@app.get("/api/health")
def health():
    s = Settings.load()
    return {"ok": s.ok, "issues": s.issues,
            "providers": [p.__dict__ for p in s.provider_status()]}


@app.get("/api/tasks")
def list_tasks():
    return [t.model_dump() for t in store.list_tasks()]


@app.post("/api/tasks")
def create_task(body: TaskIn):
    from src.voice.pipeline import VoicePipeline  # categorization lives here later
    return store.save_task(Task(title=body.title, category=body.category,
                                source_text=body.source_text)).model_dump()


@app.patch("/api/tasks/{task_id}")
def patch_task(task_id: str, body: TaskPatch):
    task = store.get_task(task_id) or Task(title="(missing)")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(task, k, v)
    import time
    task.updated_at = task.last_active = time.time()
    return store.save_task(task).model_dump()


@app.post("/api/tasks/{task_id}/dispatch")
def dispatch_task(task_id: str, body: DispatchIn):
    task = store.get_task(task_id)
    if not task:
        return {"error": "not found"}
    s = Settings.load()
    if body.target == "hermes":
        from src.dispatch import hermes
        res = hermes.dispatch(task, s.hermes_agent_path, s.hermes_agent_endpoint)
    else:
        from src.dispatch import claude_code
        res = claude_code.dispatch(task, s.claude_code_path,
                                   gateway_key=s.gateway_api_key)
    task.status = Status.IN_PROGRESS
    task.links.extend(res.links)
    store.save_task(task)
    return {"session_id": res.session_id, "task": task.model_dump()}


@app.post("/api/capture")
def quick_capture(body: TaskIn):
    """Win+Space overlay endpoint: text in → task out (fast loop in Phase 1)."""
    return store.save_task(Task(title=body.title, category="inbox",
                                source_text=body.source_text or body.title)).model_dump()


@app.websocket("/ws")
async def ws(ws: WebSocket):
    await ws.accept()
    sockets.append(ws)
    try:
        while True:
            await ws.receive_text()  # keep-alive; server pushes events
    except WebSocketDisconnect:
        sockets.remove(ws)
