# Roadmap

## Phase 0 — Foundation ✅ (this scaffold)
- [x] Architecture design
- [x] `.env.example` + `.gitignore` + local `.env`
- [x] `setup_wizard.py` CLI installer
- [x] Typed config loader (`src/config.py`)
- [x] Provider clients + fast/smart/cheap router
- [x] Task models + SQLite store + dep DAG + ranker
- [x] TUI visualizer stub, React visualizer module, overlay spec
- [x] Dispatch + toast + idea-tier stubs

## Phase 1 — Talk → tasks ✅ (live)
- [x] Voice pipeline end-to-end (Deepgram module + simulator; live mic needs key+hardware)
- [x] Fast-loop extraction (LLM w/ JSON repair + salvage, heuristic fallback, offline)
- [x] FastAPI server + WebSocket fan-out (serves UI at `/`, 10/10 tests)
- [x] Web Tasks tab with big blocky cards (live API-driven, WS updates)
- [x] TUI visualizer live-mic mode (sounddevice+FFT, demo fallback)
- [ ] Polish queue: idea dedup by meaning, live Deepgram socket test w/ real key

## Phase 2 — Wow UI
- [ ] Timeline tab, Ideas S–F tab, Graph tab
- [ ] Win+Space overlay (Tauri)
- [ ] Toast nudges watcher

## Phase 3 — Agents
- [ ] Hermes + Claude Code dispatch, session links, result cards
- [ ] Smart-pass dependency resolver + nightly re-rank

## Phase 4 — Ambient tracking (designed, not started)
- [ ] Activity collectors (agent sessions, tabs, history, CLI, GitHub)
- [ ] Cheap-loop clustering worker
- [ ] Privacy dashboard (per-source toggles, redaction preview)
