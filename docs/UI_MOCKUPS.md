# UI mockups (ASCII) — every tab

## Tasks tab (default) — HUGE blocky rounded cards
```
┌─ Tasks ── Timeline ── Ideas ── Graph ── Activity ── Settings ─────────────┐
│ 🎙️ Listening… "…so after docker I need the api keys then librechat"       │
│ ╭────────────────────────────────────────────────────────────────────────╮ │
│ │ ☐  Reinstall Docker                              [ops]  ①   ▶  12/20m │ │  ← chain pos
│ │    ▓▓▓▓▓▓░░░░░░ 60%                                    ⋮ Send to agent │ │
│ ╰────────────────────────────────────────────────────────────────────────╯ │
│ ╭────────────────────────────────────────────────────────────────────────╮ │
│ │ ☐  Grab API keys + ENV vars + base URLs          [ops]  ②   ▶   0/15m │ │
│ │    ░░░░░░░░░░░░░  0%  ⛓ waits on: Reinstall Docker     ⋮ Send to agent │ │
│ ╰────────────────────────────────────────────────────────────────────────╯ │
│ ╭────────────────────────────────────────────────────────────────────────╮ │
│ │ ☐  Set up LibreChat                              [dev]  ③   ▶   0/45m │ │
│ │    ░░░░░░░░░░░░░  0%  ⛓ waits on: API keys…            ⋮ Send to agent │ │
│ ╰────────────────────────────────────────────────────────────────────────╯ │
│  Project: Homelab revival ▾   [+ New]   Sort: Priority ✦                   │
└────────────────────────────────────────────────────────────────────────────┘
```

## Ideas tab — S→F tiers
```
┌─ … ── Ideas ── … ─────────────────────────────────────────────────────────┐
│  S ★            A               B               C          D    F          │
│ ╭────────╮   ╭────────╮     ╭────────╮     ╭────────╮                      │
│ │Voice   │   │Browser │     │Tab     │     │Meal    │    (empty = good)    │
│ │tasker  │   │Use MCP │     │janitor │     │planner │                      │
│ │9.4 ★ S │   │8.1 · A │     │6.2 · B │     │4.8 · C │                      │
│ ╰────────╯   ╰────────╯     ╰────────╯     ╰────────╯                      │
│ Verdict: "Rare + shippable with your stack."  Next: scaffold the STT loop │
└────────────────────────────────────────────────────────────────────────────┘
```

## Graph tab — category → project → task
```
   (dev)─── Browser Automation ──┬── Research browser automation ✓
                                 ├── Build BrowserUse MCP ──▶ Test automations
   (ops)─── Homelab revival ─────┴── Docker ──▶ API keys ──▶ LibreChat
   legend: ● size=priority  color=status  ─▶ depends-on  ── same-project
```

## TUI (terminal) — sine + spectrogram + captions
```
 ═══════════════════════════════════════════════════════════════
   ADHD-VOICE-TASKER · TUI                          ● LIVE  41ms
 ═══════════════════════════════════════════════════════════════
   ▁▂▃▄▅▆▇█▇▆▅▄▃▂▁▁▂▃▄▅▆▇█▇▆▅▄▃  (cyan ribbon, energy-driven)
   ▂▃▄▅▆▇█▇▆▅▄▃▂▁▁▂▃▄▅▆▇█▇▆▅▄▃▂  (violet, phase-offset)
   ▃▄▅▆▇█▇▆▅▄▃▂▁▁▂▃▄▅▆▇█▇▆▅▄▃▂▁  (pink, harmonic)
 ───────────────────────────────────────  SPECTROGRAM ─────────
   @%#*+::..   << scrolling heat (purple→cyan→yellow), peak-hold ▲
 ──────────────────────────────────────────────────────────────
   > …after docker I need the api keys…          [+ Task: Reinstall Docker]
```
