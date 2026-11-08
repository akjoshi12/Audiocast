"""python -m scripts.make_chapter <book-file> <chapter-number> [out-dir]
Annotate (cached in script.json) -> auto-cast -> render one announced chapter to chapter.wav."""
import json
import sys
import time
from pathlib import Path

from app import annotate, books, tts

book, n = Path(sys.argv[1]), int(sys.argv[2])
out = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("samples") / book.stem.split(" - ")[0].replace(" ", "_") / f"ch{n:02d}"
out.mkdir(parents=True, exist_ok=True)

chapters = books.extract_chapters(book)
ch = chapters[n - 1]
script = out / "script.json"
t0 = time.time()
if script.exists():
    data = json.loads(script.read_text())
else:
    s = annotate.annotate_chapter(ch["text"])
    data = {"title": ch["title"], "cast": tts.auto_cast(s["characters"]), "characters": s["characters"],
            "lines": annotate.frame(ch["title"], s["lines"])}
    script.write_text(json.dumps(data, indent=1))
print(f"script ready: {len(data['lines'])} lines, cast {data['cast']} ({time.time()-t0:.0f}s)", flush=True)
wav = tts.render(data["lines"], data["cast"], out)
print("done", wav, f"({time.time()-t0:.0f}s total)", flush=True)

# music: group scene moods into cues, generate beds, duck under speech
import soundfile as sf
from app import music
voice, _ = sf.read(wav, dtype="float32")
sp = tts.spans(data["lines"], data["cast"], out)
cue_list = music.cues(data["lines"], sp)
print("music cues:", [(c["mood"], round(c["start"]), round(c["end"])) for c in cue_list], flush=True)
sf.write(out / "chapter_music.wav", music.mix(voice, sp, cue_list, Path("samples/music"), data.get("setting", "")), tts.SR)
print("done with music", out / "chapter_music.wav", f"({time.time()-t0:.0f}s total)", flush=True)
