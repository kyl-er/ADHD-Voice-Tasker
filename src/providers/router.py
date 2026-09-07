"""Fast/smart/cheap LLM router with automatic fallback.

Roles:
  fast  — hot voice loop (extract/categorize/dedup). Default: Cerebras 8B.
  smart — deps DAG, S–F tiers, clustering.        Default: Gateway spark.
  cheap — Phase-4 ambient loops (runs forever).    Always cheapest available.

Usage:
    from src.providers.router import Router
    router = Router.from_settings()
    data = router.complete_json("fast", FAST_EXTRACT_PROMPT + transcript)
"""
from __future__ import annotations

import json
from typing Any

from src.config import Settings
from src.providers.base import ProviderSpec, chat, get_client


class Router:
    def __init__(self, settings: Settings):
        self.s = settings
        self.specs = {
            "cerebras": ProviderSpec("cerebras", settings.cerebras_base_url,
                                     settings.cerebras_api_key, settings.cerebras_fast_model,
                                     settings.cerebras_smart_model),
            "groq": ProviderSpec("groq", settings.groq_base_url, settings.groq_api_key,
                                 settings.groq_fast_model, settings.groq_smart_model),
            "gateway": ProviderSpec("gateway", settings.gateway_base_url,
                                    settings.gateway_api_key, settings.gateway_fast_model,
                                    settings.gateway_smart_model),
        }
        self._clients: dict[str, Any] = {}

    @classmethod
    def from_settings(cls) -> "Router":
        return cls(Settings.load())

    # -- chains ------------------------------------------------------
    def chain_for(self, role: str) -> list[tuple[str, str]]:
        """[(provider, model)] ordered by preference for a role."""
        if role == "fast":
            order = self.s.fast_chain()
            pick = lambda p: self.specs[p].fast_model
        elif role == "smart":
            order = [self.s.smart_llm_provider] + [
                p for p in ("gateway", "cerebras", "groq")
                if p != self.s.smart_llm_provider and self.specs[p].configured]
            pick = lambda p: self.specs[p].smart_model
        elif role == "cheap":  # cheapest-first for infinite background loops
            order = [p for p in ("gateway", "groq", "cerebras")
                     if self.specs[p].configured]
            pick = lambda p: self.specs[p].fast_model
        else:
            raise ValueError(f"unknown role {role!r}")
        return [(p, pick(p)) for p in order if self.specs[p].configured]

    def _client(self, provider: str):
        if provider not in self._clients:
            self._clients[provider] = get_client(self.specs[provider])
        return self._clients[provider]

    # -- calls -------------------------------------------------------
    def complete(self, role: str, messages: list[dict], **kw) -> str:
        errors = []
        for provider, model in self.chain_for(role):
            try:
                return chat(self._client(provider), model, messages, **kw)
            except Exception as e:  # noqa: BLE001 - try next provider
                errors.append(f"{provider}/{model}: {e}")
        raise RuntimeError(f"No LLM available for role={role!r}: {'; '.join(errors)}")

    def complete_json(self, role: str, messages: list[dict], **kw) -> dict:
        """Complete + parse JSON, tolerating ```json fences."""
        kw.setdefault("response_format", {"type": "json_object"})
        last = ""
        try:
            last = self.complete(role, messages, **kw)
            return json.loads(last)
        except Exception:
            text = last.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(text)
