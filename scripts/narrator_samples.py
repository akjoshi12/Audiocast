"""Deep-narrator candidates on the opening of The Martian ch.1."""
import soundfile as sf
from pathlib import Path
from app import tts

T = ("I’m pretty much screwed. That’s my considered opinion. Screwed. "
     "Six days in to what should be a greatest two months of my life, and it’s turned in to a nightmare.")
out = Path("samples/narrator")
DEEP = "Very deep, low, resonant baritone audiobook narrator. Slow, warm, measured pace, intimate and natural, like a human storyteller, not robotic."
for v in ("uncle_fu", "ryan", "eric", "dylan", "aiden"):
    sf.write(out / f"custom_{v}.wav", tts.speak(T, v, DEEP), tts.SR); print(v, flush=True)

from mlx_audio.tts.utils import load_model
d = load_model(model_path="mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-bf16")
import numpy as np
for i, desc in enumerate([
    "A man in his fifties with a very deep, rich, gravelly baritone, a seasoned audiobook narrator, slow and warm, natural breathing, subtle dry humor.",
    "A deep bass-baritone male voice, smooth and cinematic like a documentary narrator, calm, unhurried, intimate.",
]):
    a = np.concatenate([np.array(r.audio) for r in d.generate(text=T, instruct=desc, lang_code="en", verbose=False)])
    sf.write(out / f"design_{i+1}.wav", a, tts.SR); print("design", i + 1, flush=True)
