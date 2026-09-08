"""FastAPI backend: REST + WebSocket fan-out to web UI / overlay / TUI.

Serves the demo UI itself at `/` (same origin → no CORS pain).

  GET  /                        the UI (demo.html)
  GET  /api/health              config + engine modes
  GET  /api/tasks               ranked, dep-ordered, project-enriched
  POST /api/tasks               direct create {title, category?, source_text?}
  PATCH /api/tasks/{id}         status/priority/pin/estimate…
  POST /api/tasks/{id}/dispatch {target: hermes|claude-code}
  GET  /api/projects            GET /api/ideas (tier-sorted)
  POST /api/capture             text in → extraction → tasks/ideas out
  POST /api/simulate/start      replay scripted voice session over WS
  WS   /ws                      task/idea/transcript/sim events
"""
from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src.config import Settings
from src.tasks.models import Status, Task
from src.tasks.ranker import topo_order
from src.tasks.store import Store
from src.voice.pipeline import VoicePipeline

ROOT = Path(__file__).resolve().parent.parent.parent
store = Store()
sockets: list[WebSocket] = []


async def broadcast(event: dict) -> None:
    dead = []
    for ws in list(sockets):
        try:
            await ws.send_json(event)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in sockets:
            sockets.remove(ws)


pipeline = VoicePipeline(store=store, emit=broadcast)


@asynccontextmanager
async def lifespan(app: FastAPI):
    def forward(event: dict) -> None:  # store is sync; hop onto the loop
        if event.get("type") == "task.upsert":
            event["project_name"] = _project_name(event["task"].get("project_id"))
        try:
            asyncio.get_running_loop().create_task(broadcast(event))
        except RuntimeError:
            pass

    store.subscribe(forward)
    yield


app = FastAPI(title="ADHD-Voice-Tasker")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])


def _project_name(pid: str | None) -> str:
    if not pid:
        return "Inbox"
    for p in store.list_projects():
        if p.id == pid:
            return p.name
    return "Inbox"


def _task_payload(t: Task) -> dict:
    d = t.model_dump()
    d["project_name"] = _project_name(t.project_id)
    return d


# -- UI ----------------------------------------------------------------
@app.get("/")
def index():
    return FileResponse(ROOT / "demo.html")


# -- health -------------------------------------------------------------
@app.get("/api/health")
def health():
    s = Settings.load()
    chain = s.fast_chain()
    return {"ok": s.ok, "issues": s.issues,
            "providers": [p.__dict__ for p in s.provider_status()],
            "mode": {"stt": "deepgram" if s.deepgram_api_key else "simulator",
                     "llm": chain[0] if chain else "heuristic",
                     "sim_running": pipeline.sim_running}}


# -- tasks --------------------------------------------------------------
@app.get("/api/tasks")
def list_tasks():
    return [_task_payload(t) for t in topo_order(store.list_tasks())]


class TaskIn(BaseModel):
    title: str = ""
    text: str = ""
    category: str = "general"
    source_text: str = ""


@app.post("/api/tasks")
def create_task(body: TaskIn):
    title = body.title or body.text
    return _task_payload(store.save_task(
        Task(title=title, category=body.category,
             source_text=body.source_text or title)))


class TaskPatch(BaseModel):
    title: str | None = None
    status: Status | None = None
    priority: float | None = None
    pinned: bool | None = None
    estimate_min: int | None = None
    elapsed_s: int | None = None
    project_id: str | None = None


@app.patch("/api/tasks/{task_id}")
def patch_task(task_id: str, body: TaskPatch):
    task = store.get_task(task_id)
    if not task:
        return {"error": "not found"}
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(task, k, v)
    task.updated_at = task.last_active = time.time()
    return _task_payload(store.save_task(task))


@app.get("/api/projects")
def list_projects():
    return [p.model_dump() for p in store.list_projects()]


@app.get("/api/ideas")
def list_ideas():
    return [i.model_dump() for i in store.list_ideas()]


# -- capture + dispatch --------------------------------------------------
class DispatchIn(BaseModel):
    target: str  # hermes | claude-code


@app.post("/api/capture")
async def quick_capture(body: TaskIn):
    """Win+Space overlay endpoint: text in → full extraction → tasks/ideas."""
    text = body.text or body.title
    if not text.strip():
        return {"error": "empty text"}
    return await pipeline.process_final(text)


@app.post("/api/tasks/{task_id}/dispatch")
def dispatch_task(task_id: str, body: DispatchIn):
    task = store.get_task(task_id)
    if not task:
        return {"error": "not found"}
    s = Settings.load()
    try:
        if body.target == "hermes":
            from src.dispatch import hermes
            res = hermes.dispatch(task, s.hermes_agent_path, s.hermes_agent_endpoint)
        else:
            from src.dispatch import claude_code
            res = claude_code.dispatch(task, s.claude_code_path,
                                       gateway_key=s.gateway_api_key)
    except Exception as e:  # noqa: BLE001 - surface as JSON, don't 500
        return {"error": str(e)[:200]}
    task.status = Status.IN_PROGRESS
    task.links.extend(res.links)
    store.save_task(task)
    return {"session_id": res.session_id, "task": _task_payload(task)}


# -- simulator ------------------------------------------------------------
@app.post("/api/simulate/start")
async def simulate_start():
    if pipeline.sim_running:
        return {"started": False, "reason": "already running"}
    asyncio.create_task(pipeline.run_simulation())
    return {"started": True}


# -- websocket -------------------------------------------------------------
@app.websocket("/ws")
async def ws(ws: WebSocket):
    await ws.accept()
    sockets.append(ws)
    try:
        await ws.send_json({"type": "hello",
                            "tasks": [_task_payload(t) for t in store.list_tasks()]})
        while True:
            await ws.receive_text()  # keep-alive; server pushes events
    except WebSocketDisconnect:
        if ws in sockets:
            sockets.remove(ws)
