# ADHD-Voice-Tasker — System Architecture

**One-line pitch:** Talk out loud about what you're working on. A fast voice→LLM
loop turns speech into tracked tasks, grouped projects, priorities, dependency
order, S–F ranked ideas, and agent dispatches — with a gorgeous voice
visualizer and a Win+Space quick-capture overlay.

> Status: **design + foundation scaffold (Phase 0)**. The wizard, config,
> provider router, task models, and visualizer stubs are real code; the
> activity-tracking panopticon (Phase 4) is specified but intentionally not
> built yet.

---

## 1. Pipeline overview

```
 ┌────────┐   PCM 16kHz   ┌────────────┐  WebSocket   ┌──────────────────┐
 │  MIC   ├──────────────►│    VAD     ├─────────────►│  DEEPGRAM Nova-3 │  $0.0077/min
 └────────┘  (sounddevice)│ gate+chunk │  streaming   │  (or Flux turns) │  streaming STT
 ┌────────┐               └────────────┘              └────────┬─────────┘
 │Win+Space│  quick capture overlay ──► same pipeline ────────┘
 │overlay │                                                    │ partial + final
 └────────┘                                                    ▼ transcripts
                                                     ┌──────────────────┐
                                                     │  FAST LLM ROUTER │  ◄── the hot loop
                                                     │ Cerebras │ Groq  │  ~100–2000 tok/s
                                                     │ │ LLM Gateway    │  task extract,
                                                     └────────┬─────────┘  categorize, dedup,
                                                              │ JSON events  deps, rank
                                                              ▼
                                                     ┌──────────────────┐
                                                     │   TASK ENGINE    │  sqlite + pub/sub
                                                     │ tasks│projects│  │  WS fan-out to UIs
                                                     │ time │deps│links │──► TUI / Web / Overlay
                                                     └────────┬─────────┘
                                                              │ dispatch
                                               ┌──────────────┼──────────────┐
                                               ▼              ▼              ▼
                                         ┌──────────┐  ┌───────────┐  ┌───────────┐
                                         │  HERMES  │  │CLAUDE CODE│  │WIN TOASTS │
                                         │  Agent   │  │    CLI    │  │  nudges   │
                                         └──────────┘  └───────────┘  └───────────┘
```

**Latency budget (speech → task card on screen):** Deepgram partials ~300ms,
fast-LLM extraction ~300–800ms, render <16ms. Total perceived: **under ~1.5s**
for the card to appear, refining as you keep talking.

---

## 2. Provider layer (`src/providers/`)

All LLM providers are **OpenAI-compatible**, so one client shape talks to all
three. The router picks per call-type, with automatic fallback.

| Role | 1st choice | Why | Fallback |
|---|---|---|---|
| STT streaming | **Deepgram Nova-3** (`nova-3`) | Sub-300ms partials, $0.0077/min streaming, diarization + keyterm add-ons | `flux-general-en` turn-taking mode |
| Hot loop (extract/categorize/dedup) | **Cerebras** `llama3.1-8b` (~1800+ tok/s) | Raw throughput king; cheap per token | Groq `llama-3.1-8b-instant` |
| Realtime chat/agent turns | **Groq** `llama-3.3-70b-versatile` | Sub-100ms TTFT, best SDK polish for agents | Cerebras `llama-3.3-70b` |
| Smart reasoning (deps, tiers, eval) | **LLM Gateway** `muse-spark-1.3` | 200+ models behind one key/base URL | `kimi-k3`, `gpt-5` via same gateway |
| Cheap background loops (Phase 4 activity scan) | **LLM Gateway** `qwen3.8-flash` ($0.14/$0.28 per M) | Pennies per million tokens; survives infinite loops | Groq 8b-instant |

**LLM Gateway / DevPass details** (OpenAI-compatible):

- Base URL: `https://api.llmgateway.io/v1`
- Auth: `Authorization: Bearer llmgtwy_...`
- Model IDs are canonical without provider prefix on DevPass coding plans
  (e.g. `muse-spark-1.3`, not `anthropic/muse-spark-1.3`); the gateway routes.
- Claude-Code-style tools use `ANTHROPIC_BASE_URL=https://api.llmgateway.io`
  (no `/v1`) + `ANTHROPIC_AUTH_TOKEN`. Our `claude_code.py` dispatcher
  reuses this convention so dispatched sessions also bill to the gateway.

`src/providers/router.py` exposes:

```python
router.complete(role="fast" | "smart" | "cheap", messages=[...]) -> str
router.complete_json(role, messages, schema) -> dict   # structured output
```

`role="fast"` → `FAST_LLM_PROVIDER` from `.env` (cerebras|groq|gateway),
`role="smart"` → `SMART_LLM_PROVIDER`, `role="cheap"` → always the cheapest
configured (gateway flash → groq 8b → cerebras 8b).

---

## 3. Voice pipeline (`src/voice/pipeline.py`)

1. **Capture** — `sounddevice` @ 16kHz mono float32, 100ms frames into a ring
   buffer. The same frames feed the visualizers (no second capture path).
2. **VAD gate** — energy + zero-crossing gate (upgrade path: Silero VAD) so
   silence never hits the paid STT socket.
3. **Deepgram streaming** — one WebSocket per session:
   `model=nova-3, interim_results=true, endpointing=300, smart_format=true,
   diarize=true`. Partials drive the live caption + visualizer energy;
   finals go to the fast-LLM loop.
4. **Utterance events** — `{type: partial|final, text, conf, t0, t1,
   speaker?}` published on an internal bus; the API server re-broadcasts
   over WebSocket to the web UI + overlay.

---

## 4. Fast-LLM "in-between" loop

Every **final** transcript chunk runs this chain on the `fast` role model
(single combined prompt → one JSON object, to stay in one round-trip):

```
transcript ─► EXTRACT {tasks[], ideas[], notes[]} ─► for each task:
  • normalize title (verb-first, <80 chars)
  • infer category  (dev | research | ops | admin | personal | …)
  • dedup key       (fuzzy match vs open tasks → merge or create)
  • priority hints  (urgency/c verbiage, deadlines mentioned)
  • dep hints       ("after X", "needs Y first", build-order common sense)
```

A second, debounced `smart`-role pass (every ~30s or on demand) does the
expensive reasoning: **dependency DAG resolution, re-prioritization, project
clustering, idea tiering**. This two-speed design is what keeps the hot loop
at ~1s while the smart stuff stays correct.

### Worked example (dependency inference)

User rambles: *"set up librechat… oh wait need docker reinstalled first…
and I gotta grab all the api keys and env vars and base urls…"*

Smart pass outputs edges + order:

```
Reinstall Docker ──► Grab API keys + ENV vars + base URLs ──► Set up LibreChat
```

UI renders the chain with `1 → 2 → 3` badges and blocks "start" on a task
whose deps aren't done (soft-block with override).

---

## 5. Task engine (`src/tasks/`)

Pydantic models: `Task(id, title, category, project_id, status, priority,
deps[], estimate_min, elapsed_s, links[], created_from{transcript|overlay|…})`,
`Project(id, name, category, task_ids[], goal)`.

- **Store** — SQLite (`data/tasks.db`) + in-memory pub/sub; every mutation
  emits an event the UIs subscribe to over WebSocket. No refresh buttons.
- **Time tracking** — tasks accrue `elapsed_s` while `in-progress`; the LLM
  estimates `estimate_min` from the title + history, UI shows
  `progress = elapsed / estimate` bars and per-project rollups.
- **Grouping** — `category` inferred inline; `project_id` assigned by the
  smart clustering pass (e.g. *"Research browser automation / Build BrowserUse
  MCP / Test automations"* → project **Browser Automation**).
- **Ranking** — priority score = f(explicit urgency, deps depth, staleness,
  user pins). Main view sorts by it; overrides stick.

---

## 6. Visualizers (the fun part)

### 6a. TUI: sine waves + spectrogram (`src/tui/visualizer.py`)

Built on **Textual** + `numpy`, reading the same mic ring-buffer as the STT
path (zero extra audio plumbing):

- **Top pane — layered sine waves:** 3 phase-offset sine traces driven by
  real RMS energy, rendered with `rich` block characters (`▁▂▃▄▅▆▇█`) in
  gradient colors. Idle = slow breathing wave; speech = dense harmonics.
- **Bottom pane — scrolling spectrogram:** 32-bin FFT magnitudes per frame,
  scrolled right→left as a heat-mapped block matrix (deep purple → cyan →
  hot yellow). Peak-hold markers on the loudest bin.
- **Side rail — live caption:** Deepgram partials stream here; finals flash
  green and spawn task cards below.

Run: `python -m src.tui.visualizer` (works with `--demo` sine-gen, no mic).

### 6b. Web: `<VoiceVisualizer/>` React module (`ui/web/src/components/`)

Fast + efficient by construction:

- Single `<canvas>`, single `requestAnimationFrame` loop, DPR capped at 2.
- `AnalyserNode` (FFT 2048) → frequency + time-domain arrays reused
  in-place (no per-frame allocation); component never `setState`s per frame
  (props flow through refs).
- Three composable layers: `<Waveform/>` (mirrored sine ribbons),
  `<Spectrogram/>` (scrolling GPU-cheap 2D heat strip),
  `<Orb/>` (the "AI is listening" glow ring that pulses with RMS).
- Falls back to a procedural demo oscillator when mic permission is denied,
  so the UI never looks dead.
- Consumes the API WebSocket for transcript captions — audio stays local,
  only text crosses the socket.

---

## 7. UI: tabs + the big blocky to-do list

Main web app (`ui/web/`, React + Vite + Tailwind):

| Tab | What it shows |
|---|---|
| **Tasks** (default) | HUGE rounded-3xl cards (min-h 96px, chunky type), grouped by project, sorted by priority rank. Each card: checkbox, title, category pill, `1→2→3` dep badge, time bar (elapsed/estimate), ▶/⏸, `⋮` → **Send to agent…** |
| **Projects** | Tasks grouped by category → project, avg progress, click-through to Tasks |
| **Timeline** | Per-task + per-project time, progress vs goal, today's burn |
| **Ideas** | S/A/B/C/D/F tier columns (see §9), drag between tiers = feedback signal |
| **Graph** | Live knowledge graph: `category → project → task` + dep edges (see §10) |
| **Activity** *(Phase 4)* | Agent sessions, browser tabs, CLI logs, GitHub events — auto-linked to tasks |
| **Settings** | Provider pickers, keys status (masked), toast prefs, dispatch targets |

Design language: dark bg (`#0b0e14`), neon accent per category, 24px radii,
cards pop with a spring animation when voice-created (that's the dopamine).

### Win+Space quick-capture overlay (`ui/overlay/`)

Like Claude Desktop's Cowork launcher: a **global `Win+Space` hotkey** summons
a tiny always-on-top input bar anywhere in Windows:

- Type or hold-to-talk (same Deepgram pipeline, short session).
- `Enter` → transcript/tasks hit the engine instantly; overlay dismisses.
- Implementation: **Tauri** (Rust global-shortcut plugin, tiny footprint) or
  Electron fallback; talks to the same FastAPI backend over localhost.
- Full spec: `docs/WINDOWS_OVERLAY.md`.

---

## 8. Toast nudges (`src/notifications/`)

Background watcher: any task `in-progress` or `open`-and-pinned with no
activity for `FORGOTTEN_TASK_MINUTES` (default 60) fires a Windows toast:

> **Still on this?** — *"Test automations" has been idle 1h 04m.*
> [Keep going] [Snooze 30m] [Done]

Implemented with `win10toast-click` (clickable actions map to API calls).
Cross-platform no-op with console fallback on macOS/Linux.

---

## 9. Idea evaluator: S-tier to F-tier (`src/ideas/tier_evaluator.py`)

A **LangChain** chain on the `smart` model scores every captured idea:

```
idea ─► RESEARCH-ASSISTED SCORING ─► {tier, scores{}, reasoning, next_step}
```

- **Rubric (0–10 each):** novelty, feasibility (for *you*, with your stack),
  leverage/impact, excitement (prosody + word-choice signal from transcript),
  strategic fit (vs current projects/graph).
- **Tiers:** S (≥9 avg + high novelty) · A · B · C · D · F (<3 or
  đạo-dupe of墓... just kidding — dupes of existing ideas auto-merge).
- **Agent flavor:** `TIER_JUDGE` system prompt acts as a blunt talent scout;
  verdicts are one punchy sentence. Re-runs nightly or on-demand as context
  grows; tier changes animate in the Ideas tab.
- User drags between tiers → stored as preference feedback, folded into the
  prompt's few-shot examples over time.

---

## 10. Knowledge graph (Graph tab)

Live `category → project → task` DAG plus `depends-on` edges, rendered with
`react-force-graph-2d` (canvas, handles 1k+ nodes):

- Nodes stream from the same WebSocket events as the task list — the graph
  literally grows as you talk.
- Node size = priority; color = status; edge style solid (dep) vs dashed
  (same-project).
- Click node → focuses the task card (cross-tab deep link).

---

## 11. Router automations: Hermes + Claude Code (`src/dispatch/`)

Flow: **select task(s) → dropdown (Hermes Agent / Claude Code / …) →
`SEND TO PROCESS`** → task flips to `in-progress` with a session link.

- `hermes.py` — spawns the Hermes Agent binary (or POSTs to its endpoint)
  with a generated brief `{goal, context, repo_paths, acceptance}`; parses
  the session id + worktree/log path back into `task.links[]`.
- `claude_code.py` — shells `claude -p "<brief>" --output-format json`,
  inheriting `ANTHROPIC_BASE_URL=https://api.llmgateway.io` so spend routes
  through the gateway; captures session id + touched files.
- Both write back a **result card** on completion (summary + file list +
  "open session" link) and flip the task to `in-review`.

---

## 12. Phase 4 (designed, NOT built): ambient activity tracking

The endgame: everything routes into the tracker so forgotten context
surfaces itself. Each source gets a poller writing normalized
`ActivityEvent{ts, source, actor, summary, refs{files,urls,branch}}` rows;
a **`cheap`-role loop model** (`qwen3.8-flash`, pennies/M tokens) clusters
events → tasks every N minutes. It *must* be the cheapest model because it
runs forever inside loops.

| Source | How (planned) |
|---|---|
| Agent sessions | Watch Hermes/Claude Code session dirs + JSONL logs |
| Chat UIs | LibreChat/ChatUI export APIs or local DB tail |
| Open browser tabs | Extension → `POST /api/activity/tab` (title/url/fav) |
| Internet history | Opt-in local history-file reader (Chrome/Edge SQLite, locked-copy) |
| CLI logs | `PROMPT_COMMAND`/PSReadLine hook → `POST /api/activity/cmd` (allowlist, secrets redacted) |
| Live activity | Active-window poller (title/process, 5s cadence, all local) |
| **GitHub** | Webhooks + poll: pushes/PRs/issues → auto-link branches (`feat/*`) to tasks; commit messages mentioning `#task-id` close the loop |

Privacy rules baked in from day one: all collectors are **opt-in per source**,
run locally, redact secrets before any LLM call, and the raw store never
leaves the machine unless the user points the gateway at a cloud model.

---

## 13. Repo map

```
├── setup_wizard.py        # CLI install/config wizard (start here)
├── .env.example           # blank template committed to GitHub
├── .env                   # YOUR keys — gitignored, created by wizard
├── src/
│   ├── config.py          # typed settings loader + validation
│   ├── providers/         # deepgram / cerebras / groq / gateway + router
│   ├── voice/             # mic → VAD → Deepgram streaming pipeline
│   ├── tasks/             # models, sqlite store, deps DAG, ranker
│   ├── ideas/             # LangChain S–F tier evaluator
│   ├── notifications/     # Windows toast nudges
│   ├── dispatch/          # Hermes + Claude Code SEND TO PROCESS
│   ├── tui/               # Textual sine-wave + spectrogram visualizer
│   ├── api/               # FastAPI + WebSocket fan-out
│   └── activity/          # Phase-4 stubs (spec'd, not built)
├── ui/
│   ├── web/               # React app: tasks, ideas, graph, visualizer
│   └── overlay/           # Win+Space Tauri/Electron quick-capture
├── docs/                  # overlay spec, UI mockups, roadmap detail
└── tests/
```

## 14. Quickstart

```bash
python setup_wizard.py        # 1. keys + defaults + .env + DB init
pip install -r requirements.txt
python -m src.tui.visualizer --demo   # 2. see the TUI visualizer
uvicorn src.api.server:app --port 8765  # 3. backend
cd ui/web && npm i && npm run dev       # 4. frontend
```
