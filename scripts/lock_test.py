import numpy as np, soundfile as sf
from mlx_audio.tts.utils import load_model
from app import tts

REF_TEXT = ("I’m pretty much screwed. That’s my considered opinion. Screwed. Six days in to what should be a greatest two months of my life, "
            "and it’s turned in to a nightmare. I don’t even know who’ll read this. I guess someone will find it eventually.")
DESC = "An elderly man with an extremely deep, warm, smooth bass voice, wise and calm, unhurried, with great gravitas, like a beloved storyteller. Speaks slowly with rich resonance and gentle pauses."
LINES = [("The airlock hissed and the whole habitat shuddered.", "tense, hushed"),
         ("It was a quiet morning, and the sun rose slowly over the red dunes.", "calm, gentle"),
         ("He screamed into the storm, but nobody could hear him.", "desperate, loud"),
         ("And that, as they say, was that.", "dry, amused")]

def f0(x, sr=24000):
    fr, vals = 1024, []
    for i in range(0, len(x) - fr * 2, fr):
        s = x[i:i+fr*2]; s = s - s.mean()
        if np.sqrt((s**2).mean()) < 0.02: continue
        ac = np.correlate(s, s, "full")[len(s)-1:]; lo, hi = sr//300, sr//60
        k = lo + int(np.argmax(ac[lo:hi]))
        if ac[k] > 0.4 * ac[0]: vals.append(sr / k)
    return float(np.median(vals)) if vals else float("nan")

res = {}
d = load_model(model_path="mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-bf16")
for i, (t, e) in enumerate(LINES):
    a = np.concatenate([np.array(r.audio) for r in d.generate(text=t, instruct=f"{DESC} Delivery: {e}.", lang_code="en", verbose=False)])
    sf.write(f"samples/lock/design_{i}.wav", a, 24000); res.setdefault("design", []).append(f0(a))
del d
c = load_model(model_path="mlx-community/chatterbox-turbo-fp16")
for i, (t, e) in enumerate(LINES):
    ex = {"tense, hushed": 0.4, "calm, gentle": 0.3, "desperate, loud": 0.9, "dry, amused": 0.55}[e]
    a = np.concatenate([np.array(r.audio) for r in c.generate(text=t, ref_audio="voices/narrator_ref.wav", ref_text=REF_TEXT, exaggeration=ex, verbose=False)])
    sf.write(f"samples/lock/chatter_{i}.wav", a, 24000); res.setdefault("chatterbox_clone", []).append(f0(a))
sf.write("samples/lock/ref_f0_check.wav", sf.read("voices/narrator_ref.wav")[0], 24000)
print("ref median f0:", round(f0(sf.read("voices/narrator_ref.wav", dtype="float32")[0]), 1))
for k, v in res.items(): print(k, [round(x, 1) for x in v], "spread (std Hz):", round(float(np.nanstd(v)), 1))
