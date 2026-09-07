"""Typed settings loader. Stdlib-only so the wizard works pre-install.

Reads `.env` (via python-dotenv if available, else a tiny built-in parser),
validates with dataclasses, and exposes provider health checks.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"


def _load_dotenv(path: Path = ENV_PATH) -> None:
    """Minimal .env loader used when python-dotenv isn't installed yet."""
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(path)
        return
    except ImportError:
        pass
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip("'\""))


@dataclass
class ProviderStatus:
    name: str
    configured: bool
    detail: str = ""


@dataclass
class Settings:
    deepgram_api_key: str = ""
    deepgram_model: str = "nova-3"
    deepgram_language: str = "en"

    cerebras_api_key: str = ""
    cerebras_base_url: str = "https://api.cerebras.ai/v1"
    cerebras_fast_model: str = "llama3.1-8b"
    cerebras_smart_model: str = "llama-3.3-70b"

    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_fast_model: str = "llama-3.1-8b-instant"
    groq_smart_model: str = "llama-3.3-70b-versatile"

    gateway_api_key: str = ""
    gateway_base_url: str = "https://api.llmgateway.io/v1"
    gateway_fast_model: str = "qwen3.8-flash"
    gateway_smart_model: str = "muse-spark-1.3"

    voice_provider: str = "deepgram"
    fast_llm_provider: str = "cerebras"
    smart_llm_provider: str = "gateway"

    database_url: str = "sqlite:///./data/tasks.db"
    api_host: str = "0.0.0.0"
    api_port: int = 8765

    toast_enabled: bool = True
    forgotten_task_minutes: int = 60

    hermes_agent_path: str = ""
    hermes_agent_endpoint: str = ""
    claude_code_path: str = "claude"

    issues: list = field(default_factory=list)

    @classmethod
    def load(cls) -> "Settings":
        _load_dotenv()
        g = os.environ.get
        s = cls(
            deepgram_api_key=g("DEEPGRAM_API_KEY", ""),
            deepgram_model=g("DEEPGRAM_MODEL", "nova-3"),
            deepgram_language=g("DEEPGRAM_LANGUAGE", "en"),
            cerebras_api_key=g("CEREBRAS_API_KEY", ""),
            cerebras_base_url=g("CEREBRAS_BASE_URL", "https://api.cerebras.ai/v1"),
            cerebras_fast_model=g("CEREBRAS_FAST_MODEL", "llama3.1-8b"),
            cerebras_smart_model=g("CEREBRAS_SMART_MODEL", "llama-3.3-70b"),
            groq_api_key=g("GROQ_API_KEY", ""),
            groq_base_url=g("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
            groq_fast_model=g("GROQ_FAST_MODEL", "llama-3.1-8b-instant"),
            groq_smart_model=g("GROQ_SMART_MODEL", "llama-3.3-70b-versatile"),
            gateway_api_key=g("LLM_GATEWAY_API_KEY", ""),
            gateway_base_url=g("LLM_GATEWAY_BASE_URL", "https://api.llmgateway.io/v1"),
            gateway_fast_model=g("LLM_GATEWAY_FAST_MODEL", "qwen3.8-flash"),
            gateway_smart_model=g("LLM_GATEWAY_SMART_MODEL", "muse-spark-1.3"),
            voice_provider=g("VOICE_PROVIDER", "deepgram"),
            fast_llm_provider=g("FAST_LLM_PROVIDER", "cerebras"),
            smart_llm_provider=g("SMART_LLM_PROVIDER", "gateway"),
            database_url=g("DATABASE_URL", "sqlite:///./data/tasks.db"),
            api_host=g("API_HOST", "0.0.0.0"),
            api_port=int(g("API_PORT", "8765")),
            toast_enabled=g("TOAST_ENABLED", "true").lower() in ("1", "true", "yes"),
            forgotten_task_minutes=int(g("FORGOTTEN_TASK_MINUTES", "60")),
            hermes_agent_path=g("HERMES_AGENT_PATH", ""),
            hermes_agent_endpoint=g("HERMES_AGENT_ENDPOINT", ""),
            claude_code_path=g("CLAUDE_CODE_PATH", "claude"),
        )
        return s.validate()

    def validate(self) -> "Settings":
        self.issues = []
        if not self.deepgram_api_key:
            self.issues.append("DEEPGRAM_API_KEY is missing (voice won't work).")
        fast_keys = {
            "cerebras": self.cerebras_api_key,
            "groq": self.groq_api_key,
            "gateway": self.gateway_api_key,
        }
        if not any(fast_keys.values()):
            self.issues.append(
                "No fast-LLM key set — add at least one of CEREBRAS_API_KEY, "
                "GROQ_API_KEY, LLM_GATEWAY_API_KEY."
            )
        if self.fast_llm_provider not in fast_keys:
            self.issues.append(f"FAST_LLM_PROVIDER={self.fast_llm_provider!r} unknown.")
        elif not fast_keys[self.fast_llm_provider]:
            self.issues.append(
                f"FAST_LLM_PROVIDER={self.fast_llm_provider} has no API key set."
            )
        if self.smart_llm_provider not in ("cerebras", "groq", "gateway"):
            self.issues.append(f"SMART_LLM_PROVIDER={self.smart_llm_provider!r} unknown.")
        return self

    @property
    def ok(self) -> bool:
        return not self.issues

    def provider_status(self) -> list[ProviderStatus]:
        return [
            ProviderStatus("deepgram", bool(self.deepgram_api_key), self.deepgram_model),
            ProviderStatus(
                "cerebras", bool(self.cerebras_api_key), self.cerebras_fast_model
            ),
            ProviderStatus("groq", bool(self.groq_api_key), self.groq_fast_model),
            ProviderStatus(
                "gateway", bool(self.gateway_api_key), self.gateway_fast_model
            ),
        ]

    def fast_chain(self) -> list[str]:
        """Ordered provider fallback chain for the hot loop."""
        chain = [self.fast_llm_provider]
        for p in ("cerebras", "groq", "gateway"):
            if p not in chain:
                chain.append(p)
        keys = {
            "cerebras": self.cerebras_api_key,
            "groq": self.groq_api_key,
            "gateway": self.gateway_api_key,
        }
        return [p for p in chain if keys[p]]


if __name__ == "__main__":
    s = Settings.load()
    print(f"config ok: {s.ok}")
    for i in s.issues:
        print(f"  ! {i}", file=sys.stderr)
    for p in s.provider_status():
        mark = "✓" if p.configured else "·"
        print(f"  [{mark}] {p.name}: {p.detail or '—'}")
