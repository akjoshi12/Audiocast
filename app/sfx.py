"""Sound effects. A script line may carry sfx=[{"prompt": "...", "at": "start"|"end"}]; AudioLDM makes a short clip per prompt
(cached on disk) and it gets its own gap in the finished voice track, right before that line or right after it."""
import hashlib
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

from app.tts import SR

MODEL_ID = "cvssp/audioldm-s-full-v2"
NATIVE_SR, SECONDS, STEPS = 16000, 3.0, 25
OVERLAP, TAIL_KEEP = 0.3, 0.15   # s of effect tail that may run under the next line's speech; s of silence kept after the trimmed clip
PEAK, MIN_PEAK, TRIES = 0.35, 0.05, 3   # effect peak vs the voice (~0.9); a take quieter than MIN_PEAK is the model failing, not a quiet sound

_pipe = None


def usable(a: np.ndarray) -> np.ndarray | None:
    """Scale a take to PEAK; None when it is (near) silent, which AudioLDM sometimes returns for a prompt."""
    peak = float(np.abs(a).max()) if len(a) else 0.0
    return None if peak < MIN_PEAK else (a * (PEAK / peak)).astype(np.float32)


def clip(prompt: str, cache: Path) -> np.ndarray | None:
    """The effect for a prompt at SR, or None when the model never produced a usable take (remembered, so it is not retried)."""
    key = hashlib.md5(f"{MODEL_ID}|{SECONDS}|{prompt}".encode()).hexdigest()[:10]
    f, bad = cache / f"{key}.wav", cache / f"{key}.none"
    if bad.exists():
        return None
    if not f.exists():
        global _pipe
        import torch
        from diffusers import AudioLDMPipeline
        if _pipe is None:   # CPU on purpose: ~3 s a clip, and the MPS backend returned silent takes for half the prompts
            _pipe = AudioLDMPipeline.from_pretrained(MODEL_ID, torch_dtype=torch.float32).to("cpu")
            _pipe.set_progress_bar_config(disable=True)
        cache.mkdir(parents=True, exist_ok=True)
        for seed in range(TRIES):
            a = _pipe(prompt, num_inference_steps=STEPS, audio_length_in_s=SECONDS, negative_prompt="low quality", guidance_scale=3.0,
                      generator=torch.Generator("cpu").manual_seed(seed)).audios[0]
            a = usable(a)
            if a is not None:
                sf.write(f, resample_poly(a, SR, NATIVE_SR).astype(np.float32), SR)
                break
        else:
            bad.touch()
            return None
    return sf.read(f, dtype="float32")[0]


def add(voice: np.ndarray, lines: list[dict], spans: list[tuple[float, float]], cache: Path, make=clip) -> tuple[np.ndarray, list[tuple[float, float]]]:
    """Each effect gets its own gap in the voice track (before its line, or after it) instead of playing over speech; returns the audio
    and the spans shifted by the inserted gaps. The speech after an effect may start OVERLAP s before the effect ends, so it flows."""
    out, spans, placed = voice.copy(), [tuple(x) for x in spans], []   # pass 1 opens every gap in the clean voice, pass 2 mixes the clips: a later gap never cuts an earlier clip
    for i, l in enumerate(lines):
        for e in l.get("sfx", []):
            c = make(e["prompt"], cache)
            if c is None or not len(c) or not np.abs(c).max():
                continue
            c = c[: int(np.nonzero(np.abs(c) > 0.05 * np.abs(c).max())[0][-1]) + 1 + int(TAIL_KEEP * SR)].copy()   # the model pads every clip to 3 s
            n, f = int(0.03 * SR), min(int(0.4 * SR), len(c) // 2)
            c[:n] *= np.linspace(0, 1, min(n, len(c)), dtype=np.float32)
            c[len(c) - f:] *= np.linspace(1, 0, f, dtype=np.float32)
            room = len(c) / SR - OVERLAP
            a, b = spans[i]
            if e.get("at") == "end":
                s, first = round(b * SR), i + 1
                gap = max(0.0, room - (spans[i + 1][0] - b)) if i + 1 < len(spans) else 0.0
            else:
                s, first, gap = round(a * SR), i, max(0.0, room)
            g = round(gap * SR)
            out = np.concatenate([out[:s], np.zeros(g, np.float32), out[s:]])
            placed.append((s, c))
            spans[first:] = [(x + g / SR, y + g / SR) for x, y in spans[first:]]
    out = np.concatenate([out, np.zeros(max([s + len(c) for s, c in placed] + [len(out)]) - len(out), np.float32)])   # last line: extend the track to fit the clip
    for s, c in placed:
        out[s:s + len(c)] += c
    return np.clip(out, -1, 1), spans
