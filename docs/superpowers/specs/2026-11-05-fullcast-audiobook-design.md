# Full-Cast Local Audiobook Generator: Design

Status: DRAFT, awaiting approval. Nothing is built until this is approved.
Items marked **[my call]** are my defaults, not things you decided. Change any of them.

## 1. Intent

Upload a book you own (EPUB/PDF/TXT) and get a full-cast audiobook: a different voice per character, a narrator, natural pauses, emotional delivery, and background music where it fits. Everything runs locally. No cloud APIs, no book text leaves the machine.

## 2. Goals

- Upload a book in a browser, get chapter-split audio out (MP3/M4B with chapter marks).
- Auto-detect characters and who speaks each line.
- Voice picker per character from multiple local voice models, with a preview button.
- Emotion and pacing per line (calm, angry, whispering, etc.), plus pauses between lines, paragraphs and scenes.
- Optional background music per scene/mood, ducked under speech.
- Review step: user can fix speaker attribution and voice casting before the expensive render.
- Resumable: a crash or restart mid-book doesn't lose finished lines.

## 3. Non-goals

- Cloud sync, accounts, multi-user, sharing/distribution of generated audio.
- Real-time streaming playback while generating.
- Training new voice models.
- Sound effects (footsteps, doors). Music beds only.
- Windows/Linux support in v1 **[my call]** (you're on macOS; code stays portable, just untested).

## 4. Anti-goals (failure even if it "works")

- Robotic monotone voices, or the narrator voice reading dialogue.
- Wrong speaker on many lines with no way to fix it.
- Music drowning speech.
- Hours of render lost to one failure.
- Any network call during processing (model downloads on first setup excepted).

## 5. Constraints

- Local only, Python, web UI.
- Apple Silicon Mac (macOS, `darwin`). Heavy models should use MPS/CPU; a full novel will take hours to render. Expected and acceptable **[my call]**.
- Only books the user owns; DRM-protected files are not supported (no DRM removal).
- Licensing: prefer permissive models. XTTS-v2 is non-commercial, so personal use only if added.

## 6. Architecture **[my call, all of it]**

```
upload -> extract chapters -> script annotation (local LLM) -> review/casting UI
       -> TTS per line -> assemble (pauses, music, ducking) -> export m4b/mp3
```

| Stage | Choice | Why |
|---|---|---|
| Web | FastAPI + one HTML page (htmx/vanilla JS) | No JS build step |
| Book parsing | `ebooklib` + `beautifulsoup4` (EPUB), `pypdf` (PDF), plain TXT | Light, standard |
| Script annotation | Local LLM via Ollama (e.g. Qwen2.5 7B/Llama 3.1 8B), JSON output per chapter chunk | Speaker + emotion + scene mood need language understanding; regex can't do it |
| TTS (default) | **Kokoro-82M**: fast, Apache-2.0, ~50 distinct voices, good on CPU/MPS | Many voice options, practical speed |
| TTS (expressive, optional) | **VoxCPM2**: voice cloning from a short sample, written delivery direction | Real emotion; slower |
| Engine interface | Small `synthesize(text, voice, emotion) -> wav` function per engine | Lets the user pick per character |
| Music | Local **MusicGen-small** generates mood beds (tense, calm, sad, epic...), cached; user can also drop their own loops into `music/<mood>/` which take priority | Local, no licensing issues for own files |
| Assembly | `pydub` + `ffmpeg` | Pauses, crossfades, ducking |
| State | One folder per book + SQLite (`lines`, `characters`, `jobs`) | Resumable, inspectable |
| Jobs | Background thread + progress polling | One user, no queue infra needed |

Emotion handling: Kokoro has no emotion knob, so emotion maps to speed, pause length and voice style where possible. True emotional range comes from VoxCPM2 (cloned voices) and Qwen3-TTS. Honest limitation: Kokoro-only output will be well-paced but emotionally mild.

## 7. User flow

1. **Upload**: pick file, see detected chapters.
2. **Analyze**: LLM produces per-line speaker, emotion, pause hints, scene mood. Progress bar.
3. **Cast**: table of characters (narrator included) with line counts. Voices are already auto-assigned (narrator gets a narrator-style voice, no duplicate voices among main characters where avoidable). Each row has an optional voice dropdown, engine choice, and a preview button to override.
4. **Review**: scrollable script; click a line to change speaker/emotion; re-render a single line.
5. **Render**: per-line TTS, then assembly. Resumable; finished lines skipped.
6. **Export**: per-chapter MP3 or single M4B with chapter marks; in-browser player.

## 8. Pauses and music rules **[my call]**

- Pauses: comma/sentence/paragraph/scene defaults (e.g. 0.25 / 0.5 / 0.9 / 2.0 s), scaled by LLM hints ("dramatic pause").
- Music: starts on scene change, fades in/out 2 s, plays at about -22 dB, ducks a further -10 dB under speech. Off by default per book, toggle on; "none" is a valid mood.

## 9. Success criteria

- A short public-domain test book (e.g. a few chapters of *Pride and Prejudice* EPUB) goes upload to listenable M4B with at least 3 distinct character voices.
- Speaker attribution is correct on most dialogue lines, and every error is fixable in the review step.
- Killing the process mid-render and restarting loses at most one line.
- No outbound network traffic during analysis/render.

## 10. Risks

- Speaker attribution quality depends on the local LLM; long-range pronoun cases ("he said") will miss sometimes. Review UI is the mitigation.
- Render time: roughly real-time-or-slower on a laptop for VoxCPM2; Kokoro much faster.
- Model download sizes (several GB total) on first setup.
- Dependency friction (PyTorch, espeak-ng, ffmpeg) on macOS; setup script will check and report.

## 11. Left to the builder

Exact LLM prompt/chunking, UI styling, DB schema details, voice auto-suggestion heuristics, music prompt wording.

## 12. Build process

Work is logged in `BUILD_LOG.md` (project root), one dated entry per step: what was done, decisions, commands run, results, failures. Built in thin vertical slices: (1) upload + chapter extraction, (2) Kokoro single-voice render, (3) LLM speaker annotation, (4) casting UI + multi-voice, (5) pauses/emotion, (6) music, (7) VoxCPM2 clones + export polish. A short check runs at each slice.

## 13. Decided by you

- Voices are **auto-assigned by default**: every character gets a suitable voice picked automatically (from gender/age/personality hints the LLM extracts), and the narrator gets a dedicated narrator-style voice. The user can change any voice afterwards, but never has to.
- Machine: Mac with **64 GB RAM**.

## 14. Consequences of 64 GB RAM **[my call]**

- Can run a larger local LLM for better speaker attribution: ~14B-32B class (e.g. Qwen2.5 32B at 4-bit, about 20 GB) instead of 7B.
- Kokoro and VoxCPM2 can both stay loaded alongside the LLM; no model swapping.
- Model weights total roughly 30 GB on disk; setup script checks free disk space.

## 15. Revisions after approval (2026-11-05)

Spec approved by the user with these changes:

- **LLM runtime is LM Studio, not Ollama.** It is already installed and running at `http://localhost:1234/v1` (OpenAI-compatible) with `qwen/qwen3.8-27b` loaded. The app uses that; no new LLM download.
- **Full emotion from day one.** Kokoro-first is dropped. Expressive engines are primary; Kokoro stays only as a fast "draft preview" option. Slower render is accepted.
- **Music must be correct, not just present.** Quality over speed: the LLM tags each scene with mood, intensity and start/end; MusicGen generates per scene (medium model, not small, if it fits); a verification pass checks the cue list against the script before rendering; the user can audition and swap any cue.
- **Reuse before download.** Already present: ffmpeg, uv, LM Studio, Python 3.12/3.13, and the model weights in the HF cache (Qwen3-TTS VoiceDesign and CustomVoice, Kokoro, MusicGen-small, Whisper). Installed in this project: mlx-audio, espeak-ng. Still not installed: torch and audiocraft (MusicGen via PyTorch; to be handled at the music slice, with an mlx route tried first).

TTS engines (revised) **[my call]**:
- **Qwen3-TTS (VoiceDesign + CustomVoice)**: instruction-driven voice and emotion ("angry, clipped, low voice"); lets each character's voice be designed from a text description, and gives the auto-assigned voices.
- **VoxCPM2**: voice cloning with a written delivery direction (runs in its own virtualenv).
- **Kokoro (MLX)**: fast draft only.
- Runtime: `mlx-audio` on Apple Silicon (native, fast). Verified at slice 2; if an engine fails, fall back to the PyTorch version and log it.
