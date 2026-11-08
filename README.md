# Audiocast

Turn an ebook into a full-cast audiobook, entirely on your own machine.

Upload an EPUB, PDF or TXT. A local LLM labels every line (who speaks, how they feel, where to pause, what mood the scene has). Each character gets their own voice, the narrator gets a narrator voice, and optional background music and sound effects are mixed in. A companion Android app syncs the finished chapters over your LAN and plays them.

Nothing leaves your computer except an optional Wikipedia lookup of title and author (never book text).

## How it works

```mermaid
flowchart LR
    subgraph PC["Your computer (Apple Silicon)"]
        UI["Web UI<br/>app/static/index.html"]
        API["FastAPI server<br/>app/main.py :8000"]
        BOOKS["Book parser<br/>app/books.py"]
        ANN["Script annotator<br/>app/annotate.py"]
        LLM[("LM Studio :1234<br/>local LLM")]
        TTS["Voice casting + TTS<br/>app/tts.py"]
        VOX["VoxCPM2 worker<br/>app/vox_worker.py"]
        MUS["Music beds<br/>app/music.py (MusicGen)"]
        SFX["Sound effects<br/>app/sfx.py (AudioLDM)"]
        MIX["Chapter mix<br/>voice + music + sfx"]
        DATA[("data/ book folders<br/>script.json, lines/, audio")]
        SYNC["Sync service<br/>app/sync.py (LAN, mDNS)"]
        WIKI["Optional lookup<br/>app/lookup.py"]
    end
    PHONE["Android app<br/>Library, offline playback,<br/>resume position"]

    UI -->|"upload / queue jobs"| API
    API --> BOOKS
    BOOKS -->|"chapters"| DATA
    API --> ANN
    ANN <-->|"label segments"| LLM
    ANN -->|"script.json"| DATA
    API --> TTS
    TTS --> VOX
    TTS --> MUS
    TTS --> SFX
    VOX --> MIX
    MUS --> MIX
    SFX --> MIX
    MIX -->|"chapter audio"| DATA
    API -.->|"title, author only"| WIKI
    DATA --> SYNC
    SYNC <-->|"pair token, download, positions"| PHONE
```

### Pipeline

1. **Parse** (`app/books.py`): EPUB spine, PDF or TXT becomes chapters. PDF text is reflowed (page numbers removed, hyphens joined, paragraphs rebuilt).
2. **Annotate** (`app/annotate.py`): code splits each chapter into numbered narration and quote segments, so the book text can never be altered or dropped. The LLM only labels each segment id with speaker, emotion, pause and mood. Six LLM stages run per chapter, then emphasis and sound-effect passes. Chapters are framed with "Chapter N." and "End of chapter N."
3. **Cast** (`app/tts.py`): new characters get a designed voice; voices are reused across chapters of the same book. You can merge characters, redesign a voice or edit the script by hand.
4. **Render**: each line is spoken with VoxCPM2 (in its own virtualenv, as a long-lived worker process) and cached per line, so a crashed render resumes.
5. **Mix**: same-mood lines become music cues (MusicGen clips, loudness-matched, ducked under speech); sound effects (AudioLDM) are laid over the voice track.
6. **Sync**: the sync service announces itself over mDNS; the Android app pairs with a token, downloads chapters and uploads your listening position.

## Layout

| Path | What |
|---|---|
| `app/` | FastAPI server and pipeline (`main`, `books`, `annotate`, `tts`, `music`, `sfx`, `sync`, `lookup`, `vox_worker`) |
| `app/static/index.html` | Web UI (library, chapter table, script editor, cast, job queue) |
| `android/` | Kotlin / Compose player app with sync |
| `scripts/` | One-off helpers: model download, sample renders, chapter builder |
| `tests/` | pytest suite (parsing, annotation splitter, TTS cache, music, sfx, API, sync) |
| `BUILD_LOG.md` | Dated log of every build step, failures included |

## Requirements

- macOS on Apple Silicon (models run on MPS / MLX); 64 GB RAM recommended
- Python 3.12, [uv](https://github.com/astral-sh/uv), ffmpeg, espeak-ng
- [LM Studio](https://lmstudio.ai) serving a capable instruct model on `:1234` (developed with Qwen 27B)
- Android Studio / Gradle for the phone app

## Setup

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv fastapi uvicorn python-multipart ebooklib beautifulsoup4 lxml pypdf \
    openai pydub soundfile numpy scipy pytest httpx zeroconf mlx-audio torch
brew install ffmpeg espeak-ng

# VoxCPM2 lives in its own environment so its torch/transformers cannot clash
uv venv --python 3.12 .venv-voxcpm
uv pip install --python .venv-voxcpm voxcpm
```

Model weights download from Hugging Face on first use (VoxCPM2 takes about 2 minutes to load).

## Run

```sh
.venv/bin/uvicorn app.main:app --port 8000
```

Open http://localhost:8000, upload a book, analyze chapters, tick the ones you want and queue script or audio renders. Pairing details for the phone are at `GET /api/sync/pairing`.

## Test

```sh
.venv/bin/pytest tests
```

The live LLM test needs LM Studio running and is skipped otherwise.

## Known limits

- Audio quality and music fit are judged by ear; there is no automatic check beyond a Whisper round-trip on sample chapters.
- A 20 s music clip per mood is looped, so long scenes can audibly repeat.
- Annotation is slow on large local models (roughly minutes per chapter).
- `book/`, `data/` and `samples/` are git-ignored: bring your own books, and mind their copyright.

## License

See `LICENSE`.
