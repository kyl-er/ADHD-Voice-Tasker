"""Shared OpenAI-compatible client factory.

Cerebras, Groq, and LLM Gateway all speak the OpenAI chat API, so one
`openai.OpenAI(base_url=..., api_key=...)` client serves all three.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ProviderSpec:
    name: str
    base_url: str
    api_key: str
    fast_model: str
    smart_model: str

    @property
    def configured(self) -> bool:
        return bool(self.api_key)


def get_client(spec: ProviderSpec):
    from openai import OpenAI  # lazy: only needs `openai` + a key at call time

    if not spec.configured:
        raise RuntimeError(f"Provider {spec.name!r} has no API key configured.")
    return OpenAI(base_url=spec.base_url, api_key=spec.api_key)


def chat(client, model: str, messages: list[dict], **kw) -> str:
    """Single chat completion; temperature 0 default for JSON-ish tasks."""
    kw.setdefault("temperature", 0)
    resp = client.chat.completions.create(model=model, messages=messages, **kw)
    return resp.choices[0].message.content or ""
