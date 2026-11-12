"""Script -> audio. Qwen3-TTS CustomVoice: named speaker + emotion instruction per line.
Per-line wavs are cached on disk so a crashed render resumes where it stopped."""
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

MODEL_ID = "mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-6bit"
SR = 24000
# ponytail: voice genders are my guess from the model's speaker list; verify by listening (scripts/voice_samples.py)
VOICES = {
    "female": ["serena", "vivian", "ono_anna", "sohee"],
    "male": ["ryan", "aiden", "eric", "dylan", "uncle_fu"],
}
NARRATOR_VOICE = "narrator_ref"   # VoxCPM2 clone of voices/narrator_ref.wav ("a_warm_elder", chosen by the user)
NARRATOR_REF = Path(__file__).resolve().parent.parent / "voices" / "narrator_ref.wav"
NARRATOR_REF_TEXT = ("I’m pretty much screwed. That’s my considered opinion. Screwed. Six days in to what should be a greatest two months of my life, "
                     "and it’s turned in to a nightmare. I don’t even know who’ll read this. I guess someone will find it eventually.")

ROOT = Path(__file__).resolve().parent.parent
DESIGN_TEXT = ("I never thought I would see you again, not after everything that happened. "
               "But here we are, and there is a great deal to say before the night is over.")
VARIETY = ["", "higher-pitched and bright", "low and gravelly", "soft and slow", "crisp and clear", "warm and breathy"]
_model = None
_dm = None


def _cut(s: str, maxc: int) -> list[str]:
    """Break an over-long sentence into pieces of at most maxc chars, preferably after a comma/semicolon/colon, else at a space."""
    out = []
    while len(s) > maxc:
        cut = max((s.rfind(m, 0, maxc) for m in (", ", "; ", ": ")), default=-1)
        cut = cut + 1 if cut > 0 else (s.rfind(" ", 0, maxc) if s.rfind(" ", 0, maxc) > 0 else maxc)
        out.append(s[:cut].strip())
        s = s[cut:].strip()
    return out + [s]


def split_text(text: str, maxc: int = 160) -> list[str]:
    """Sentence-sized pieces (long paragraphs flatten TTS prosody; very long ones can make a voice model fail), each at most maxc chars."""
    import re
    out, cur = [], ""
    for sent in re.split(r"(?<=[.!?…])\s+", text.strip()):
        for piece in (_cut(sent, maxc) if len(sent) > maxc else [sent]):
            if cur and len(cur) + len(piece) > maxc:
                out.append(cur); cur = ""
            cur = f"{cur} {piece}".strip()
    return out + ([cur] if cur else [])


def model():
    global _model
    if _model is None:
        from mlx_audio.tts.utils import load_model
        _model = load_model(model_path=MODEL_ID)
    return _model


PITCH = ["deep", "low", "mid-range", "high"]
TIMBRE = ["gravelly", "smooth", "nasal", "breathy", "resonant", "thin", "warm", "reedy", "husky"]
PACE = ["slow", "measured"]


def contrast(avoid: dict | None = None) -> dict:
    """Random pitch/timbre/pace to push a redesigned voice away from the previous one (avoid = its words)."""
    import random
    avoid = avoid or {}
    pick = lambda opts, k: random.choice([o for o in opts if o != avoid.get(k)] or opts)
    return {"pitch": pick(PITCH, "pitch"), "timbre": pick(TIMBRE, "timbre"), "pace": pick(PACE, "pace")}


def voice_prompt(c: dict, k: int, hint: dict | None = None) -> str:
    """Description for the voice-design model. k = how many characters of the same gender/age already exist (pushes look-alikes
    apart); hint = explicit pitch/timbre/pace. Unknown gender/age is left out rather than invented."""
    who = " ".join(x for x in (c.get("age") if c.get("age") != "unknown" else "", c.get("gender") if c.get("gender") in ("male", "female") else "") if x) or "adult"
    traits = "" if "excerpt" in (c.get("voice") or "").lower() else (c.get("voice") or "")  # the describer sometimes writes about the excerpt, not the voice
    extra = f"{hint['pitch']}-pitched, {hint['timbre']}, {hint['pace']} pace." if hint else VARIETY[k % len(VARIETY)]
    return f"{'An' if who[0] in 'aeiou' else 'A'} {who} speaking voice. {traits} {extra}".strip()


def ref_pitch(path: Path) -> int:
    """Median pitch (Hz) of a voice clip, to check that a redesigned voice really differs."""
    a = sf.read(path, dtype="float32")[0]
    lo, hi = SR // 400, SR // 60
    ps = []
    for i in range(0, len(a) - 7200, 7200):
        w = a[i:i + 7200]
        if np.sqrt((w ** 2).mean()) > 0.02:
            ps.append(SR // (lo + int(np.argmax(np.correlate(w, w, "full")[len(w):][lo:hi]))))
    return int(np.median(ps)) if ps else 0


def design_voice(instruct: str, out: Path) -> Path:
    """Make one voice from a text description and save it; the file is then the character's fixed reference (cloned for every line)."""
    global _dm
    if _dm is None:
        from mlx_audio.tts.utils import load_model
        _dm = load_model(model_path="mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-bf16")
    parts = [np.array(r.audio) for r in _dm.generate(text=DESIGN_TEXT, instruct=instruct, lang_code="en", verbose=False)]
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(out, np.concatenate(parts), SR)
    return out


def auto_cast(characters: list[dict]) -> dict[str, str]:
    """character name -> voice. Narrator gets a fixed voice; others spread by gender, no repeats until exhausted."""
    cast = {"Narrator": NARRATOR_VOICE}
    used = {NARRATOR_VOICE: 1}
    for c in characters:
        pool = VOICES["female"] if c["gender"] == "female" else VOICES["male"] if c["gender"] == "male" \
            else VOICES["female"] + VOICES["male"]
        v = min(pool, key=lambda p: used.get(p, 0))
        used[v] = used.get(v, 0) + 1
        cast[c["name"]] = v
    return cast


VOX_PY = ROOT / ".venv-voxcpm" / "bin" / "python"
NARRATOR_DIRECTION = "an unhurried, warm audiobook narrator"
_vox = None


def stop_vox() -> None:
    """Quit the VoxCPM2 worker so its memory is free (called before scripts start); it restarts on the next render."""
    global _vox
    if _vox is not None and _vox.poll() is None:
        _vox.terminate()
        _vox.wait(timeout=30)
    _vox = None


def _vox_ask(job: dict) -> dict:
    """One request to the VoxCPM2 worker process (started on first use; the model takes ~2 min to load, then stays up)."""
    global _vox
    if _vox is None or _vox.poll() is not None:
        _vox = subprocess.Popen([str(VOX_PY), str(Path(__file__).with_name("vox_worker.py"))], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        if "ready" not in json.loads(_vox.stdout.readline() or "{}"):
            raise RuntimeError("VoxCPM2 worker did not start (see server.log)")
    _vox.stdin.write(json.dumps(job) + "\n")
    _vox.stdin.flush()
    r = json.loads(_vox.stdout.readline() or '{"ok": false, "err": "worker died"}')
    if not r["ok"]:
        raise RuntimeError(f"VoxCPM2: {r['err']}")
    return r


def _speak_vox(text: str, voice: str, emotion: str, depth: int = 0, retried: bool = False) -> np.ndarray:
    """Clone `voice` with VoxCPM2; the line's emotion becomes the written direction "(...)" in front of the text.
    If the model fails on a piece, a long one is retried as two halves (up to 3 levels deep), a short one is retried once as it is:
    the model samples randomly and has failed with an array-shape error on some takes."""
    from scipy.signal import resample_poly
    ref = NARRATOR_REF if voice == NARRATOR_VOICE else ROOT / voice[6:]
    direction = ", ".join(x for x in (NARRATOR_DIRECTION if voice == NARRATOR_VOICE else "", emotion.strip()) if x)
    fd, out = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        _vox_ask({"text": f"({direction}) {text}" if direction else text, "ref": str(ref), "out": out})
        a, sr = sf.read(out, dtype="float32")
    except RuntimeError:
        mid = text.rfind(" ", 0, len(text) // 2 + 1)
        if len(text) > 80 and depth < 3 and mid > 0:
            return np.concatenate([_speak_vox(text[:mid], voice, emotion, depth + 1), _speak_vox(text[mid + 1:], voice, emotion, depth + 1)])
        if not retried:
            return _speak_vox(text, voice, emotion, depth, retried=True)
        raise
    finally:
        if os.path.exists(out):
            os.unlink(out)
    return resample_poly(a, SR, sr).astype(np.float32)


def _speak_piece(text: str, voice: str, emotion: str) -> np.ndarray:
    if voice == NARRATOR_VOICE or voice.startswith("clone:"):
        return _speak_vox(text, voice, emotion)
    rs = model().generate(text=text, voice=voice, instruct=emotion, lang_code="en", verbose=False)
    parts = [np.array(r.audio) for r in rs]
    return np.concatenate(parts) if parts else np.zeros(0, dtype=np.float32)


TIGHTEN = "pace2"   # bump when tighten() or the piece length changes: part of the line-cache key (pace2: pieces <=160 chars; long takes drifted into a rough, grainy voice)


def tighten(a: np.ndarray, max_gap: float = 0.7, edge: float = 0.1) -> np.ndarray:
    """Shorten silences inside a clip to max_gap seconds and trim its own lead/tail to `edge`. The voice model sometimes stalls
    ~1 s at a comma or dash in the middle of a sentence; pauses between sentences are added by us, not by the model."""
    w = int(SR * 0.02)
    n = len(a) // w
    if n < 10:
        return a
    env = np.sqrt((a[:n * w].reshape(n, w) ** 2).mean(axis=1))
    quiet = env < max(float(env.max()) * 0.05, 1e-4)
    keep, i, gap, ed = np.ones(n, bool), 0, int(max_gap / 0.02), int(edge / 0.02)
    while i < n:
        if not quiet[i]:
            i += 1
            continue
        j = i
        while j < n and quiet[j]:
            j += 1
        if i == 0:
            keep[i:max(j - ed, i)] = False                 # lead: keep only the last `edge`
        elif j == n:
            keep[min(i + ed, j):j] = False                 # tail: keep only the first `edge`
        elif j - i > gap:
            keep[i + gap // 2:j - (gap - gap // 2)] = False  # inside: cut the middle of the silence
        i = j
    return np.concatenate([a[k * w:(k + 1) * w] for k in np.flatnonzero(keep)] + [a[n * w:]])


TEMPO = 0.92   # slow() default; also kept in line_file's hashed string only so existing cache names stay valid
GAPS = {".": 0.55, "!": 0.5, "?": 0.5, "…": 0.7}   # pause after a sentence piece, by its last mark; other = 0.3


def slow(a: np.ndarray, tempo: float = TEMPO) -> np.ndarray:
    """Pitch-preserving slow-down through ffmpeg atempo."""
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-",
                        "-filter:a", f"atempo={tempo}", "-f", "f32le", "-"], input=a.astype("<f4").tobytes(), capture_output=True, check=True)
    return np.frombuffer(r.stdout, dtype="<f4").copy()


CHAR_MAX_WPM, MIN_TEMPO = 165, 0.8   # calibration knobs, tune by ear: character voices are slowed to at most this pace (narrator measures ~155-165 wpm on existing renders, never capped)


def pace(a: np.ndarray, text: str, max_wpm: float = CHAR_MAX_WPM) -> np.ndarray:
    """Slow a piece that is read faster than max_wpm (never below MIN_TEMPO). Short pieces give a noisy rate, so they pass."""
    words = len(text.split())
    if words < 4 or not len(a):
        return a
    # ponytail: words-per-minute is a rough proxy; count syllables if long-word lines still rush
    rate = words / (len(a) / SR / 60)
    return a if rate <= max_wpm else slow(a, max(max_wpm / rate, MIN_TEMPO))


def speak(text: str, voice: str, emotion: str) -> np.ndarray:
    out = []
    for t in split_text(text):
        a = tighten(_speak_piece(t, voice, emotion))
        a = a if voice == NARRATOR_VOICE else pace(a, t)
        out += [a, np.zeros(int(SR * GAPS.get(t.rstrip("\"”’')")[-1:], 0.3)), dtype=np.float32)]
    return np.concatenate(out[:-1]) if out else np.zeros(0, dtype=np.float32)


def _voice_for(l: dict, cast: dict[str, str]) -> str:
    return cast.get(l["speaker"], cast.get("Narrator", NARRATOR_VOICE))


def line_file(cache: Path, i: int, l: dict, voice: str) -> Path:
    """Cache name includes a hash of what is spoken, so editing a line re-renders only that line."""
    # the hashed string is frozen so re-rendering hours of narrator audio is not needed: engine literal, TEMPO and the (now unused) 'emphasis' key stay in it
    engine = "voxcpm" if voice == NARRATOR_VOICE or voice.startswith("clone:") else ""
    h = hashlib.md5((f"{voice}|{engine}|{TIGHTEN}|{TEMPO}|{l['emotion']}|{l['text']}|{l.get('emphasis', '')}" + ('' if voice == NARRATOR_VOICE else f"|wpm{CHAR_MAX_WPM}")).encode()).hexdigest()[:10]
    return cache / f"{i:05d}_{h}.wav"


def spans(lines: list[dict], cast: dict[str, str], folder: Path) -> list[tuple[float, float]]:
    """(start, end) seconds of each line's speech inside chapter.wav, from the cached line wavs."""
    t, out = 0.0, []
    for i, l in enumerate(lines):
        d = sf.info(line_file(folder / "lines", i, l, _voice_for(l, cast))).duration
        out.append((t, t + d))
        t += d + max(l["pause_after"], 0.1)
    return out


def render(lines: list[dict], cast: dict[str, str], folder: Path, progress=None) -> Path:
    """Render every line (cached), join with pauses, return the wav path."""
    cache = folder / "lines"
    cache.mkdir(parents=True, exist_ok=True)
    pieces = []
    for i, l in enumerate(lines):
        voice = _voice_for(l, cast)
        f = line_file(cache, i, l, voice)
        if not f.exists():
            sf.write(f, speak(l["text"], voice, l["emotion"]), SR)
        pieces += [sf.read(f, dtype="float32")[0],
                   np.zeros(int(SR * max(l["pause_after"], 0.1)), dtype=np.float32)]
        if progress:
            progress(i + 1, len(lines))
    for old in cache.glob("*.wav"):  # drop cache files of lines that no longer exist or changed
        if old not in {line_file(cache, j, m, _voice_for(m, cast)) for j, m in enumerate(lines)}:
            old.unlink()
    out = folder / "chapter.wav"
    sf.write(out, np.concatenate(pieces), SR)
    return out
