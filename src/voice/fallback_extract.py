"""Offline heuristic extractor — zero keys, zero latency, deterministic.

Used automatically when no fast-LLM key is configured (and in tests/CI).
Same contract as the LLM prompt: tasks / ideas / notes / done_mentions,
plus a suggested project.
"""
from __future__ import annotations

import re

FILLER_PREFIX = re.compile(
    r"^(okay so|ok so|so|oh also|oh|well|like|please|hey|um|uh|right)\b[\s,]*", re.I)
SEQ_STRIP = re.compile(r"^(first|then|and then|next|finally|after that)\b[\s,]*", re.I)
SPLIT = re.compile(r"[.;…?!]+|\band then\b|\bthen\b|\band finally\b|\bfinally\b"
                   r"|\balso\b|\bplus\b|\bafter that\b|\bnext,"
                   r"|,\s*(?=(?:build|test|setup|set up|create|research|grab|install"
                   r"|reinstall|run|write|deploy|make|configure|fix)\b)", re.I)
SEQ_CUES = ("first", "then", "after", "before", "finally", "next", "step")
DONE_CUES = ("done with", "finished", "completed", "shipped", "knocked out", "did the")
IDEA_CUES = ("what if", "idea", "we should", "wouldn't it be", "could we",
             "s-tier", "s tier", "startup", "would be cool", "should build")
URGENT_WORDS = ("urgent", "asap", "now", "today", "deadline", "blocking", "must", "important")

CAT_KEYWORDS = {
    "dev": ("build", "setup", "set up", "install", "code", "server", "mcp", "app",
            "api", "deploy", "librechat", "docker", "repo", "branch", "debug",
            "test", "script", "automat"),
    "research": ("research", "best way", "compare", "look into", "figure out",
                 "investigate", "read up", "learn", "find out"),
    "ops": ("reinstall", "keys", "env", "base url", "backup", "update",
            "restart", "password", "account", "billing"),
    "admin": ("email", "invoice", "schedule", "meeting", "call", "book", "pay", "form"),
    "personal": ("gym", "grocer", "cook", "clean", "walk", "sleep", "doctor", "dentist"),
}
PROJECT_KEYWORDS = {
    "Homelab revival": ("docker", "librechat", "homelab", "server", "self-host",
                        "api keys", "env vars", "base url"),
    "Browser Automation": ("browser", "mcp", "automation", "scrap", "playwright", "selenium"),
}
ESTIMATES = {"dev": 45, "research": 40, "ops": 20, "admin": 15,
             "personal": 30, "general": 25}


MODAL_STRIP = re.compile(r"^(i|we|you)\s+(can|will|would|could|just)\s+", re.I)
NEED_STRIP = re.compile(r"\bi('ve|ve)?\s+(need to|gotta|have to|got to)\s+", re.I)
NEED_PREFIX = re.compile(r"^(i need to|i gotta|need to|gotta|have to|got to|i'm going to|going to|gonna)\s+", re.I)
SEQ_STARTER = re.compile(r"^(and\s+|ok\s*,?\s*)?(then|after that|next|finally)\b", re.I)
VERB_LIST = re.compile(r",\s*(?:build|test|setup|set up|create|research|grab|install"
                       r"|reinstall|run|write|deploy|make|configure|fix)\b", re.I)
LEAD_PUNCT = re.compile(r"^[\s,—–\-:;\"'()]+")
JUNK = re.compile(r"^(i|we|you|it|this|that)\s+(can|will|would|could|should|is|are|was|do)\s*$", re.I)


def _clean(clause: str) -> str:
    c = clause.strip().strip(",")
    c = re.sub(r",?\s*it'?s (totally |really |just |so ).*$", "", c, flags=re.I)
    for _ in range(2):  # prefix stripping converges (e.g. "and then I can …")
        c = LEAD_PUNCT.sub("", c)
        c = FILLER_PREFIX.sub("", c).strip()
        c = SEQ_STRIP.sub("", c).strip()
        c = MODAL_STRIP.sub("", c).strip()
        c = NEED_STRIP.sub("", c).strip()
        c = NEED_PREFIX.sub("", c).strip()
    c = LEAD_PUNCT.sub("", c).strip()
    if not c or JUNK.match(c):
        return ""
    return (c[0].upper() + c[1:]).rstrip(".")


def split_clauses(text: str) -> list[str]:
    return [c.strip() for c in SPLIT.split(text) if c.strip()]


def categorize(text: str) -> str:
    low = text.lower()
    best, hits = "general", 0
    for cat, words in CAT_KEYWORDS.items():
        n = sum(1 for w in words if w in low)
        if n > hits:
            best, hits = cat, n
    return best


def suggest_project(text: str) -> str | None:
    low = text.lower()
    best, hits = None, 0
    for proj, words in PROJECT_KEYWORDS.items():
        n = sum(1 for w in words if w in low)
        if n > hits:
            best, hits = proj, n
    return best


def urgency_of(text: str) -> float:
    low = text.lower()
    n = sum(1 for w in URGENT_WORDS if w in low)
    if re.search(r"\b(finally|must|need)\b", low):
        n += 1
    return min(1.0, 0.3 + 0.2 * n)


def extract(text: str, prev_titles: tuple[str, ...] = ()) -> dict:
    """Heuristic extraction. Returns the same shape as the LLM fast loop.

    prev_titles: recent open-task titles for cross-utterance chaining —
    an utterance starting with then/next/finally continues that thread.
    """
    tasks, ideas, notes, done = [], [], [], []
    sequential = (any(c in text.lower() for c in SEQ_CUES)
                  or bool(VERB_LIST.search(text)))
    continues_thread = bool(SEQ_STARTER.search(text.strip()))
    for raw in split_clauses(text):
        low = raw.lower()
        if any(c in low for c in DONE_CUES):
            done.append(_clean(re.sub("|".join(DONE_CUES), "", low)).strip() or raw.strip())
            continue
        if any(c in low for c in IDEA_CUES):
            title = _clean(raw)
            if len(title.split()) >= 2:
                ideas.append({"title": title[:90], "detail": text[:240]})
            continue
        title = _clean(raw)
        if len(title.split()) < 2:
            if title:
                notes.append(title)
            continue
        tasks.append({"title": title[:90], "category": categorize(title),
                      "urgency": round(urgency_of(title), 2), "dep_hints": []})
    if sequential and len(tasks) > 1:  # chain in spoken order
        for i in range(1, len(tasks)):
            tasks[i]["dep_hints"] = [tasks[i - 1]["title"]]
    if continues_thread and tasks and prev_titles:  # continue prior thread
        tasks[0]["dep_hints"] = [prev_titles[-1]] + tasks[0]["dep_hints"]
    return {"tasks": tasks, "ideas": ideas, "notes": notes,
            "done_mentions": done, "project": suggest_project(text)}
