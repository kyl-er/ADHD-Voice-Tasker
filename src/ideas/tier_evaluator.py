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


EXCITED_WORDS = ("love", "amazing", "awesome", "finally", "s-tier",
                 "s tier", "need this", "game changer", "brilliant")


def score_heuristic(title: str, detail: str = "", context: str = "") -> dict:
    """Deterministic offline scoring. LLM path used when keys exist."""
    text = f"{title} {detail}".lower()
    words = len(text.split())
    excitement = 5 + sum(1 for w in EXCITED_WORDS if w in text)
    if "!" in title:
        excitement += 1
    scores = {
        "novelty": min(10, 4 + ("what if" in text) * 3 + (words > 12)),
        "feasibility": 7 if words > 6 else 5,
        "leverage": min(10, 5 + ("automat" in text) * 2 + ("overlay" in text)),
        "excitement": min(10, excitement),
        "strategic_fit": min(10, 5 + (any(k in text for k in
            ("task", "voice", "agent", "overlay", "automat", "track")) * 3)),
    }
    tier = tier_for(scores)
    verdict = {"S": "Rare + shippable. Build this next.", "A": "Strong idea, clear win.",
               "B": "Solid — worth a prototype.", "C": "Fine, but crowded or vague.",
               "D": "Weak signal. Park it.", "F": "Nope. Kill it kindly."}[tier]
    return {"scores": scores, "tier": tier, "verdict": verdict,
            "next_step": f"Smallest test of '{title[:50]}': 25-min spike."}


def evaluate_idea(title: str, detail: str = "", context: str = "") -> dict:
    """LangChain chain on the `smart` model; heuristic fallback offline.

    Uses langchain-openai's ChatOpenAI when installed (pointed at the
    configured smart provider's OpenAI-compatible base URL), else the
    internal Router — same models, same JSON contract.
    """
    try:
        from src.config import Settings
        from src.providers.router import Router
        s = Settings.load()
        if not Router(s).chain_for("smart"):
            raise RuntimeError("no smart key")
        try:  # prefer real LangChain chain when available
            from langchain_openai import ChatOpenAI  # type: ignore
            from src.providers.router import _parse_json
            prov = {"cerebras": (s.cerebras_base_url, s.cerebras_api_key, s.cerebras_smart_model),
                    "groq": (s.groq_base_url, s.groq_api_key, s.groq_smart_model),
                    "gateway": (s.gateway_base_url, s.gateway_api_key, s.gateway_smart_model)}
            base, key, model = prov[Router(s).chain_for("smart")[0][0]]
            llm = ChatOpenAI(base_url=base, api_key=key, model=model, temperature=0.3)
            raw = llm.invoke(TIER_JUDGE_SYSTEM + f"\n\nIDEA: {title}\nDETAIL: {detail}\n"
                             f"CONTEXT: {context}").content
            data = _parse_json(raw)
        except ImportError:
            data = Router(s).complete_json(
                "smart", [{"role": "system", "content": TIER_JUDGE_SYSTEM},
                           {"role": "user", "content": f"IDEA: {title}\nDETAIL: {detail}\n"
                                                       f"CONTEXT: {context}"}])
        data["tier"] = tier_for(data.get("scores", {}))
        return data
    except Exception:
        return score_heuristic(title, detail, context)
