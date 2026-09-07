"""SEND TO PROCESS → Hermes Agent.

Takes a task + generated brief, spawns the Hermes binary (HERMES_AGENT_PATH)
or POSTs to HERMES_AGENT_ENDPOINT, and returns a session link for the task.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from src.tasks.models import Link, Task


@dataclass
class DispatchResult:
    session_id: str
    links: list[Link]
    note: str = ""


def build_brief(task: Task, project_goal: str = "") -> str:
    deps = ", ".join(task.deps) or "none"
    return (f"GOAL: {task.title}\nPROJECT GOAL: {project_goal or 'n/a'}\n"
            f"DEPENDS ON: {deps}\nCONTEXT: {task.source_text or 'n/a'}\n"
            f"ACCEPTANCE: task is demonstrably complete; list files changed.")


def dispatch(task: Task, hermes_path: str = "", endpoint: str = "",
             project_goal: str = "") -> DispatchResult:
    brief = build_brief(task, project_goal)
    if endpoint:
        import urllib.request
        req = urllib.request.Request(
            endpoint.rstrip("/") + "/dispatch",
            data=json.dumps({"task_id": task.id, "brief": brief}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        return DispatchResult(data.get("session_id", "remote"),
                              [Link(kind="agent-session", label="Hermes session",
                                    ref=data.get("session_url", endpoint))])
    if not hermes_path:
        raise RuntimeError("Set HERMES_AGENT_PATH or HERMES_AGENT_ENDPOINT in .env")
    proc = subprocess.run([hermes_path, "run", "--brief", brief,
                           "--output", "json"], capture_output=True, text=True, timeout=120)
    data = json.loads(proc.stdout or "{}")
    links = [Link(kind="agent-session", label="Hermes session",
                  ref=data.get("session_path", hermes_path))]
    for f in data.get("files", []):
        links.append(Link(kind="file", label=f, ref=f))
    return DispatchResult(data.get("session_id", "local"), links)
