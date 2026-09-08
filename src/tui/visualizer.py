"""TUI voice visualizer: layered sine waves + scrolling spectrogram.

Textual app reading the shared mic ring-buffer (or `--demo` synth when no
mic/keys). Layout:

  ┌ sine waves (3 phase-offset traces, energy-driven) ─────┐ caption rail
  │ ▁▂▃▄▅▆▇█ gradient ribbons                              │ > partial…
  ├ spectrogram (32-bin FFT heat scroll, peak-hold) ───────┤ > FINAL ✓
  └ status: provider · latency · tasks captured ───────────┘

Run:  python -m src.tui.visualizer --demo
"""
from __future__ import annotations

import argparse
import math
import random
import time

BLOCKS = " ▁▂▃▄▅▆▇█"
HEAT = " .·:+*#%@"  # spectrogram intensity ramp


def sine_frame(width: int, t: float, energy: float, layers: int = 3) -> list[str]:
    """Render `layers` sine traces as block-char rows. energy 0..1."""
    rows = []
    for layer in range(layers):
        phase = t * (2.0 + layer * 0.7) + layer * 2.1
        amp = 0.25 + energy * 0.75 * (1 - layer * 0.2)
        chars = []
        for x in range(width):
            v = math.sin(x * 0.15 + phase) * amp
            v += 0.3 * math.sin(x * 0.05 - phase * 0.6) * energy
            idx = max(0, min(8, int((v * 0.5 + 0.5) * 8)))
            chars.append(BLOCKS[idx])
        rows.append("".join(chars))
    return rows


def spectrum_frame(n_bins: int = 32, energy: float = 0.5) -> list[float]:
    """Fake-but-plausible FFT magnitudes; Phase 1 swaps in numpy rfft."""
    return [min(1.0, energy * (0.4 + 0.6 * random.random())
             * math.exp(-i / (n_bins * 0.45))) for i in range(n_bins)]


def heat_col(mags: list[float], height: int = 8) -> list[str]:
    cols = []
    for row in range(height):
        line = "".join(HEAT[min(8, int(m * (row + 1)))] for m in mags)
        cols.append(line)
    return cols


def demo_loop(fps: int = 15) -> None:
    """Zero-dependency demo: breathing sine + fake speech bursts."""
    import os
    t0 = time.time()
    try:
        while True:
            t = time.time() - t0
            # breathing idle + random "speech" bursts
            energy = 0.15 + 0.1 * math.sin(t * 0.8)
            if int(t) % 5 in (2, 3):
                energy = 0.6 + 0.3 * math.sin(t * 7)
            energy = max(0.05, min(1.0, energy))
            os.system("cls" if os.name == "nt" else "clear")
            print("═" * 64 + "\n  ADHD-VOICE-TASKER · TUI  (demo synth — Ctrl+C to quit)\n" + "═" * 64)
            for row in sine_frame(60, t, energy):
                print("  " + row)
            print("─" * 64 + "  SPECTROGRAM")
            for line in heat_col(spectrum_frame(48, energy)):
                print("  " + line)
            print("─" * 64 + f"  energy {energy:0.2f} · Deepgram partials would stream here")
            time.sleep(1 / fps)
    except KeyboardInterrupt:
        print("\nbye 👋")


class VoiceVisualizerApp:
    """Phase-1 Textual app shell. Requires: textual, numpy, sounddevice."""

    def __init__(self, demo: bool = False):
        self.demo = demo

    def run(self) -> None:
        if self.demo:
            return demo_loop()
        try:
            return live_loop()  # real mic RMS + FFT (sounddevice + numpy)
        except Exception as e:  # noqa: BLE001 - no mic/libs in this env
            print(f"[live unavailable: {e} — falling back to demo synth]")
            return demo_loop()


def live_loop(fps: int = 15) -> None:
    """Live mic mode: real RMS energy + real FFT spectrum drive the renderers.

    Requires: sounddevice, numpy. Raises if no mic/default input exists.
    """
    import os

    import numpy as np
    import sounddevice as sd

    state = {"energy": 0.0, "mags": [0.0] * 32}

    def on_audio(indata, frames, time_info, status):
        mono = np.asarray(indata[:, 0], dtype=np.float32)
        rms = float(np.sqrt(np.mean(mono ** 2)))
        state["energy"] = min(1.0, rms * 6)
        spec = np.abs(np.real(np.fft.rfft(mono * np.hanning(len(mono)))))
        spec /= max(spec.max(), 1e-6)
        idx = (np.logspace(0, np.log10(len(spec)), 33)).astype(int)
        state["mags"] = [float(spec[a:b].max()) if b > a else 0.0
                         for a, b in zip(idx[:-1], idx[1:])]

    print("live mic mode — Ctrl+C to quit")
    with sd.InputStream(samplerate=16000, channels=1, blocksize=1600,
                        callback=on_audio):
        t0 = time.time()
        try:
            while True:
                t = time.time() - t0
                e = state["energy"]
                os.system("cls" if os.name == "nt" else "clear")
                print("═" * 64 + "\n  ADHD-VOICE-TASKER · TUI  ● LIVE MIC\n" + "═" * 64)
                for row in sine_frame(60, t, max(0.05, e)):
                    print("  " + row)
                print("─" * 64 + "  SPECTROGRAM (live FFT)")
                for line in heat_col(state["mags"]):
                    print("  " + line)
                print("─" * 64 + f"  energy {e:0.2f} · finals → fast-LLM loop")
                time.sleep(1 / fps)
        except KeyboardInterrupt:
            print("\nbye 👋")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="synth demo, no mic needed")
    args = ap.parse_args()
    VoiceVisualizerApp(demo=args.demo).run()


if __name__ == "__main__":
    main()
