"""Idea evaluator — LangChain chain that ranks ideas S-tier → F-tier.

Rubric (0–10): novelty, feasibility, leverage, excitement, strategic_fit.
avg ≥9 + novelty ≥9 → S · ≥7.5 A · ≥6 B · ≥4.5 C · ≥3 D · else F.
Dupes of existing ideas merge instead of ranking (returns tier "DUPE").
"""
from __future__ import annotations

TIER_JUDGE_SYSTEM = """You are TIER_JUDGE, a blunt talent scout for a builder's idea inbox.
Score the idea 0-10 on: novelty, feasibility (for THIS builder's stack),
leverage/impact, excitement (infer from wording + energy), strategic_fit
(vs their current projects, provided as context).

Return JSON ONLY: {"scores": {…}, "tier": "S|A|B|C|D|F",
"verdict": "one punchy sentence", "next_step": "smallest concrete action"}.
Be harsh: most ideas are C. S-tier means genuinely rare + shippable."""

TIERS = ["S", "A", "B", "C", "D", "F"]


def tier_for(scores: dict[str, float]) -> str:
    vals = [scores.get(k, 0) for k in
            ("novelty", "feasibility", "leverage", "excitement", "strategic_fit")]
    avg = sum(vals) / len(vals)
    if avg >= 9 and scores.get("novelty", 0) >= 9:
        return "S"
    if avg >= 7.5:
        return "A"
    if avg >= 6:
        return "B"
    if avg >= 4.5:
        return "C"
    if avg >= 3:
        return "D"
    return "F"


def evaluate_idea(title: str, detail: str = "", context: str = "") -> dict:
    """Run the LangChain chain on the `smart` model. Phase-1 wiring:

        from langchain_openai import ChatOpenAI
        from src.config import Settings
        s = Settings.load()  # gateway base URL + key → ChatOpenAI(...)
        llm = ChatOpenAI(base_url=s.gateway_base_url, api_key=s.gateway_api_key,
                         model=s.gateway_smart_model, temperature=0.3)
        return json.loads((SYS + HUMAN).invoke(...)...)
    """
    raise NotImplementedError("Phase 1: wire LangChain ChatOpenAI via gateway")
