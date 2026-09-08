import os
from src.config import Settings


def test_missing_keys_reports_issues(monkeypatch):
    for k in ("DEEPGRAM_API_KEY", "CEREBRAS_API_KEY", "GROQ_API_KEY", "LLM_GATEWAY_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    s = Settings.load().validate()
    assert not s.ok
    assert any("DEEPGRAM" in i for i in s.issues)


def test_fast_chain_prefers_configured(monkeypatch):
    monkeypatch.setenv("DEEPGRAM_API_KEY", "x")
    monkeypatch.setenv("GROQ_API_KEY", "x")
    monkeypatch.delenv("CEREBRAS_API_KEY", raising=False)
    monkeypatch.delenv("LLM_GATEWAY_API_KEY", raising=False)
    monkeypatch.setenv("FAST_LLM_PROVIDER", "cerebras")
    s = Settings.load()
    assert s.fast_chain() == ["groq"]


def test_tier_thresholds():
    from src.ideas.tier_evaluator import tier_for
    s = {k: 9.5 for k in ("novelty", "feasibility", "leverage", "excitement", "strategic_fit")}
    assert tier_for(s) == "S"
    assert tier_for({k: 1.0 for k in s}) == "F"


def test_ranker_dep_order():
    from src.tasks.models import Task
    from src.tasks.ranker import rank
    a, b = Task(title="docker"), Task(title="librechat")
    b.deps = [a.id]
    out = rank([b, a])
    assert out[-1].id == b.id and b.dep_order == 2
