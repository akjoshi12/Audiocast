import hashlib
import re
from collections import Counter
import random
import io
import json
import subprocess
import threading
import uuid
from pathlib import Path

import numpy as np
import soundfile as sf
from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel

from app import annotate, lookup, music, sfx, sync, tts
from app.books import extract_chapters, guess_details

DATA = Path(__file__).resolve().parent.parent / "data"
MUSIC_CACHE = DATA / "music_cache"
app = FastAPI(title="Full-Cast Audiobook")


@app.on_event("startup")
def _start_phone_sync():
    sync.start()


@app.get("/api/sync/pairing")
def pairing():
    import segno
    url = sync.pairing_url()
    return {"url": url, "svg": segno.make(url).svg_inline(scale=6, dark="#fff", light=None)}
LOCK = threading.Lock()   # ponytail: one heavy model job at a time (analyze / render / preview); queue if multi-user
JOBS: dict[str, dict] = {}


def _dir(book_id: str, n: int | None = None) -> Path:
    d = DATA / book_id
    if not (d / "chapters.json").exists():
        raise HTTPException(404, "unknown book")
    return d if n is None else d / f"ch{n:02d}"


def _chapters(book_id: str) -> list[dict]:
    return json.loads((_dir(book_id) / "chapters.json").read_text())


class Cancelled(Exception):
    pass


QUEUE: list[tuple[str, object]] = []   # waiting jobs (key, fn)
COND = threading.Condition()
_last = [None]


def _kind(key: str) -> str:
    return key.split(":")[2]


def _run(key: str, fn):
    try:
        with LOCK:
            JOBS[key].update(state="running", msg="working")

            def tick(d, t, msg=""):
                JOBS[key].update(done=d, total=t, msg=msg)
                if JOBS[key].get("cancel"):
                    raise Cancelled
            fn(tick)
        JOBS[key].update(state="done", msg="")
    except Cancelled:  # ponytail: stops at the next chunk boundary, not mid-chunk
        JOBS[key].update(state="cancelled", msg="")
    except Exception as e:  # surfaced to the UI
        JOBS[key].update(state="error", msg=f"{type(e).__name__}: {e}")


def _worker():
    """One job at a time. Keeps going with the same kind (all scripts, then all audio) so the text model and the
    voice models aren't swapped in and out between jobs."""
    while True:
        with COND:
            while not QUEUE:
                COND.wait()
            key, fn = QUEUE.pop(next((i for i, (k, _) in enumerate(QUEUE) if _kind(k) == _last[0]), 0))
        _last[0] = _kind(key)
        _run(key, fn)


threading.Thread(target=_worker, daemon=True).start()


def _job(key: str, fn):
    with COND:
        if JOBS.get(key, {}).get("state") in ("queued", "running"):
            return JOBS[key]
        JOBS[key] = {"state": "queued", "done": 0, "total": 1, "msg": "waiting in line"}
        QUEUE.append((key, fn))
        COND.notify()
    return JOBS[key]


@app.get("/api/queue")
def queue_status():
    out = []
    for key, j in JOBS.items():
        if j["state"] in ("queued", "running"):
            book_id, n, kind = key.split(":")
            try:
                title = _chapters(book_id)[int(n) - 1]["title"]
            except Exception:
                title = f"chapter {n}"
            try:
                bname = json.loads((DATA / book_id / "meta.json").read_text()).get("name", book_id)
            except Exception:
                bname = book_id
            out.append({"book": book_id, "book_name": bname, "n": int(n), "kind": kind, "title": title, **j})
    return out


@app.post("/api/books/{book_id}/queue/{kind}")
def queue_all(book_id: str, kind: str, ns: str = ""):
    """Line up chapters that need it: 'analyze' = no script yet, 'render' = script but no audio. `ns` ("1,3,4") limits it to those chapters."""
    if kind not in ("analyze", "render"):
        raise HTTPException(404, "kind must be analyze or render")
    todo, skipped = [], []
    pick = {int(x) for x in ns.split(",") if x.strip().isdigit()}
    for n in range(1, len(_chapters(book_id)) + 1):
        if pick and n not in pick:
            continue
        d = _dir(book_id, n)
        has_script, has_audio = (d / "script.json").exists(), (d / "chapter.mp3").exists()
        if (kind == "analyze" and not has_script) or (kind == "render" and has_script and not has_audio):
            (analyze if kind == "analyze" else render)(book_id, n)
            todo.append(n)
        else:
            skipped.append(n)
    return {"queued": todo, "skipped": skipped if pick else []}


@app.get("/", response_class=HTMLResponse)
def index():
    return (Path(__file__).parent / "static" / "index.html").read_text()


@app.post("/api/books")
async def upload(file: UploadFile):
    data = await file.read()
    book_id = hashlib.sha1(data).hexdigest()[:8]  # same file -> same book, scripts kept
    folder = DATA / book_id
    if (folder / "chapters.json").exists():
        return book_info(book_id)
    folder.mkdir(parents=True, exist_ok=True)
    src = folder / f"source{Path(file.filename or '').suffix.lower()}"
    src.write_bytes(data)
    try:
        chapters = extract_chapters(src)
    except Exception as e:
        raise HTTPException(400, str(e))
    (folder / "chapters.json").write_text(json.dumps(chapters))
    (folder / "meta.json").write_text(json.dumps({"name": file.filename, **guess_details(src, file.filename or ""), "lookup": False}))
    return book_info(book_id)


@app.get("/api/books")
def list_books():
    return [book_info(p.parent.name) for p in sorted(DATA.glob("*/chapters.json"), key=lambda p: -p.stat().st_mtime)]


@app.get("/api/books/{book_id}")
def book_info(book_id: str):
    d = _dir(book_id)
    meta = json.loads((d / "meta.json").read_text()) if (d / "meta.json").exists() else {}
    about = json.loads((d / "about.json").read_text()) if (d / "about.json").exists() else None
    return {"id": book_id, "name": meta.get("name", book_id), "title": meta.get("title", ""), "author": meta.get("author", ""),
            "cover": bool(list(d.glob("cover.*")) or (d / "source.pdf").exists()),
            "lookup": meta.get("lookup", False), "found": about and {"page": about["page"], "url": about["url"]},
            "chapters": [{"n": i + 1, "title": c["title"], "part": c.get("part", ""), "chars": len(c["text"]),
                          "analyzed": (d / f"ch{i+1:02d}" / "script.json").exists(),
                          "rendered": (d / f"ch{i+1:02d}" / "chapter.mp3").exists()}
                         for i, c in enumerate(_chapters(book_id))]}


COVER_TYPES = {b"\x89PNG": ("png", "image/png"), b"\xff\xd8\xff": ("jpg", "image/jpeg")}


def _cover_file(book_id: str) -> Path | None:
    return sync.cover_file(_dir(book_id))


@app.get("/api/books/{book_id}/cover")
def get_cover(book_id: str):
    f = _cover_file(book_id)
    if not f:
        raise HTTPException(404, "no cover")
    return FileResponse(f, media_type="image/png" if f.suffix == ".png" else "image/jpeg", headers={"Cache-Control": "no-cache"})


@app.put("/api/books/{book_id}/cover")
async def put_cover(book_id: str, request: Request):
    d, body = _dir(book_id), await request.body()
    kind = next((v for k, v in COVER_TYPES.items() if body.startswith(k)), None)
    if not kind or len(body) > 10_000_000:
        raise HTTPException(400, "send a PNG or JPEG image (up to 10 MB)")
    for old in d.glob("cover.*"):
        old.unlink()
    (d / f"cover.{kind[0]}").write_bytes(body)
    return {"ok": True}


class About(BaseModel):
    title: str
    author: str = ""
    lookup: bool = False


@app.put("/api/books/{book_id}/about")
def set_about(book_id: str, body: About):
    """Title/author help the AI recognise a known book. With lookup on, Wikipedia is asked once (title and author only)."""
    d = _dir(book_id)
    meta = json.loads((d / "meta.json").read_text())
    meta.update(title=body.title.strip(), author=body.author.strip(), lookup=body.lookup)
    (d / "about.json").unlink(missing_ok=True)
    if body.lookup and meta["title"]:
        try:
            found = lookup.find(meta["title"], meta["author"])
        except Exception as e:
            raise HTTPException(502, f"Couldn't reach Wikipedia ({type(e).__name__}). Turn the lookup off to continue offline.")
        if found:
            (d / "about.json").write_text(json.dumps(found))
    (d / "meta.json").write_text(json.dumps(meta))
    return book_info(book_id)


def _about(book_id: str) -> str:
    """Prompt text: the book's identity plus any looked-up background, for describing characters the chapter leaves vague."""
    d = _dir(book_id)
    meta = json.loads((d / "meta.json").read_text()) if (d / "meta.json").exists() else {}
    if not meta.get("title"):
        return ""
    out = f"Book: {meta['title']}" + (f" by {meta['author']}" if meta.get("author") else "") + ".\n"
    if (d / "about.json").exists():
        out += "Background from Wikipedia (may be incomplete; use it only for facts about the characters):\n" + json.loads((d / "about.json").read_text())["text"] + "\n\n"
    return out


def _aliases(book_id: str) -> dict:
    f = DATA / book_id / "aliases.json"
    return json.loads(f.read_text()) if f.exists() else {}


SPEECH_VERB = r"(?:said|asked|answered|replied|cried|remarked|added|exclaimed|returned|continued|whispered|murmured|shouted|observed|" \
              r"ventured|suggested|inquired|rejoined|laughed|muttered|stammered|interrupted|retorted|responded|called|groaned)"


def first_person_narrator(lines: list[dict]) -> str | None:
    """In a story told as "I", the narrator and one character are the same person. That character is the one whose quotes sit next to
    the narration tags "I said," / "I answered." (needs 3 such tags and a clear lead over the runner-up)."""
    n = Counter()
    for a, b in zip(lines, lines[1:]):
        for q, t in ((a, b), (b, a)):
            if q["kind"] == "speech" and t["kind"] == "narration" and q["speaker"] != "Narrator" and re.match(rf"I\s+{SPEECH_VERB}\b", t["text"].strip()) and len(t["text"].split()) <= 10:
                n[q["speaker"]] += 1
    top = n.most_common(2)
    return top[0][0] if top and top[0][1] >= 3 and (len(top) == 1 or top[0][1] >= 1.5 * top[1][1]) else None


def _apply_aliases(book_id: str, s: dict) -> dict:
    """Names the user merged earlier ("Watson" -> "John Watson") are renamed in a freshly labelled chapter."""
    al = _aliases(book_id)
    me = first_person_narrator(s["lines"])
    if me and al.get(me) != "Narrator":  # "Watson" and "John Watson" are the same person as well
        mine = set(me.lower().split())
        for c in s["characters"]:
            if c["name"] == me or (set(c["name"].lower().split()) <= mine or mine <= set(c["name"].lower().split())):
                al[c["name"]] = "Narrator"
        (DATA / book_id / "aliases.json").write_text(json.dumps(al))
    if not al:
        return s
    for l in s["lines"]:
        l["speaker"] = al.get(l["speaker"], l["speaker"])
    seen, chars = set(), []
    for c in s["characters"]:
        c = {**c, "name": al.get(c["name"], c["name"])}
        if c["name"] not in seen and c["name"] != "Narrator":  # the narrator needs no designed voice
            seen.add(c["name"]); chars.append(c)
    return {**s, "characters": chars}


def _cast_file(book_id: str) -> Path:
    return DATA / book_id / "cast.json"


def _book_cast(book_id: str) -> dict:
    f = _cast_file(book_id)
    return json.loads(f.read_text()) if f.exists() else {}


def _design(book_id: str, c: dict, k: int, hint: dict | None = None) -> dict:
    """New wav (fresh file name, so cached lines of an old voice are not reused) + its cast entry."""
    prompt = tts.voice_prompt(c, k, hint)
    wav = DATA / book_id / "voices" / f"{uuid.uuid4().hex[:8]}.wav"
    tts.design_voice(prompt, wav)
    return {"voice": "clone:" + str(wav.relative_to(tts.ROOT)), "desc": prompt, "traits": c.get("voice", ""), "gender": c.get("gender", "unknown"),
            "age": c.get("age", "unknown"), "guessed": c.get("gender") not in ("male", "female") or not c.get("voice"), "pitch": tts.ref_pitch(wav)}


@app.post("/api/books/{book_id}/chapters/{n}/analyze")
def analyze(book_id: str, n: int):
    ch = _chapters(book_id)[n - 1]
    out = _dir(book_id, n)

    def work(progress):
        last = [0, 1]

        def annotate_tick(d, t, msg=""):
            last[:] = [d, t]
            progress(d, t, msg)
        annotate.ensure_loaded()
        s = annotate.annotate_chapter(ch["text"], progress=annotate_tick, about=_about(book_id))
        out.mkdir(parents=True, exist_ok=True)
        s = _apply_aliases(book_id, s)
        cast = _book_cast(book_id)  # one voice per character for the whole book: only characters not seen before get designed
        new = [c for c in s["characters"] if c["name"] not in cast]
        for i, c in enumerate(new):
            progress(last[0], last[1], f"Designing voice {i + 1} of {len(new)}: {c['name']}")
            k = sum(1 for v in cast.values() if (v["gender"], v["age"]) == (c.get("gender"), c.get("age")))
            cast[c["name"]] = _design(book_id, c, k)
        _cast_file(book_id).write_text(json.dumps(cast, indent=1))
        lines = annotate.frame(ch["title"], s["lines"], ch.get("part", ""))
        (out / "script.json").write_text(json.dumps({
            "title": ch["title"], "characters": s["characters"], "cast": {"Narrator": tts.NARRATOR_VOICE, **{c["name"]: cast[c["name"]]["voice"] for c in s["characters"]}},
            "lines": lines, "music": True, "setting": ""}, indent=1))
    return _job(f"{book_id}:{n}:analyze", work)


@app.get("/api/books/{book_id}/chapters/{n}/script")
def get_script(book_id: str, n: int):
    f = _dir(book_id, n) / "script.json"
    if not f.exists():
        raise HTTPException(404, "not analyzed yet")
    bc = _book_cast(book_id)
    return {**json.loads(f.read_text()), "guessed": [k for k, v in bc.items() if v.get("guessed")], "notes": {k: v.get("notes", "") for k, v in bc.items()},
            "narrator_also": [k for k, v in _aliases(book_id).items() if v == "Narrator"]}


class Script(BaseModel):
    cast: dict[str, str]
    lines: list[dict]
    music: bool = True
    setting: str = ""


@app.put("/api/books/{book_id}/chapters/{n}/script")
def put_script(book_id: str, n: int, body: Script):
    f = _dir(book_id, n) / "script.json"
    old = json.loads(f.read_text())
    # fidelity guard: the UI may change speakers/emotions/pauses, never the book's words
    if [l["text"] for l in body.lines] != [l["text"] for l in old["lines"]]:
        raise HTTPException(400, "line text cannot be edited")
    f.write_text(json.dumps({**old, **body.model_dump()}, indent=1))
    bc = _book_cast(book_id)  # a voice picked here is the character's voice in every chapter
    for name, v in body.cast.items():
        if name in bc and bc[name]["voice"] != v:
            bc[name].update(voice=v, guessed=False)
    if bc:
        _cast_file(book_id).write_text(json.dumps(bc, indent=1))
    return {"ok": True}


class Merge(BaseModel):
    source: str
    into: str


@app.post("/api/books/{book_id}/cast/merge")
def merge_characters(book_id: str, body: Merge):
    """Two names for one person: every line of `source` becomes `into`, in every chapter that has a script, and later chapters
    remember the link. `into` keeps its voice. Audio already generated keeps the old voices until generated again."""
    bc = _book_cast(book_id)
    if body.source == body.into or body.source == "Narrator" or (body.into != "Narrator" and body.into not in bc):
        raise HTTPException(400, "pick a different, existing character to merge into")
    al = {k: (body.into if v == body.source else v) for k, v in _aliases(book_id).items()}
    al[body.source] = body.into
    (DATA / book_id / "aliases.json").write_text(json.dumps(al))
    for f in sorted((DATA / book_id).glob("ch*/script.json")):
        sc = json.loads(f.read_text())
        for l in sc["lines"]:
            if l["speaker"] == body.source:
                l["speaker"] = body.into
        chars = {}
        for c in sc["characters"]:
            name = body.into if c["name"] == body.source else c["name"]
            if name != "Narrator":
                chars.setdefault(name, {**c, "name": name})
        sc["characters"] = list(chars.values())
        if body.source in sc["cast"]:
            sc["cast"].pop(body.source)
            sc["cast"].setdefault(body.into, tts.NARRATOR_VOICE if body.into == "Narrator" else bc[body.into]["voice"])
        f.write_text(json.dumps(sc, indent=1))
    bc.pop(body.source, None)
    _cast_file(book_id).write_text(json.dumps(bc, indent=1))
    return {"ok": True}


@app.delete("/api/books/{book_id}/aliases/{name}")
def remove_alias(book_id: str, name: str):
    """Undo a merge (or an automatic first-person-narrator match) for later chapters. A chapter that already has a script keeps it
    until its script is created again."""
    al = _aliases(book_id)
    al.pop(name, None)
    (DATA / book_id / "aliases.json").write_text(json.dumps(al))
    return {"ok": True}


class Redesign(BaseModel):
    notes: str = ""


@app.post("/api/books/{book_id}/cast/{name}/redesign")
def redesign(book_id: str, name: str, body: Redesign = Redesign()):
    """New voice for one character. With notes ("older, gravelly, Scottish") the notes replace the AI's description; without,
    a random pitch/timbre/pace steers away from the old voice. The pitch is measured and re-rolled (up to 3 times) if it barely moved."""
    bc = _book_cast(book_id)
    if name not in bc:
        raise HTTPException(404, "unknown character")
    old, notes = bc[name], body.notes.strip() or bc[name].get("notes", "")
    old_pitch = old.get("pitch") or tts.ref_pitch(tts.ROOT / old["voice"][6:]) if old["voice"].startswith("clone:") else 0
    avoid = old.get("hint")
    with LOCK:
        for _ in range(3):
            hint = None if notes else tts.contrast(avoid)
            new = _design(book_id, {"gender": old["gender"], "age": old["age"], "voice": notes or old.get("traits", "")}, random.randrange(len(tts.VARIETY)), hint)
            if not old_pitch or abs(new["pitch"] - old_pitch) >= 12:
                break
    bc[name] = {**new, "traits": old.get("traits", ""), "notes": notes, "hint": hint, "guessed": False}
    _cast_file(book_id).write_text(json.dumps(bc, indent=1))
    return {**bc[name], "old_pitch": old_pitch}


@app.get("/api/voices")
def voices(book: str = ""):
    designed = [{"id": v["voice"], "label": f"{n} (designed for this book)"} for n, v in _book_cast(book).items()] if book else []
    return [{"id": tts.NARRATOR_VOICE, "label": "Deep narrator (cloned) - default narrator"}] + designed + \
           [{"id": v, "label": f"{v} ({g})"} for g, vs in tts.VOICES.items() for v in vs]


class Preview(BaseModel):
    voice: str
    emotion: str = "calm"
    text: str = "I never thought I would see you again, not after everything that happened."


@app.post("/api/preview")
def preview(p: Preview):
    with LOCK:
        audio = tts.speak(p.text, p.voice, p.emotion)
    buf = io.BytesIO()
    sf.write(buf, audio, tts.SR, format="WAV")
    return Response(buf.getvalue(), media_type="audio/wav")


@app.post("/api/books/{book_id}/chapters/{n}/render")
def render(book_id: str, n: int):
    out = _dir(book_id, n)
    if not (out / "script.json").exists():
        raise HTTPException(404, "not analyzed yet")

    def work(progress):
        script = json.loads((out / "script.json").read_text())
        wav = tts.render(script["lines"], script["cast"], out, progress=progress)
        audio = sf.read(wav, dtype="float32")[0]
        sp = tts.spans(script["lines"], script["cast"], out)
        if script.get("music"):
            cues = music.cues(script["lines"], sp)
            (out / "cues.json").write_text(json.dumps(cues))
            audio = music.mix(audio, sp, cues, MUSIC_CACHE, script.get("setting", ""))
        if script.get("sfx", True):   # sound effects named in the text (a knock, a bark); lines carry them from the analysis
            audio = sfx.add(audio, script["lines"], sp, DATA / "sfx_cache")
        sf.write(out / "final.wav", audio, tts.SR)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(out / "final.wav"), "-codec:a", "libmp3lame",
                        "-q:a", "2", str(out / "chapter.mp3")], check=True)
    return _job(f"{book_id}:{n}:render", work)


@app.post("/api/jobs/{book_id}/{n}/{kind}/cancel")
def job_cancel(book_id: str, n: int, kind: str):
    key = f"{book_id}:{n}:{kind}"
    j = JOBS.get(key)
    if j and j["state"] in ("queued", "running"):
        j["cancel"] = True
        with COND:
            if j["state"] == "queued":
                QUEUE[:] = [q for q in QUEUE if q[0] != key]
                j.update(state="cancelled", msg="")
    return {"ok": True}


@app.get("/api/jobs/{book_id}/{n}/{kind}")
def job_status(book_id: str, n: int, kind: str):
    return JOBS.get(f"{book_id}:{n}:{kind}", {"state": "idle", "done": 0, "total": 1, "msg": ""})


@app.get("/api/books/{book_id}/chapters/{n}/audio")
def audio(book_id: str, n: int):
    f = _dir(book_id, n) / "chapter.mp3"
    if not f.exists():
        raise HTTPException(404, "not rendered yet")
    return FileResponse(f, media_type="audio/mpeg", filename=f"chapter_{n:02d}.mp3")
