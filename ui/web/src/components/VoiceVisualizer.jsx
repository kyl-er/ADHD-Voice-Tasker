/**
 * <VoiceVisualizer/> — fast, efficient AI voice visualizer module.
 *
 * Design for 60fps on weak hardware:
 *  - ONE canvas, ONE requestAnimationFrame loop, DPR capped at 2
 *  - AnalyserNode FFT arrays allocated ONCE and reused (zero per-frame alloc)
 *  - No setState per frame — props flow through refs; React renders once
 *  - Layers are pure draw fns: Waveform (mirrored ribbons) + Spectrogram
 *    (scrolling heat strip via drawImage self-blit) + Orb (listening glow)
 *  - Falls back to a procedural demo oscillator if mic is denied
 *
 * Usage:
 *   <VoiceVisualizer mode="full" energyRef={energyRef} stream={micStream} />
 *   // or demo: <VoiceVisualizer mode="full" demo />
 */
import { useEffect, useRef } from "react";

const HEAT = ["#12071f", "#2b0f54", "#4c1d95", "#0ea5e9", "#67e8f9", "#fef08a"];

export default function VoiceVisualizer({ mode = "full", stream = null, demo = false, energyRef = null }) {
  const canvasRef = useRef(null);
  const optsRef = useRef({ mode, stream, demo });
  optsRef.current = { mode, stream, demo }; // fresh props, no re-subscribe

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d", { alpha: false });
    let raf = 0, audioCtx = null, analyser = null, freq = null, wave = null;
    let W = 0, H = 0, t = 0, running = true;

    const resize = () => {
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      const r = canvas.getBoundingClientRect();
      W = canvas.width = Math.max(1, r.width * dpr);
      H = canvas.height = Math.max(1, r.height * dpr);
    };
    resize();
    window.addEventListener("resize", resize);

    const attachMic = async (s) => {
      try {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const src = audioCtx.createMediaStreamSource(s);
        analyser = audioCtx.createAnalyser();
        analyser.fftSize = 2048;
        analyser.smoothingTimeConstant = 0.82;
        src.connect(analyser);
        freq = new Uint8Array(analyser.frequencyBinCount); // alloc once
        wave = new Uint8Array(analyser.fftSize);            // alloc once
      } catch { analyser = null; }
    };
    if (optsRef.current.stream) attachMic(optsRef.current.stream);

    // demo oscillator state (no allocs in loop)
    let demoPhase = 0;

    const sampleEnergy = () => {
      if (analyser) {
        analyser.getByteTimeDomainData(wave);
        let sum = 0;
        for (let i = 0; i < wave.length; i += 4) {
          const v = (wave[i] - 128) / 128;
          sum += v * v;
        }
        return Math.min(1, Math.sqrt(sum / (wave.length / 4)) * 2.4);
      }
      // procedural demo: breathing + speech-like bursts
      demoPhase += 0.016;
      const burst = Math.sin(demoPhase * 0.9) > 0.4 ? 0.55 : 0.12;
      return Math.min(1, burst + 0.08 * Math.sin(demoPhase * 7));
    };

    const drawWaveform = (energy, half) => {
      const mid = half / 2;
      for (let layer = 0; layer < 3; layer++) {
        ctx.beginPath();
        ctx.strokeStyle = ["#22d3ee", "#a78bfa", "#f472b6"][layer];
        ctx.globalAlpha = 0.9 - layer * 0.25;
        ctx.lineWidth = (3 - layer) * (W / 900);
        for (let x = 0; x <= W; x += 4) {
          const p = x / W;
          let y;
          if (analyser) {
            const idx = Math.floor(p * (wave.length - 1));
            y = mid + ((wave[idx] - 128) / 128) * mid * (1 - layer * 0.22);
          } else {
            y = mid + Math.sin(p * 9 + t * (2 + layer * 0.7) + layer * 2.1)
              * mid * 0.55 * (0.3 + energy) * (1 - layer * 0.2);
          }
          x === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        }
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
    };

    const drawSpectrogram = (energy, top, height) => {
      // scroll previous frame left by 2px (GPU-cheap self-blit)
      ctx.drawImage(canvas, 2, 0, W - 2, H, 0, 0, W - 2, H);
      const bins = 48;
      const bw = height / bins;
      for (let i = 0; i < bins; i++) {
        let m;
        if (analyser) {
          const idx = 2 + Math.floor(Math.pow(i / bins, 1.6) * 400);
          m = freq[idx] / 255;
        } else {
          m = energy * Math.exp(-i / (bins * 0.4)) * (0.6 + 0.4 * Math.sin(t * 5 + i));
        }
        ctx.fillStyle = HEAT[Math.min(HEAT.length - 1, (m * HEAT.length) | 0)];
        ctx.fillRect(W - 2, top + H - height + i * bw, 2, bw + 1);
      }
    };

    const drawOrb = (energy) => {
      const cx = W / 2, cy = H * 0.32, r = Math.min(W, H) * 0.09 * (1 + energy * 0.5);
      const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, r * 3);
      g.addColorStop(0, "rgba(34,211,238,0.9)");
      g.addColorStop(0.4, "rgba(167,139,250,0.35)");
      g.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = g;
      ctx.beginPath(); ctx.arc(cx, cy, r * 3, 0, 7); ctx.fill();
      ctx.fillStyle = "#e0faff";
      ctx.beginPath(); ctx.arc(cx, cy, r * 0.45, 0, 7); ctx.fill();
    };

    const frame = () => {
      if (!running) return;
      t += 0.016;
      const energy = sampleEnergy();
      if (energyRef) energyRef.current = energy; // share with captions, no render
      const m = optsRef.current.mode;
      ctx.fillStyle = "#0b0e14";
      if (m !== "spectro") ctx.fillRect(0, 0, W, H);
      if (m === "full" || m === "wave") drawWaveform(energy, m === "full" ? H * 0.55 : H);
      if (m === "full" || m === "spectro") drawSpectrogram(energy, 0, H * 0.45);
      if (m === "full" || m === "orb") drawOrb(energy);
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);

    return () => {
      running = false;
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      if (audioCtx) audioCtx.close();
    };
  }, []);

  // re-attach if a mic stream arrives late (still no per-frame renders)
  useEffect(() => {
    if (stream && canvasRef.current) {
      // simplest correct: remount handled by parent key={hasStream}
    }
  }, [stream]);

  return (
    <canvas
      ref={canvasRef}
      style={{ width: "100%", height: "100%", display: "block", borderRadius: 24 }}
      aria-label="AI voice visualizer"
    />
  );
}
