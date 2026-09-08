#!/usr/bin/env python3
"""ADHD-Voice-Tasker — interactive setup wizard (stdlib only).

Usage:
    python setup_wizard.py          # full interactive setup
    python setup_wizard.py --check   # validate .env, no prompts (exit 1 if bad)
    python setup_wizard.py --test    # validate + ping each configured provider

Does: writes gitignored `.env`, creates ./data, inits the sqlite DB file,
optionally installs requirements. Safe to re-run (keeps existing values).
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"
sys.path.insert(0, str(ROOT))

from src.config import Settings  # noqa: E402  (stdlib-only module)

BANNER = r"""
    _    ____  _   _ ____    ____  _   _ ___ ____ _____
   / \  |  _ \| | | |  _ \  |  _ \| | | |_ _/ ___| ____|
  / _ \ | | | | |_| | | | | | | | | |_| || |   |  _|
 / ___ \| |_| |  _  | |_| |  |_| | |___ | | |___| |___
/_/   \_\____/|_| |_|____/  |____/ \___/|___\____|_____|
__     ___    ___ ____ _____   _____  _    ____  _  _______ ____
\ \   / / |  |_ _/ ___| ____| |_   _|/ \  / ___|| |/ / ____|  _ \
 \ \ / /| |   | | |   |  _|     | | / _ \ \___ \| ' /|  _| | |_) |
  \ V / | |___| | |___| |___    | |/ ___ \ ___) | . \| |___|  _ <
   \_/  |_____|___\____|_____|  |_/_/   \_\____/|_|\_\_____|_| \_\
"""

GREEN, RED, YELLOW, DIM, BOLD = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m"
RESET = "\033[0m"


def say(msg: str = "") -> None:
    print(msg)


def ok(msg: str) -> None:
    print(f"{GREEN}✓{RESET} {msg}")


def warn(msg: str) -> None:
    print(f"{YELLOW}!{RESET} {msg}")


def err(msg: str) -> None:
    print(f"{RED}✗{RESET} {msg}")


def prompt(label: str, default: str = "", secret: bool = False) -> str:
    hint = ""
    if default:
        hint = f" {DIM}[{('••••••••' + default[-4:]) if secret and len(default) > 4 else default}]{RESET}"
    try:
        raw = input(f"  {BOLD}{label}{RESET}{hint}: ").strip()
    except (EOFError, KeyboardInterrupt):
        say()
        raise SystemExit(1)
    return raw or default


def prompt_choice(label: str, options: list[str], default: str) -> str:
    say(f"  {BOLD}{label}{RESET}")
    for i, o in enumerate(options, 1):
        star = f" {GREEN}← current{RESET}" if o == default else ""
        print(f"    {i}) {o}{star}")
    try:
        raw = input(f"  Pick [1-{len(options)}] (Enter = {default}): ").strip()
    except (EOFError, KeyboardInterrupt):
        say()
        raise SystemExit(1)
    if not raw:
        return default
    if raw.isdigit() and 1 <= int(raw) <= len(options):
        return options[int(raw) - 1]
    if raw in options:
        return raw
    warn(f"Unknown choice {raw!r}, keeping {default}.")
    return default


def mask(v: str) -> str:
    return f"••••{v[-4:]}" if len(v) > 4 else ("(set)" if v else "(empty)")


# ---------------------------------------------------------------- providers

def ping_openai_compatible(base_url: str, api_key: str, timeout: int = 12) -> tuple[bool, str]:
    """GET {base}/models — works for Cerebras, Groq, and LLM Gateway."""
    url = base_url.rstrip("/") + "/models"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return (r.status == 200, f"HTTP {r.status}")
    except Exception as e:  # noqa: BLE001 - wizard, show whatever happened
        return False, str(e)[:100]


def ping_deepgram(api_key: str, timeout: int = 12) -> tuple[bool, str]:
    req = urllib.request.Request(
        "https://api.deepgram.com/v1/projects",
        headers={"Authorization": f"Token {api_key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return (r.status == 200, f"HTTP {r.status}")
    except Exception as e:  # noqa: BLE001
        return False, str(e)[:100]


# ---------------------------------------------------------------- steps

def step_voice(env: dict) -> None:
    say(f"\n{BOLD}── 1/5 · Voice: Deepgram ──{RESET}")
    say("  Get a key: https://console.deepgram.com  ($200 free credit, no card)")
    env["DEEPGRAM_API_KEY"] = prompt("DEEPGRAM_API_KEY", env.get("DEEPGRAM_API_KEY", ""), secret=True)
    env["DEEPGRAM_MODEL"] = prompt("Model (nova-3 recommended, or flux-general-en)", env.get("DEEPGRAM_MODEL", "nova-3"))
    env["DEEPGRAM_LANGUAGE"] = prompt("Language code", env.get("DEEPGRAM_LANGUAGE", "en"))


def step_fast_llm(env: dict) -> None:
    say(f"\n{BOLD}── 2/5 · Fast LLM loop (need ≥1) ──{RESET}")
    say("  Cerebras = max tok/s (bulk) · Groq = min latency (realtime) · Gateway = 200+ models, 1 key")
    c = prompt("CEREBRAS_API_KEY  (https://cloud.cerebras.ai)", env.get("CEREBRAS_API_KEY", ""), secret=True)
    g = prompt("GROQ_API_KEY      (https://console.groq.com)", env.get("GROQ_API_KEY", ""), secret=True)
    w = prompt("LLM_GATEWAY_API_KEY (https://llmgateway.io, llmgtwy_…)", env.get("LLM_GATEWAY_API_KEY", ""), secret=True)
    env["CEREBRAS_API_KEY"], env["GROQ_API_KEY"], env["LLM_GATEWAY_API_KEY"] = c, g, w
    if not (c or g or w):
        warn("No fast-LLM key entered — the voice loop can't extract tasks without one.")
        warn("You can re-run the wizard later; continuing with placeholders.")


def step_models(env: dict) -> None:
    say(f"\n{BOLD}── 3/5 · Models + base URLs (Enter = keep default) ──{RESET}")
    defaults = {
        "CEREBRAS_BASE_URL": "https://api.cerebras.ai/v1",
        "CEREBRAS_FAST_MODEL": "llama3.1-8b",
        "CEREBRAS_SMART_MODEL": "llama-3.3-70b",
        "GROQ_BASE_URL": "https://api.groq.com/openai/v1",
        "GROQ_FAST_MODEL": "llama-3.1-8b-instant",
        "GROQ_SMART_MODEL": "llama-3.3-70b-versatile",
        "LLM_GATEWAY_BASE_URL": "https://api.llmgateway.io/v1",
        "LLM_GATEWAY_FAST_MODEL": "qwen3.8-flash",
        "LLM_GATEWAY_SMART_MODEL": "muse-spark-1.3",
    }
    for k, d in defaults.items():
        env[k] = prompt(k, env.get(k, d))
    say()
    env["FAST_LLM_PROVIDER"] = prompt_choice(
        "Hot-loop provider (task extract / categorize / dedup)?",
        ["cerebras", "groq", "gateway"], env.get("FAST_LLM_PROVIDER", "cerebras"))
    env["SMART_LLM_PROVIDER"] = prompt_choice(
        "Smart provider (dependencies / S–F tiers / clustering)?",
        ["gateway", "cerebras", "groq"], env.get("SMART_LLM_PROVIDER", "gateway"))
    env["VOICE_PROVIDER"] = "deepgram"


def step_app(env: dict) -> None:
    say(f"\n{BOLD}── 4/5 · App + nudges + dispatch ──{RESET}")
    env["DATABASE_URL"] = prompt("DATABASE_URL", env.get("DATABASE_URL", "sqlite:///./data/tasks.db"))
    env["API_PORT"] = prompt("API_PORT", env.get("API_PORT", "8765"))
    env["API_HOST"] = prompt("API_HOST", env.get("API_HOST", "0.0.0.0"))
    env["TOAST_ENABLED"] = prompt("TOAST_ENABLED (true/false)", env.get("TOAST_ENABLED", "true"))
    env["FORGOTTEN_TASK_MINUTES"] = prompt("FORGOTTEN_TASK_MINUTES", env.get("FORGOTTEN_TASK_MINUTES", "60"))
    env["HERMES_AGENT_PATH"] = prompt("HERMES_AGENT_PATH (blank = skip)", env.get("HERMES_AGENT_PATH", ""))
    env["HERMES_AGENT_ENDPOINT"] = prompt("HERMES_AGENT_ENDPOINT (blank = skip)", env.get("HERMES_AGENT_ENDPOINT", ""))
    env["CLAUDE_CODE_PATH"] = prompt("CLAUDE_CODE_PATH", env.get("CLAUDE_CODE_PATH", "claude"))


def write_env(env: dict) -> None:
    keys = ["DEEPGRAM_API_KEY", "DEEPGRAM_MODEL", "DEEPGRAM_LANGUAGE",
            "CEREBRAS_API_KEY", "CEREBRAS_BASE_URL", "CEREBRAS_FAST_MODEL", "CEREBRAS_SMART_MODEL",
            "GROQ_API_KEY", "GROQ_BASE_URL", "GROQ_FAST_MODEL", "GROQ_SMART_MODEL",
            "LLM_GATEWAY_API_KEY", "LLM_GATEWAY_BASE_URL", "LLM_GATEWAY_FAST_MODEL", "LLM_GATEWAY_SMART_MODEL",
            "VOICE_PROVIDER", "FAST_LLM_PROVIDER", "SMART_LLM_PROVIDER",
            "DATABASE_URL", "API_HOST", "API_PORT",
            "TOAST_ENABLED", "FORGOTTEN_TASK_MINUTES",
            "HERMES_AGENT_PATH", "HERMES_AGENT_ENDPOINT", "CLAUDE_CODE_PATH"]
    lines = ["# Generated by setup_wizard.py — DO NOT COMMIT (gitignored).",
             f"# Regenerate anytime: python {ENV_PATH.name and 'setup_wizard.py'}", ""]
    for k in keys:
        lines.append(f"{k}={env.get(k, '')}")
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ok(f"Wrote {ENV_PATH} (gitignored — your keys stay local)")


def init_data_dir() -> None:
    say(f"\n{BOLD}── 5/5 · Local data ──{RESET}")
    data = ROOT / "data"
    data.mkdir(exist_ok=True)
    db = data / "tasks.db"
    if not db.exists():
        sqlite3.connect(db).close()
        ok(f"Created {db}")
    else:
        ok(f"Found {db} (kept)")
    (data / ".gitkeep").touch(exist_ok=True)


def maybe_install_deps() -> None:
    try:
        raw = input(f"\n  Install python deps now? ({DIM}pip install -r requirements.txt{RESET}) [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return
    if raw not in ("y", "yes"):
        say(f"  {DIM}Skipped — run: pip install -r requirements.txt{RESET}")
        return
    r = subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    ok("Dependencies installed.") if r.returncode == 0 else err("pip failed — see output above.")


def show_status(settings: Settings) -> bool:
    say(f"\n{BOLD}── Config status ──{RESET}")
    for p in settings.provider_status():
        icon = ok if p.configured else warn
        icon(f"{p.name:10s} {mask(getattr(settings, 'gateway_api_key' if p.name=='gateway' else p.name+'_api_key', ''))}  {DIM}{p.detail}{RESET}")
    say(f"  {DIM}fast chain: {' → '.join(settings.fast_chain()) or '(none)'} · "
        f"smart: {settings.smart_llm_provider} · db: {settings.database_url}{RESET}")
    if settings.issues:
        for i in settings.issues:
            err(i)
        return False
    ok("Config valid — you're good to go.")
    return True


def run_tests(settings: Settings) -> None:
    say(f"\n{BOLD}── Provider smoke tests ──{RESET}")
    if settings.deepgram_api_key:
        good, msg = ping_deepgram(settings.deepgram_api_key)
        (ok if good else err)(f"deepgram: {msg}")
    else:
        warn("deepgram: skipped (no key)")
    for name in ("cerebras", "groq", "gateway"):
        key = getattr(settings, f"{name}_api_key")
        base = getattr(settings, f"{name}_base_url")
        if not key:
            warn(f"{name}: skipped (no key)")
            continue
        good, msg = ping_openai_compatible(base, key)
        (ok if good else err)(f"{name} ({base}): {msg}")


def load_existing_env() -> dict:
    env: dict = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def interactive() -> None:
    print(BANNER)
    say(f"{BOLD}Welcome to ADHD-Voice-Tasker setup.{RESET} Existing values are kept — Enter skips.")
    if sys.version_info < (3, 10):
        err(f"Python {sys.version} found — 3.10+ required.")
        raise SystemExit(1)
    env = load_existing_env()
    if env:
        ok(f"Loaded {len(env)} existing value(s) from .env")
    step_voice(env)
    step_fast_llm(env)
    step_models(env)
    step_app(env)
    write_env(env)
    for k, v in env.items():
        os.environ[k] = v
    settings = Settings.load()
    init_data_dir()
    good = show_status(settings)
    if any([settings.deepgram_api_key, settings.cerebras_api_key,
            settings.groq_api_key, settings.gateway_api_key]):
        try:
            raw = input(f"\n  Smoke-test providers now? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            raw = "n"
        if raw in ("y", "yes"):
            run_tests(settings)
    maybe_install_deps()
    say(f"\n{BOLD}Next steps:{RESET}")
    say("  1. pip install -r requirements.txt")
    say("  2. python -m src.tui.visualizer --demo     # TUI sine/spectrogram demo")
    say("  3. uvicorn src.api.server:app --port 8765  # backend")
    if not good:
        say(f"  {DIM}Re-run `python setup_wizard.py` anytime to fix the issues above.{RESET}")


def main() -> None:
    ap = argparse.ArgumentParser(description="ADHD-Voice-Tasker setup wizard")
    ap.add_argument("--check", action="store_true", help="validate .env and exit")
    ap.add_argument("--test", action="store_true", help="validate + ping providers")
    args = ap.parse_args()
    if args.check or args.test:
        if not ENV_PATH.exists():
            err("No .env found — run `python setup_wizard.py` first.")
            raise SystemExit(1)
        settings = Settings.load()
        good = show_status(settings)
        if args.test:
            run_tests(settings)
        raise SystemExit(0 if good else 1)
    interactive()


if __name__ == "__main__":
    main()
