# ADHD-Voice-Tasker 🎙️✅

Talk out loud. Get organized. A voice-first task tracker for brains that
have 47 tabs open — literally and mentally.

- 🎤 **Deepgram streaming STT** (Nova-3) turns rambling into transcripts live
- ⚡ **Cerebras / Groq / LLM Gateway (DevPass)** fast-model loop extracts
  tasks, categories, priorities, and dependencies in ~1s
- 🌊 **Sine-wave + spectrogram TUI** plus a buttery `<VoiceVisualizer/>`
  React module
- 🧱 **Huge blocky to-do cards**, tabs for Timeline / Ideas (S–F tiers) /
  Knowledge Graph
- ⌨️ **Win+Space overlay** for quick capture anywhere (like Cowork launcher)
- 🤖 **Send to agent**: Hermes Agent or Claude Code with one click
- 🔔 **Windows toasts** nudge you about forgotten tasks

## Start here

```bash
python setup_wizard.py        # interactive setup: keys, defaults, .env, DB
```

The wizard writes a gitignored `.env` (template: `.env.example`), verifies
at least one STT + one LLM key is present, and optionally smoke-tests each
provider. Re-run anytime; existing values are kept as defaults.

| Command | What it does |
|---|---|
| `python setup_wizard.py` | Full interactive setup |
| `python setup_wizard.py --check` | Validate current `.env`, no prompts |
| `python setup_wizard.py --test` | Validate + ping each configured provider |

## Docs

- **`ARCHITECTURE.md`** — full system design (pipeline, models, UI, agents)
- **`ROADMAP.md`** — phased build plan
- **`docs/WINDOWS_OVERLAY.md`** — Win+Space overlay spec
- **`docs/UI_MOCKUPS.md`** — ASCII mockups of every tab

## Run (after setup)

```bash
pip install -r requirements.txt
python -m src.tui.visualizer --demo    # TUI visualizer, no mic needed
uvicorn src.api.server:app --port 8765 # backend (http://localhost:8765)
cd ui/web && npm i && npm run dev      # frontend
```

## Keys you'll need

| Key | Where | Required? |
|---|---|---|
| `DEEPGRAM_API_KEY` | https://console.deepgram.com ($200 free) | Yes (voice) |
| `CEREBRAS_API_KEY` | https://cloud.cerebras.ai | One fast LLM |
| `GROQ_API_KEY` | https://console.groq.com | One fast LLM |
| `LLM_GATEWAY_API_KEY` | https://llmgateway.io (`llmgtwy_…`) | One fast LLM |
