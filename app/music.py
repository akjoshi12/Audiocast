"""Scene moods -> MusicGen beds -> mixed under the voice track (ducked, faded)."""
import hashlib
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

from app.tts import SR

MODEL_ID = "facebook/musicgen-small"
CLIP_TOKENS = 1024        # ~20 s per generated clip (50 tokens/s)
BASE_DB, DUCK_DB = -7.0, -5.0  # music vs speech: -7 dB in gaps, -12 dB under speech (was -13/-19 and still not heard on a phone)
FADE_S, MIN_CUE_S = 2.0, 25.0
QUIET, MAX_CUE_S = ("calm", "none", ""), 75.0   # calm stretches get no music; a cue fades out after MAX_CUE_S (tune by ear)

_mg = None


def _musicgen():
    global _mg
    if _mg is None:
        import torch
        from transformers import AutoProcessor, MusicgenForConditionalGeneration
        dev = "mps" if torch.backends.mps.is_available() else "cpu"
        _mg = (AutoProcessor.from_pretrained(MODEL_ID),
               MusicgenForConditionalGeneration.from_pretrained(MODEL_ID).to(dev), dev)
    return _mg


def prompt_for(mood: str, setting: str = "") -> str:
    return (f"{mood} instrumental underscore for an audiobook{', ' + setting if setting else ''}, "
            "soft piano and warm strings, slow, sparse, no vocals, no drums, cinematic")  # an ambient drone is mostly bass: a phone speaker drops it


def bed(mood: str, seconds: float, cache: Path, setting: str = "") -> np.ndarray:
    """A music bed of the requested length for a mood. Clips are cached on disk and cross-looped."""
    key = hashlib.md5(prompt_for(mood, setting).encode()).hexdigest()[:10]
    f = cache / f"{mood.replace(' ', '_')}_{key}.wav"
    if not f.exists():
        proc, model, dev = _musicgen()
        x = proc(text=[prompt_for(mood, setting)], padding=True, return_tensors="pt").to(dev)
        a = model.generate(**x, do_sample=True, guidance_scale=3.0, max_new_tokens=CLIP_TOKENS)
        clip = a[0, 0].float().cpu().numpy()
        sr = model.config.audio_encoder.sampling_rate
        cache.mkdir(parents=True, exist_ok=True)
        sf.write(f, resample_poly(clip, SR, sr).astype(np.float32), SR)
    clip = sf.read(f, dtype="float32")[0]
    clip = clip * (0.1 / max(float(np.sqrt((clip ** 2).mean())), 1e-4))  # same loudness for every mood
    return loop(clip, int(seconds * SR))


def loop(clip: np.ndarray, n: int, xf: int = int(3 * SR)) -> np.ndarray:
    """Repeat a clip to n samples with equal-power-ish crossfades (ponytail: audible repeat every ~17 s
    on long scenes; upgrade = generate several clips per mood and alternate)."""
    out = clip.copy()
    fade = np.linspace(0, 1, xf, dtype=np.float32)
    while len(out) < n:
        out[-xf:] = out[-xf:] * (1 - fade) + clip[:xf] * fade
        out = np.concatenate([out, clip[xf:]])
    return out[:n]


def cues(lines: list[dict], spans: list[tuple[float, float]]) -> list[dict]:
    """Music only where the scene calls for it: calm/unlabelled lines and headings are silent ("none"), music enters at a mood change.
    Same-mood lines group into a cue, cues shorter than MIN_CUE_S are absorbed into the previous one, audible cues are capped at MAX_CUE_S."""
    moods = ["none" if l.get("kind") == "heading" or l["mood"].strip().lower() in QUIET else l["mood"].strip().lower() for l in lines]
    out = []
    for mood, (a, b) in zip(moods, spans):
        if out and out[-1]["mood"] == mood:
            out[-1]["end"] = b
        else:
            out.append({"mood": mood, "start": a, "end": b})
    merged = []
    for c in out:
        if merged and (c["end"] - c["start"] < MIN_CUE_S or c["mood"] == merged[-1]["mood"]):
            merged[-1]["end"] = c["end"]
        else:
            merged.append(c)
    for c in merged:
        if c["mood"] != "none":
            c["end"] = min(c["end"], c["start"] + MAX_CUE_S)
    return merged


def mix(voice: np.ndarray, spans: list[tuple[float, float]], cue_list: list[dict], cache: Path,
        setting: str = "") -> np.ndarray:
    n = len(voice)
    music = np.zeros(n, dtype=np.float32)
    for c in cue_list:
        if c["mood"] in ("none", ""):
            continue
        a, b = int(c["start"] * SR), min(int(c["end"] * SR), n)
        seg = bed(c["mood"], (b - a + 1) / SR, cache, setting)[: b - a]  # +1: int(s*SR) can round one sample short
        f = min(int(FADE_S * SR), len(seg) // 2)
        seg[:f] *= np.linspace(0, 1, f); seg[-f:] *= np.linspace(1, 0, f)
        music[a:b] += seg
    # duck under speech: extra attenuation while someone talks, smoothed so it never pumps
    talk = np.zeros(n, dtype=np.float32)
    for a, b in spans:
        talk[int(a * SR): int(b * SR)] = 1
    k = int(0.5 * SR)
    talk = np.convolve(talk, np.ones(k, dtype=np.float32) / k, mode="same")
    gain = 10 ** ((BASE_DB + DUCK_DB * talk) / 20)
    return np.clip(voice + music * gain, -1, 1)
