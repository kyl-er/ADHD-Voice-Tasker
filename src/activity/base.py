"""Phase 4 (SPEC, not built): ambient activity tracking.

Each collector polls a source and writes normalized ActivityEvents.
A `cheap`-role loop model (gateway qwen3.8-flash — pennies/M tokens)
clusters events → tasks every N minutes. It MUST be the cheapest model
because it runs forever inside loops.

Collectors (all opt-in, local-first, secrets redacted pre-LLM):
  agent_sessions  watch Hermes/Claude session dirs + JSONL
  chat_uis        LibreChat/ChatUI export API or local DB tail
  browser_tabs    companion extension → POST /api/activity/tab
  history         opt-in Chrome/Edge history SQLite reader (locked copy)
  cli_logs        PROMPT_COMMAND / PSReadLine hook → POST /api/activity/cmd
  live_window     active-window poller, 5s cadence, local only
  github          webhooks + poll: pushes/PRs/issues → branch/task links
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class ActivityEvent:
    source: str  # one of the collectors above
    summary: str
    refs: dict = field(default_factory=dict)  # files | urls | branch | session
    ts: float = field(default_factory=time.time)


class BaseCollector:
    source = "base"

    def poll(self) -> list[ActivityEvent]:
        raise NotImplementedError("Phase 4")
