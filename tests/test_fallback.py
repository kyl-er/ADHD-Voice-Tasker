from src.voice.fallback_extract import extract
from src.ideas.tier_evaluator import score_heuristic, tier_for


def test_docker_librechat_chain():
    data = extract("first reinstall docker, then grab all api keys and env vars, "
                   "and finally set up librechat on top of all that")
    assert len(data["tasks"]) == 3
    assert data["tasks"][1]["dep_hints"] == [data["tasks"][0]["title"]]
    assert data["tasks"][2]["dep_hints"] == [data["tasks"][1]["title"]]
    assert data["project"] == "Homelab revival"
    assert data["tasks"][0]["category"] in ("dev", "ops")


def test_browser_group_and_idea():
    data = extract("research browser automation, build the BrowserUse MCP, test it. "
                   "What if the overlay drafted my standup? we should build that!")
    assert data["project"] == "Browser Automation"
    assert len(data["tasks"]) == 3  # comma verb-list chains in order
    assert data["tasks"][2]["dep_hints"] == [data["tasks"][1]["title"]]
    assert len(data["ideas"]) >= 1


def test_junk_clauses_dropped():
    data = extract("and then I can finally set up librechat")
    assert len(data["tasks"]) == 1
    assert data["tasks"][0]["title"] == "Set up librechat"


def test_cross_utterance_chain():
    data = extract("then grab all api keys together",
                   prev_titles=("Reinstall docker",))
    assert data["tasks"][0]["dep_hints"] == ["Reinstall docker"]


def test_done_mentions():
    data = extract("I'm done with the docker reinstall, finally finished it")
    assert data["done_mentions"]


def test_heuristic_tiers():
    s = score_heuristic("What if overlay drafted my standup automatically?")
    assert s["tier"] in ("S", "A", "B", "C", "D", "F")
    assert tier_for({k: 9.5 for k in ("novelty", "feasibility", "leverage",
                                      "excitement", "strategic_fit")}) == "S"
