"""One neutral and one angry sample per CustomVoice speaker, to judge gender/quality by ear."""
from pathlib import Path

import soundfile as sf

from app import tts

out = Path("samples/voices"); out.mkdir(parents=True, exist_ok=True)
for v in sum(tts.VOICES.values(), []):
    for emo in ("calm", "furious, shouting"):
        sf.write(out / f"{v}_{emo.split(',')[0]}.wav",
                 tts.speak("I never thought I would see you again, not after what happened.", v, emo), tts.SR)
        print(v, emo, flush=True)
