"""Windows toast nudges for forgotten tasks.

Watcher logic: any task in {open+pinned, in-progress} idle longer than
FORGOTTEN_TASK_MINUTES gets: "Still on this? — '<title>' idle 1h 04m."
[Keep going] [Snooze 30m] [Done] map to API calls.

Windows: win10toast-click. Everywhere else: console fallback (no-op safe).
"""
from __future__ import annotations

import sys
import time
from src.tasks.models import Task


def idle_tasks(tasks: list[Task], forgotten_minutes: int,
               now: float | None = None) -> list[Task]:
    now = now or time.time()
    cutoff = forgotten_minutes * 60
    return [t for t in tasks
            if (t.status.value == "in-progress" or (t.status.value == "open" and t.pinned))
            and (now - t.last_active) > cutoff]


def notify(title: str, message: str, on_click=None) -> None:
    if sys.platform != "win32":
        print(f"[toast] {title} — {message}")
        return
    try:
        from win10toast_click import ToastNotifier  # type: ignore
    except ImportError:
        print(f"[toast:missing-dep] {title} — {message}")
        return
    ToastNotifier().show_toast(title, message, duration=10,
                               callback_on_click=on_click or (lambda: None), threaded=True)


def nudge(task: Task, idle_s: float) -> None:
    mins = int(idle_s // 60)
    notify("Still on this?",
           f"'{task.title}' has been idle {mins // 60}h {mins % 60:02d}m. "
           f"Keep going, snooze, or mark done from the Tasks tab.")
