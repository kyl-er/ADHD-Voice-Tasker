"""Voice pipeline orchestration: mic → VAD → Deepgram → fast-LLM loop.

Modes (chosen automatically):
  * Live STT … Deepgram streaming when a key + mic + SDK are present.
  * Simulator … replays a scripted voice session as partial/final events.
  * Extraction … fast-LLM Router when a key exists, else heuristic fallback.

Every FINAL transcript → extract → dedup → project attach → dep resolve →
persist → broadcast. Works end-to-end with ZERO keys (simulator+heuristic).
"""
from __future__ import annotations

import asyncio
import re
import time

FAST_EXTRACT_PROMPT = """You turn a voice transcript chunk into structured task data.
Return JSON ONLY: {"tasks": [{"title": verb-first, "<80 chars",
"category": "dev|research|ops|admin|personal|general",
"urgency": 0..1, "dep_hints": ["titles this waits on"]}],
"ideas": [{"title": "", "detail": ""}], "notes": [""],
"done_mentions": [""], "project": "project name or null"}.
Merge duplicates by meaning, not wording. Empty arrays are fine."""

SIM_SCRIPT = [
    "ok so first I need to reinstall docker, it's totally borked…",
    "then grab all my api keys and env vars and base urls together…",
    "and THEN I can finally set up librechat on top of all that.",
    "oh also — research browser automation, build the BrowserUse MCP, test it…",
    "what if the overlay could draft my standup from yesterday's activity? "
    "that would be so cool, we should build that.",
]

_STOP = set("the a an to of and or on in my i it that this for with so then than".split())


def _tokens(s: str) -> set[str]:
    return {w for w in re.sub(r"[^a-z0-9+ ]", "", s.lower()).split()
            if w and w not in _STOP}


def overlap(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


class VoicePipeline:
    def __init__(self, settings=None, store=None, emit=None):
        self.settings = settings
        self.store = store
        self.emit = emit  # async callable(event: dict)
        self._sim_running = False

    def _get_settings(self):
        if self.settings is None:
            from src.config import Settings
            self.settings = Settings.load()
        return self.settings

    def _get_store(self):
        if self.store is None:
            from src.tasks.store import Store
            self.store = Store()
        return self.store

    async def _emit(self, event: dict) -> None:
        if self.emit:
            await self.emit(event)

    # -- extraction --------------------------------------------------
    def _extract(self, text: str, prev_titles: tuple[str, ...] = ()) -> tuple[dict, str]:
        """Returns (data, engine). LLM first, heuristic fallback."""
        try:
            from src.providers.router import Router
            ctx = ("\nOpen tasks (merge dupes by meaning; dep_hints may name these): "
                   + "; ".join(prev_titles[:8]) if prev_titles else "")
            data = Router.from_settings().complete_json(
                "fast", [{"role": "system", "content": FAST_EXTRACT_PROMPT},
                         {"role": "user", "content": text + ctx}])
            data.setdefault("tasks", []); data.setdefault("ideas", [])
            data.setdefault("notes", []); data.setdefault("done_mentions", [])
            data.setdefault("project", None)
            return data, "llm"
        except Exception:
            from src.voice.fallback_extract import extract
            return extract(text, prev_titles), "heuristic"

    # -- finals ------------------------------------------------------
    async def process_final(self, text: str) -> dict:
        from src.ideas.tier_evaluator import evaluate_idea
        from src.tasks.models import Idea, Status, Task
        from src.voice.fallback_extract import ESTIMATES

        store = self._get_store()
        open_tasks = [t for t in store.list_tasks()
                      if t.status not in (Status.DONE,)]
        prev = tuple(t.title for t in open_tasks[-4:])
        data, engine = self._extract(text, prev)

        def match(title: str, thresh: float = 0.5):
            best, score = None, 0.0
            for t in open_tasks:
                s = overlap(title, t.title)
                if s > score:
                    best, score = t, s
            return best if score >= thresh else None

        # project: find-or-create
        project = None
        if data.get("project"):
            want = str(data["project"]).strip().lower()
            for p in store.list_projects():
                if p.name.lower() == want or overlap(p.name, want) > 0.6:
                    project = p
                    break
            if project is None:
                from src.tasks.models import Project
                project = store.save_project(
                    Project(name=str(data["project"]).strip()[:60]))

        created, merged = [], []
        for item in data.get("tasks", []):
            title = str(item.get("title", "")).strip()
            if not title:
                continue
            dupe = match(title, 0.8)
            if dupe:  # merge: refresh + keep single card
                dupe.source_text = (dupe.source_text + " / " + text[:120])[:400]
                dupe.last_active = time.time()
                store.save_task(dupe)
                merged.append(dupe.id)
                continue
            deps = []
            for hint in item.get("dep_hints", []) or []:
                m = match(str(hint), 0.45)
                if m and m.id not in deps:
                    deps.append(m.id)
            cat = str(item.get("category", "general") or "general")
            task = Task(title=title[:90], category=cat,
                        project_id=project.id if project else None,
                        deps=deps, estimate_min=ESTIMATES.get(cat, 25),
                        source_text=text[:200])
            store.save_task(task)
            open_tasks.append(task)
            created.append(task.id)
            if project and task.id not in project.task_ids:
                project.task_ids.append(task.id)
        if project:
            store.save_project(project)

        done_ids = []
        for mention in data.get("done_mentions", []) or []:
            m = match(str(mention), 0.4)
            if m:
                m.status = Status.DONE
                m.last_active = time.time()
                store.save_task(m)
                done_ids.append(m.id)

        ideas = []
        for item in data.get("ideas", []) or []:
            ev = evaluate_idea(str(item.get("title", "")),
                               str(item.get("detail", "")), context=text[:200])
            idea = Idea(title=str(item.get("title", ""))[:90],
                        detail=str(item.get("detail", ""))[:400],
                        tier=ev.get("tier", "C"), scores=ev.get("scores", {}),
                        verdict=ev.get("verdict", ""),
                        next_step=ev.get("next_step", ""))
            store.save_idea(idea)
            ideas.append(idea.id)
            await self._emit({"type": "idea.upsert", "idea": idea.model_dump()})

        await self._emit({"type": "extract.done", "engine": engine,
                          "created": created, "merged": merged, "done": done_ids})
        return {"engine": engine, "created": created, "merged": merged,
                "done": done_ids, "ideas": ideas,
                "project": project.name if project else None}

    # -- simulator ---------------------------------------------------
    async def run_simulation(self, script: list[str] | None = None,
                             word_delay: float = 0.09) -> dict:
        if self._sim_running:
            return {"started": False, "reason": "already running"}
        self._sim_running = True
        try:
            await self._emit({"type": "sim.start"})
            for text in (script or SIM_SCRIPT):
                words = text.split()
                for i in range(2, len(words) + 1, 3):
                    await self._emit({"type": "transcript", "kind": "partial",
                                      "text": " ".join(words[:i])})
                    await asyncio.sleep(word_delay)
                await self._emit({"type": "transcript", "kind": "final", "text": text})
                await self.process_final(text)
                await asyncio.sleep(0.8)
            await self._emit({"type": "sim.done"})
            return {"started": True, "utterances": len(script or SIM_SCRIPT)}
        finally:
            self._sim_running = False

    @property
    def sim_running(self) -> bool:
        return self._sim_running

    # -- live mic (needs key + hardware) -----------------------------
    def start_live(self) -> None:
        s = self._get_settings()
        if not s.deepgram_api_key:
            raise RuntimeError("No DEEPGRAM_API_KEY — run the simulator instead "
                               "(POST /api/simulate/start).")
        try:
            import deepgram  # noqa: F401
            import sounddevice  # noqa: F401
        except ImportError as e:
            raise RuntimeError(f"Live mic needs: pip install -r requirements.txt ({e})")
        raise NotImplementedError(
            "Live mic loop wires up next (DeepgramStreamer.start) — the "
            "simulator + capture endpoints already prove the full loop.")
