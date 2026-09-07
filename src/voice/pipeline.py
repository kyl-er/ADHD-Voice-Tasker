"""Voice pipeline orchestration: mic → VAD → Deepgram → fast-LLM loop.

The mic ring-buffer is shared with the TUI visualizer (single capture path).
Only FINAL transcripts hit the LLM; partials go to caption + visualizer.

Fast-loop prompt contract (one round-trip, JSON out):
  {"tasks": [{title, category, urgency, dep_hints[]}],
   "ideas": [{title, detail}], "notes": [str], "done_mentions": [str]}
"""
from __future__ import annotations

FAST_EXTRACT_PROMPT = """You turn a voice transcript chunk into structured task data.
Return JSON ONLY: {"tasks": [{"title": verb-first, "<80 chars",
"category": "dev|research|ops|admin|personal|general",
"urgency": 0..1, "dep_hints": ["titles this waits on"]}],
"ideas": [{"title": "", "detail": ""}], "notes": [""], "done_mentions": [""]}.
Merge duplicates by meaning, not wording. Empty arrays are fine."""


class VoicePipeline:
    """Phase-1: connect DeepgramStreamer + Router + Store."""

    def __init__(self, settings=None):
        self.settings = settings
        self._frames: list[bytes] = []  # shared ring-buffer (visualizer reads this)

    @property
    def ring_buffer(self):
        return self._frames

    def on_final_transcript(self, text: str) -> dict:
        """Run the fast loop on a final transcript. Returns the parsed JSON."""
        from src.providers.router import Router
        router = Router.from_settings() if self.settings is None else Router(self.settings)
        return router.complete_json(
            "fast",
            [{"role": "system", "content": FAST_EXTRACT_PROMPT},
             {"role": "user", "content": text}])
