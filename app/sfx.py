"""Sound effects. A script line may carry sfx=[{"prompt": "...", "at": "start"|"end"}]; AudioLDM makes a short clip per prompt
(cached on disk) and it is laid over the finished voice track at the start of that line or right after it."""
import hashlib
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

from app.tts import SR

MODEL_ID = "cvssp/audioldm-s-full-v2"
NATIVE_SR, SECONDS, STEPS = 16000, 3.0, 25
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


def add(voice: np.ndarray, lines: list[dict], spans: list[tuple[float, float]], cache: Path, make=clip) -> np.ndarray:
    out = voice.copy()
    for l, (a, b) in zip(lines, spans):
        for e in l.get("sfx", []):
            c = make(e["prompt"], cache)
            s = int((b if e.get("at") == "end" else a) * SR)
            if c is None or s >= len(out):
                continue
            c = c[: len(out) - s].copy()
            n, f = int(0.03 * SR), min(int(0.4 * SR), len(c) // 2)
            c[:n] *= np.linspace(0, 1, min(n, len(c)), dtype=np.float32)
            c[len(c) - f:] *= np.linspace(1, 0, f, dtype=np.float32)
            out[s:s + len(c)] += c
    return np.clip(out, -1, 1)
