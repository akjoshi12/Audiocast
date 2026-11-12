"""Download TTS weights into the HF cache (skips anything already complete)."""
from huggingface_hub import snapshot_download

REPOS = [
    "mlx-community/Kokoro-82M-bf16",
    "mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-bf16",
    "mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-6bit",
]
for r in REPOS:
    print("->", r, flush=True)
    print(snapshot_download(r), flush=True)
