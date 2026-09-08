"""Deepgram streaming STT wrapper (Nova-3 / Flux).

Owns one WebSocket per voice session. Emits UtteranceEvents onto callbacks:
  on_partial(text) — live caption + visualizer energy
  on_final(text, confidence, t0, t1) — feeds the fast-LLM loop

Requires: deepgram-sdk, sounddevice, numpy (see requirements.txt).
Full wiring lands in Phase 1; this module pins the connection options.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

DEFAULT_OPTIONS = {
    "model": "nova-3",
    "language": "en",
    "smart_format": True,
    "interim_results": True,
    "endpointing": 300,  # ms of silence before finalizing
    "diarize": True,
    "utterance_end_ms": 1000,
}


@dataclass
class UtteranceEvent:
    kind: str  # "partial" | "final"
    text: str
    confidence: float = 0.0
    t0: float = 0.0
    t1: float = 0.0
    speaker: int | None = None


class DeepgramStreamer:
    def __init__(self, api_key: str, model: str = "nova-3", language: str = "en",
                 on_event: Callable[[UtteranceEvent], None] | None = None):
        self.api_key = api_key
        self.model = model
        self.language = language
        self.on_event = on_event or (lambda e: None)
        self._running = False

    @property
    def options(self) -> dict:
        return {**DEFAULT_OPTIONS, "model": self.model, "language": self.language}

    def start(self) -> None:
        """Open socket + mic and stream. Phase-1 implementation.

        Pseudocode (deepgram-sdk v3):
            client = DeepgramClient(self.api_key)
            conn = client.listen.websocket.v("1")
            conn.on(LiveTranscriptionEvents.Transcript, self._handle)
            conn.start(LiveOptions(**self.options))
            mic_stream(conn.send)   # 16kHz mono int16 frames
        """
        self._running = True
        raise NotImplementedError("Phase 1: wire deepgram-sdk streaming + mic capture")

    def stop(self) -> None:
        self._running = False
