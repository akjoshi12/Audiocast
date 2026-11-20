"""Runs in .venv-tango (its own environment): reads [{"prompt", "seconds", "out"}] as JSON on stdin and writes a mono 44.1 kHz wav per job.
One process per render, so the model loads once and is freed afterwards."""
import json
import sys

import numpy as np
import soundfile as sf
from tangoflux import TangoFluxInference

import torch
import diffusers.models.transformers.transformer_flux as tf

# diffusers' rope() asks for float64, which Apple's GPU (MPS) cannot do: do that small step on the CPU, return float32 on the GPU.
_rope = tf.rope
tf.rope = lambda pos, dim, theta: _rope(pos.cpu(), dim, theta).to(pos.device)
DEVICE = "mps" if torch.backends.mps.is_available() else "cpu"   # measured: ~12 s per clip on MPS vs ~34 s on CPU (M4 Max)
m = TangoFluxInference(name="declare-lab/TangoFlux", device=DEVICE)
for j in json.load(sys.stdin):
    a = m.generate(j["prompt"], steps=50, duration=j["seconds"])
    a = a.cpu().numpy() if hasattr(a, "cpu") else np.asarray(a)
    sf.write(j["out"], (a.mean(0) if a.ndim > 1 else a).astype(np.float32), 44100)
    print(j["prompt"], flush=True)
