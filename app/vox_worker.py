"""Runs inside .venv-voxcpm (its own torch/transformers, so it cannot clash with the app's packages).
Reads one JSON per line {text, ref, out}, writes a wav at the model's rate, answers one JSON line. stdout is the protocol; library noise goes to stderr."""
import json
import sys
import traceback

proto, sys.stdout = sys.stdout, sys.stderr
import numpy as np
import soundfile as sf
from voxcpm import VoxCPM

m = VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False, optimize=False, device="mps")
sr = m.tts_model.sample_rate
print(json.dumps({"ready": sr}), file=proto, flush=True)
for line in sys.stdin:
    j = json.loads(line)
    try:
        sf.write(j["out"], np.asarray(m.generate(text=j["text"], reference_wav_path=j["ref"], cfg_value=2.0, inference_timesteps=10), dtype=np.float32), sr)
        r = {"ok": True, "sr": sr}
    except Exception as e:  # one bad line must not kill the render
        traceback.print_exc()   # to server.log: the reply below only carries the message
        r = {"ok": False, "err": repr(e)}
    print(json.dumps(r), file=proto, flush=True)
