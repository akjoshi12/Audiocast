"""Round 2: 'deep, warm, gravitas' narrator voices built from descriptions (no real-person imitation)."""
import numpy as np, soundfile as sf
from pathlib import Path
from mlx_audio.tts.utils import load_model
from app import tts

T = ("I’m pretty much screwed. That’s my considered opinion. Screwed. "
     "Six days in to what should be a greatest two months of my life, and it’s turned in to a nightmare. "
     "I don’t even know who’ll read this. I guess someone will find it eventually.")
out = Path("samples/narrator2"); out.mkdir(exist_ok=True)
D = {
 "a_warm_elder": "An elderly man with an extremely deep, warm, smooth bass voice, wise and calm, unhurried, with great gravitas, like a beloved storyteller. Speaks slowly with rich resonance and gentle pauses.",
 "b_gravelly": "A deep gravelly baritone, weathered and rich, slow and deliberate, intimate and authoritative, American accent, a voice that makes every sentence sound important.",
 "c_indian_english": "A man with a very deep, commanding, resonant baritone and a subtle Indian English accent, calm and powerful, measured pace, dramatic gravitas, like an epic narrator.",
 "d_cinematic_bass": "A very low bass voice, cinematic and booming yet soft and close to the microphone, slow, dramatic, every word weighty, British-neutral accent.",
}
m = load_model(model_path="mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-bf16")
for k, desc in D.items():
    a = np.concatenate([np.array(r.audio) for r in m.generate(text=T, instruct=desc, lang_code="en", speed=0.92, verbose=False)])
    sf.write(out / f"{k}.wav", a, tts.SR); print(k, f"{len(a)/tts.SR:.1f}s", flush=True)
