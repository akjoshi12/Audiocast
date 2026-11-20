"""Sound effects. A script line may carry sfx=[{"prompt": "...", "at": "start"|"end"}]; TangoFlux makes a short clip per prompt
(cached on disk) and it gets its own gap in the finished voice track, right before that line or right after it."""
import hashlib
import json
import re
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, resample_poly, sosfilt

from app.music import loop
from app.tts import SR

MODEL_ID = "declare-lab/TangoFlux"
SECONDS = 4.0
ROOT = Path(__file__).resolve().parent.parent
TANGO_PY, WORKER = ROOT / ".venv-tango" / "bin" / "python", Path(__file__).with_name("tango_worker.py")
OVERLAP, TAIL_KEEP = 0.3, 0.15   # s of effect tail that may run under the next line's speech; s of silence kept after the trimmed clip
PEAK, MIN_PEAK = 0.35, 0.05   # effect peak vs the voice (~0.9); a take quieter than MIN_PEAK is the model failing, not a quiet sound

BED_S, BED_RMS, BED_DUCK_DB, BED_FADE_S = 10.0, 0.012, -4.0, 1.5   # ambience clip length; its level vs a ~0.09 voice (tune by ear: too loud hides the dialogue); extra dip under speech
SOFT = {"bed": 2500, "spot": 4000}   # Hz low-pass: the generated clips are hissy and harsh in the highs, which is what grates; SPOT_GAIN keeps effects behind the voice
SPOT_GAIN = 0.6
OVERLAY_GAIN, OVERLAY_LEAD = 0.7, 0.4   # an effect under speech sits lower; an 'end' effect starts this long before its line ends
PANS = (-0.3, 0.3, -0.15, 0.15, -0.4, 0.4)   # character positions, -1 left .. 1 right; the narrator stays in the centre
WIDTH_S = 0.018   # beds: right channel delayed this long, a cheap stereo width


def soften(a: np.ndarray, hz: int) -> np.ndarray:
    return sosfilt(butter(2, hz, fs=SR, output="sos"), a).astype(np.float32)


def usable(a: np.ndarray) -> np.ndarray | None:
    """Scale a take to PEAK; None when it is (near) silent, which a generator sometimes returns for a prompt."""
    peak = float(np.abs(a).max()) if len(a) else 0.0
    return None if peak < MIN_PEAK else (a * (PEAK / peak)).astype(np.float32)


def key(prompt: str, seconds: float) -> str:
    return hashlib.md5(f"{MODEL_ID}|{seconds}|{prompt}".encode()).hexdigest()[:10]


def clip(prompt: str, cache: Path, seconds: float = SECONDS) -> np.ndarray | None:
    """The cached effect for a prompt at SR, or None when it was never made or the model returned a silent take. prefetch() makes them."""
    f = cache / f"{key(prompt, seconds)}.wav"
    return sf.read(f, dtype="float32")[0] if f.exists() else None


def prefetch(jobs: set[tuple[str, float]], cache: Path, progress=None) -> None:
    """Generate every missing (prompt, seconds) in ONE TangoFlux process (its own venv, so its dependencies never touch the app's).
    progress(done, total) is called as each clip finishes (the worker prints one line per clip)."""
    cache.mkdir(parents=True, exist_ok=True)
    todo = [{"prompt": p, "seconds": sec, "out": str(cache / f"{key(p, sec)}.tmp.wav")} for p, sec in sorted(jobs)
            if not (cache / f"{key(p, sec)}.wav").exists() and not (cache / f"{key(p, sec)}.none").exists()]
    if not todo:
        return
    if progress:
        progress(0, len(todo))
    with subprocess.Popen([str(TANGO_PY), str(WORKER)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True) as p:
        p.stdin.write(json.dumps(todo))
        p.stdin.close()
        for i, _ in enumerate(p.stdout, 1):
            if progress:
                progress(min(i, len(todo)), len(todo))   # a stray library print can't push it past 100%
    if p.returncode:
        raise subprocess.CalledProcessError(p.returncode, WORKER)
    for j in todo:
        tmp = Path(j["out"])
        a = usable(resample_poly(sf.read(tmp, dtype="float32")[0], SR, 44100)) if tmp.exists() else None
        if a is None:
            (cache / f"{key(j['prompt'], j['seconds'])}.none").touch()
        else:
            sf.write(cache / f"{key(j['prompt'], j['seconds'])}.wav", a, SR)
        tmp.unlink(missing_ok=True)


def prepare(lines: list[dict], cache: Path, progress=None) -> None:
    """Make every effect and bed the script asks for."""
    prefetch({(e["prompt"], SECONDS) for l in lines for e in l.get("sfx", [])} | {(l["bed"].strip(), BED_S) for l in lines if (l.get("bed") or "").strip()}, cache, progress)


def add(voice: np.ndarray, lines: list[dict], spans: list[tuple[float, float]], cache: Path, make=clip, overlay: bool = False) -> tuple[np.ndarray, list[tuple[float, float]]]:
    """Each effect gets its own gap in the voice track (before its line, or after it) instead of playing over speech; returns the audio
    and the spans shifted by the inserted gaps. The speech after an effect may start OVERLAP s before the effect ends, so it flows."""
    out, spans, placed = voice.copy(), [tuple(x) for x in spans], []   # pass 1 opens every gap in the clean voice, pass 2 mixes the clips: a later gap never cuts an earlier clip
    for i, l in enumerate(lines):
        for e in l.get("sfx", []):
            c = make(e["prompt"], cache)
            if c is None or not len(c) or not np.abs(c).max():
                continue
            c = soften(c[: int(np.nonzero(np.abs(c) > 0.05 * np.abs(c).max())[0][-1]) + 1 + int(TAIL_KEEP * SR)], SOFT["spot"]) * SPOT_GAIN   # the model pads every clip to 3 s
            n, f = int(0.03 * SR), min(int(0.4 * SR), len(c) // 2)
            c[:n] *= np.linspace(0, 1, min(n, len(c)), dtype=np.float32)
            c[len(c) - f:] *= np.linspace(1, 0, f, dtype=np.float32)
            room = len(c) / SR - OVERLAP
            a, b = spans[i]
            if overlay:   # under the voice, no gap: the timeline does not move
                placed.append((max(0, round(a * SR) if e.get("at") != "end" else round(b * SR) - int(OVERLAY_LEAD * SR)), c * OVERLAY_GAIN))
                continue
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


MAX_BED_S = 25.0   # any bed fades out after this long, even a place (a 45 s road drone stretches)
EVENT, EVENT_S = re.compile(r"cry|scream|shout|yell|bark|knock|slam|honk|bang|crash|ring", re.I), 8.0   # one-off noises last seconds, not a paragraph (ponytail: keyword guess, tag place vs event in the LLM pass if it misfires)


def grounded(prompt: str, text: str) -> bool:
    """A bed may only start where its first line itself names something from its prompt (5-letter stems: screaming ~ scream, engine ~ engine)."""
    stems = {w[:5] for w in re.findall(r"[a-z]{3,}", prompt.lower())} - {"quiet", "dista", "soft", "faint", "muffl", "stead", "gentl", "with", "and", "the", "low", "slow"}
    return bool(stems & {w[:5] for w in re.findall(r"[a-z]{3,}", text.lower())})


def beds(voice: np.ndarray, lines: list[dict], spans: list[tuple[float, float]], cache: Path, make=clip) -> np.ndarray:
    """Quiet looping ambience under the voices: consecutive lines with the same l["bed"] prompt ("windscreen wipers and rain on a car roof",
    "a toddler screaming in another room") share one bed that runs from the first line's start to the last line's end, faded in and out,
    a little lower while someone speaks."""
    out, talk = voice.copy(), np.zeros(len(voice), np.float32)
    for a, b in spans:
        talk[int(a * SR):int(b * SR)] = 1
    k = int(0.4 * SR)
    talk = np.convolve(talk, np.ones(k, np.float32) / k, mode="same")
    gain = 10 ** (BED_DUCK_DB * talk / 20)
    i = 0
    while i < len(lines):
        prompt = (lines[i].get("bed") or "").strip()
        j = i
        while j + 1 < len(lines) and (lines[j + 1].get("bed") or "").strip() == prompt:
            j += 1
        if prompt and grounded(prompt, lines[i].get("text", "")):
            c = make(prompt, cache, BED_S)
            a, b = int(spans[i][0] * SR), min(int(spans[j][1] * SR), len(out))
            b = min(b, a + int((EVENT_S if EVENT.search(prompt) else MAX_BED_S) * SR))
            if c is not None and len(c) and np.abs(c).max() and b > a:
                w = int(1.5 * SR)   # generated engines/crowds chug in 1-3 s pulses: divide by the slow envelope so the bed hums steadily
                env = np.sqrt(np.convolve(np.pad(c ** 2, (w, w), mode="wrap"), np.ones(w, np.float32) / w, mode="same"))[w:-w]
                seg = soften(loop(c / np.maximum(env, 0.1 * float(env.max())), b - a), SOFT["bed"])
                seg = seg * (BED_RMS / max(float(np.sqrt((seg ** 2).mean())), 1e-4))
                f = min(int(BED_FADE_S * SR), len(seg) // 2)
                seg[:f] *= np.linspace(0, 1, f, dtype=np.float32); seg[len(seg) - f:] *= np.linspace(1, 0, f, dtype=np.float32)
                out[a:b] += seg * gain[a:b]
        i = j + 1
    return np.clip(out, -1, 1)


def stereo(voice: np.ndarray, fx: np.ndarray, bed: np.ndarray, lines: list[dict], spans: list[tuple[float, float]]) -> np.ndarray:
    """(n, 2) mix: narrator centred, each character at a fixed slightly-left/right spot, effects centred, beds widened."""
    n = max(len(voice), len(fx), len(bed))
    pad = lambda x: np.pad(x, (0, n - len(x)))
    voice, fx, bed = pad(voice), pad(fx), pad(bed)
    left, right = fx.copy(), fx.copy()
    for l, (a, b) in zip(lines, spans):
        pos = 0.0 if l.get("speaker", "Narrator") == "Narrator" else PANS[int(hashlib.md5(l["speaker"].encode()).hexdigest()[:4], 16) % len(PANS)]
        th = (pos + 1) * np.pi / 4
        seg = slice(int(a * SR), int(b * SR))
        left[seg] += voice[seg] * np.cos(th) * np.sqrt(2)
        right[seg] += voice[seg] * np.sin(th) * np.sqrt(2)
    d = int(WIDTH_S * SR)
    left += bed
    right += np.concatenate([np.zeros(d, np.float32), bed[:n - d]])
    return np.clip(np.stack([left, right], 1), -1, 1).astype(np.float32)


CHIME_S, CHIME_PEAK, CHIME_LEAD = 1.0, 0.22, 0.9   # a soft bell, quiet next to the voice; it starts this long before its line


def chimes(fx: np.ndarray, lines: list[dict], spans: list[tuple[float, float]]) -> np.ndarray:
    """Add a synthetic bell before every line marked l["chime"] (non-fiction takeaways); no model, no download."""
    t = np.arange(int(CHIME_S * SR)) / SR
    bell = sum(a * np.sin(2 * np.pi * f * t) for f, a in ((880.0, 1.0), (1318.5, 0.5), (1760.0, 0.25))) * np.exp(-4.5 * t)
    bell[:int(0.01 * SR)] *= np.linspace(0, 1, int(0.01 * SR))
    bell = (bell * (CHIME_PEAK / np.abs(bell).max())).astype(np.float32)
    out = fx.copy()
    for l, (a, b) in zip(lines, spans):
        if l.get("chime"):
            s0 = max(0, round(a * SR) - int(CHIME_LEAD * SR))
            out = np.pad(out, (0, max(0, s0 + len(bell) - len(out))))
            out[s0:s0 + len(bell)] += bell
    return out
