"""SEND TO PROCESS → Claude Code CLI.

Shells `claude -p "<brief>" --output-format json` with ANTHROPIC_BASE_URL
pointed at the LLM Gateway so spend bills to the DevPass plan, and parses
the session id + touched files back into task links.
"""
from __future__ import annotations

import json
import os
import subprocess
from src.dispatch.hermes import DispatchResult, build_brief
from src.tasks.models import Link, Task


def dispatch(task: Task, claude_path: str = "claude",
             gateway_base: str = "https://api.llmgateway.io",
             gateway_key: str = "", project_goal: str = "") -> DispatchResult:
    env = dict(os.environ)
    if gateway_key:  # route Claude spend through the gateway
        env["ANTHROPIC_BASE_URL"] = gateway_base
        env["ANTHROPIC_AUTH_TOKEN"] = gateway_key
    proc = subprocess.run(
        [claude_path, "-p", build_brief(task, project_goal),
         "--output-format", "json"],
        capture_output=True, text=True, timeout=600, env=env)
    data = json.loads(proc.stdout or "{}")
    links = [Link(kind="agent-session", label="Claude Code session",
                  ref=data.get("session_id", "local"))]
    for f in data.get("files", []) or data.get("touched_files", []):
        links.append(Link(kind="file", label=f, ref=f))
    return DispatchResult(data.get("session_id", "local"), links,
                          note=data.get("summary", ""))
