import time

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

from app import main, tts
from tests.test_upload import make_epub

FAKE = {"characters": [{"name": "Anna", "gender": "female", "age": "adult", "voice": "x"}],
        "units": [], "lines": [
            {"kind": "narration", "speaker": "Narrator", "text": "It rained.", "emotion": "calm", "pause_after": 0.3, "mood": "tense", "unsure": False},
            {"kind": "speech", "speaker": "Anna", "text": "Go home.", "emotion": "firm", "pause_after": 0.3, "mood": "tense", "unsure": True}]}


def wait(c, bid, n, kind):
    for _ in range(100):
        s = c.get(f"/api/jobs/{bid}/{n}/{kind}").json()
        if s["state"] != "running":
            return s
        time.sleep(0.05)
    raise AssertionError("job stuck")


def test_full_flow(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DATA", tmp_path / "data")
    monkeypatch.setattr(main, "MUSIC_CACHE", tmp_path / "mc")
    monkeypatch.setattr(main.annotate, "annotate_chapter", lambda text, progress=None, about="": (progress and progress(1, 1)) or FAKE)

    def fake_render(lines, cast, folder, progress=None):
        folder.mkdir(parents=True, exist_ok=True)
        sf.write(folder / "chapter.wav", np.zeros(tts.SR * 4, np.float32), tts.SR)
        progress and progress(len(lines), len(lines))
        return folder / "chapter.wav"
    monkeypatch.setattr(main.tts, "render", fake_render)
    designed = []

    def fake_design(instruct, out):
        designed.append(instruct); out.parent.mkdir(parents=True, exist_ok=True)
        sf.write(out, np.zeros(tts.SR // 10, np.float32), tts.SR); return out
    monkeypatch.setattr(main.tts, "design_voice", fake_design)
    monkeypatch.setattr(main.tts, "ROOT", tmp_path)
    monkeypatch.setattr(main.tts, "spans", lambda lines, cast, folder: [(0.0, 1.0), (1.5, 2.5)])
    monkeypatch.setattr(main.music, "mix", lambda audio, sp, cues, cache, setting="": audio)

    c = TestClient(main.app)
    p = tmp_path / "b.epub"; make_epub(p)
    b = c.post("/api/books", files={"file": ("b.epub", p.read_bytes())}).json()
    bid = b["id"]
    assert [x["analyzed"] for x in b["chapters"]] == [False, False]
    assert c.get(f"/api/books/{bid}/chapters/1/script").status_code == 404

    c.post(f"/api/books/{bid}/chapters/1/analyze")
    assert wait(c, bid, 1, "analyze")["state"] == "done"
    s = c.get(f"/api/books/{bid}/chapters/1/script").json()
    assert s["lines"][0]["text"] == "Chapter one." and s["lines"][-1]["text"] == "End of chapter one."
    assert s["cast"]["Narrator"] == tts.NARRATOR_VOICE and s["cast"]["Anna"].startswith("clone:") and len(designed) == 1
    assert "female" in designed[0] and s["guessed"] == []  # gender and a voice description were given

    # the UI may change speaker/emotion, never the book's words
    ok = {**s, "cast": {**s["cast"], "Anna": "ryan"}}
    ok["lines"][2]["emotion"] = "whispering"
    assert c.put(f"/api/books/{bid}/chapters/1/script", json=ok).status_code == 200
    assert c.get(f"/api/books/{bid}/chapters/1/script").json()["cast"]["Anna"] == "ryan"
    # voices belong to the book: re-analysing keeps the user's pick and designs nothing new
    c.post(f"/api/books/{bid}/chapters/1/analyze"); assert wait(c, bid, 1, "analyze")["state"] == "done"
    assert c.get(f"/api/books/{bid}/chapters/1/script").json()["cast"]["Anna"] == "ryan" and len(designed) == 1
    old = c.get(f"/api/voices?book={bid}").json()
    new = c.post(f"/api/books/{bid}/cast/Anna/redesign").json()["voice"]
    assert len(designed) == 2 and new.startswith("clone:") and any(v["id"] == new for v in c.get(f"/api/voices?book={bid}").json()) and len(old) >= 1
    r = c.post(f"/api/books/{bid}/cast/Anna/redesign", json={"notes": "older and gravelly"}).json()
    assert "older and gravelly" in designed[-1] and "female" in designed[-1] and r["notes"] == "older and gravelly"
    assert "older and gravelly" not in designed[-2]
    c.post(f"/api/books/{bid}/cast/Anna/redesign")  # no notes: the earlier notes are kept
    assert "older and gravelly" in designed[-1]
    assert c.get(f"/api/books/{bid}/chapters/1/script").json()["notes"]["Anna"] == "older and gravelly"
    bad = {**ok, "lines": [dict(l) for l in ok["lines"]]}
    bad["lines"][1]["text"] = "changed words"
    assert c.put(f"/api/books/{bid}/chapters/1/script", json=bad).status_code == 400

    assert c.get(f"/api/books/{bid}/chapters/1/audio").status_code == 404
    c.post(f"/api/books/{bid}/chapters/1/render")
    assert wait(c, bid, 1, "render")["state"] == "done"
    r = c.get(f"/api/books/{bid}/chapters/1/audio")
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg" and len(r.content) > 1000
    assert c.get(f"/api/books/{bid}").json()["chapters"][0]["rendered"] is True


def test_job_error_is_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DATA", tmp_path / "data")
    def boom(text, progress=None, about=""): raise RuntimeError("LM Studio is not running")
    monkeypatch.setattr(main.annotate, "annotate_chapter", boom)
    c = TestClient(main.app)
    p = tmp_path / "b.epub"; make_epub(p)
    bid = c.post("/api/books", files={"file": ("b.epub", p.read_bytes())}).json()["id"]
    c.post(f"/api/books/{bid}/chapters/1/analyze")
    s = wait(c, bid, 1, "analyze")
    assert s["state"] == "error" and "LM Studio" in s["msg"]


def test_list_books(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DATA", tmp_path / "data")
    c = TestClient(main.app)
    assert c.get("/api/books").json() == []
    p = tmp_path / "b.epub"; make_epub(p)
    bid = c.post("/api/books", files={"file": ("b.epub", p.read_bytes())}).json()["id"]
    r = c.get("/api/books")
    assert r.status_code == 200 and [b["id"] for b in r.json()] == [bid]


def test_cancel_stops_job():
    def slow(progress):
        for i in range(50):
            progress(i, 50)
            time.sleep(0.05)
    main.JOBS.pop("cx:1:t", None)
    main._job("cx:1:t", slow)
    c = TestClient(main.app)
    c.post("/api/jobs/cx/1/t/cancel")
    assert wait(c, "cx", 1, "t")["state"] == "cancelled"


def test_same_upload_is_one_book(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DATA", tmp_path / "data")
    c = TestClient(main.app)
    p = tmp_path / "b.epub"; make_epub(p)
    ids = [c.post("/api/books", files={"file": ("b.epub", p.read_bytes())}).json()["id"] for _ in range(2)]
    assert ids[0] == ids[1] and len(c.get("/api/books").json()) == 1


def test_lookup_accepts_only_the_right_page():
    from app import lookup
    text = "Intro of the novel.\n\n== Plot ==\nstuff\n== Characters ==\nSherlock Holmes: detective. Mrs. Hudson: elderly landlady.\n== Reception ==\nok"
    pages = {"The Hound of the Baskervilles": text}

    def fake(**p):
        if p.get("list") == "search":
            return {"query": {"search": [{"title": "Hound (band)"}, {"title": "The Hound of the Baskervilles"}]}}
        return {"query": {"pages": [{"extract": pages[p["titles"]]}]}}
    got = lookup.find("The Hound of the Baskervilles", "Doyle", get=fake)
    assert got["page"] == "The Hound of the Baskervilles" and "elderly landlady" in got["text"] and "Reception" not in got["text"]
    assert lookup.find("Totally Different Title", get=fake) is None


def test_about_roundtrip_and_offline_error(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DATA", tmp_path / "data")
    c = TestClient(main.app)
    p = tmp_path / "b.epub"; make_epub(p)
    bid = c.post("/api/books", files={"file": ("b.epub", p.read_bytes())}).json()["id"]
    monkeypatch.setattr(main.lookup, "find", lambda t, a: {"page": "P", "url": "http://x", "text": "Anna is old."})
    b = c.put(f"/api/books/{bid}/about", json={"title": "T", "author": "A", "lookup": True}).json()
    assert b["title"] == "T" and b["found"]["page"] == "P" and "Anna is old." in main._about(bid) and "Book: T by A." in main._about(bid)
    b = c.put(f"/api/books/{bid}/about", json={"title": "T", "lookup": False}).json()
    assert b["found"] is None and "Anna" not in main._about(bid)

    def offline(t, a): raise OSError("no network")
    monkeypatch.setattr(main.lookup, "find", offline)
    r = c.put(f"/api/books/{bid}/about", json={"title": "T", "lookup": True})
    assert r.status_code == 502 and "Wikipedia" in r.json()["detail"]


def test_merge_characters_rewrites_scripts_and_remembers_alias(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DATA", tmp_path / "data")
    monkeypatch.setattr(main, "MUSIC_CACHE", tmp_path / "mc")
    monkeypatch.setattr(main.tts, "ROOT", tmp_path)
    monkeypatch.setattr(main.tts, "design_voice", lambda i, out: (out.parent.mkdir(parents=True, exist_ok=True), sf.write(out, np.zeros(2400, np.float32), tts.SR), out)[2])
    two = {"characters": [{"name": "Anna", "gender": "female", "age": "adult", "voice": "x"}, {"name": "Ann", "gender": "female", "age": "adult", "voice": "x"}],
           "units": [], "lines": [{**FAKE["lines"][1]}, {**FAKE["lines"][1], "speaker": "Ann"}]}
    monkeypatch.setattr(main.annotate, "annotate_chapter", lambda text, progress=None, about="": two | {"lines": [dict(l) for l in two["lines"]], "characters": [dict(c) for c in two["characters"]]})
    c = TestClient(main.app)
    p = tmp_path / "b.epub"; make_epub(p)
    bid = c.post("/api/books", files={"file": ("b.epub", p.read_bytes())}).json()["id"]
    c.post(f"/api/books/{bid}/chapters/1/analyze"); wait(c, bid, 1, "analyze")
    s = c.get(f"/api/books/{bid}/chapters/1/script").json()
    assert s["cast"]["Anna"] != s["cast"]["Ann"]
    assert c.post(f"/api/books/{bid}/cast/merge", json={"source": "Ann", "into": "Anna"}).status_code == 200
    s = c.get(f"/api/books/{bid}/chapters/1/script").json()
    assert "Ann" not in s["cast"] and {l["speaker"] for l in s["lines"] if l["kind"] == "speech"} == {"Anna"} and [x["name"] for x in s["characters"]] == ["Anna"]
    n = len(list((tmp_path / "data" / bid / "voices").glob("*.wav")))
    c.post(f"/api/books/{bid}/chapters/1/analyze"); wait(c, bid, 1, "analyze")  # same names come back; Ann must not get a new voice
    s = c.get(f"/api/books/{bid}/chapters/1/script").json()
    assert "Ann" not in s["cast"] and len(list((tmp_path / "data" / bid / "voices").glob("*.wav"))) == n
    assert c.post(f"/api/books/{bid}/cast/merge", json={"source": "Anna", "into": "Anna"}).status_code == 400


def test_first_person_narrator_is_detected_and_voiced_as_narrator(tmp_path, monkeypatch):
    from app.main import first_person_narrator
    L = lambda kind, sp, text: {"kind": kind, "speaker": sp, "text": text, "emotion": "calm", "pause_after": 0.3, "mood": "calm", "unsure": False}
    story = [L("speech", "John Watson", "Looking for lodgings,"), L("narration", "Narrator", "I answered."), L("speech", "Holmes", "Indeed."),
             L("narration", "Narrator", "he said."), L("narration", "Narrator", "I cried,"), L("speech", "John Watson", "By Jove!"),
             L("speech", "John Watson", "I should like to meet him,"), L("narration", "Narrator", "I said.")]
    assert first_person_narrator(story) == "John Watson"
    assert first_person_narrator([l for l in story if l["speaker"] != "John Watson"]) is None  # third person: nobody
    # end to end: the narrator's character gets no designed voice and its lines are spoken by the narrator voice
    monkeypatch.setattr(main, "DATA", tmp_path / "data")
    monkeypatch.setattr(main, "MUSIC_CACHE", tmp_path / "mc")
    monkeypatch.setattr(main.tts, "ROOT", tmp_path)
    made = []
    monkeypatch.setattr(main.tts, "design_voice", lambda i, out: (made.append(i), out.parent.mkdir(parents=True, exist_ok=True), sf.write(out, np.zeros(2400, np.float32), tts.SR), out)[3])
    chars = [{"name": n, "gender": "male", "age": "adult", "voice": "x"} for n in ("John Watson", "Watson", "Holmes")]
    fake = {"characters": chars, "units": [], "lines": story * 1}
    monkeypatch.setattr(main.annotate, "annotate_chapter", lambda text, progress=None, about="": {**fake, "lines": [dict(l) for l in story], "characters": [dict(c) for c in chars]})
    c = TestClient(main.app)
    p = tmp_path / "b.epub"; make_epub(p)
    bid = c.post("/api/books", files={"file": ("b.epub", p.read_bytes())}).json()["id"]
    c.post(f"/api/books/{bid}/chapters/1/analyze"); wait(c, bid, 1, "analyze")
    s = c.get(f"/api/books/{bid}/chapters/1/script").json()
    assert set(s["cast"]) == {"Narrator", "Holmes"} and len(made) == 1 and set(s["narrator_also"]) == {"John Watson", "Watson"}
    assert {l["speaker"] for l in s["lines"] if l["text"] == "Looking for lodgings,"} == {"Narrator"}
    assert c.delete(f"/api/books/{bid}/aliases/Watson").status_code == 200
    assert c.get(f"/api/books/{bid}/chapters/1/script").json()["narrator_also"] == ["John Watson"]
    # by hand: merge a character into the narrator
    assert c.post(f"/api/books/{bid}/cast/merge", json={"source": "Holmes", "into": "Narrator"}).status_code == 200
    s = c.get(f"/api/books/{bid}/chapters/1/script").json()
    assert set(s["cast"]) == {"Narrator"} and {l["speaker"] for l in s["lines"]} == {"Narrator"} and [x["name"] for x in s["characters"]] == []


def test_book_cover_upload_and_pdf_first_page(tmp_path, monkeypatch):
    import json
    monkeypatch.setattr(main, "DATA", tmp_path / "data")
    d = tmp_path / "data" / "b1"
    d.mkdir(parents=True)
    (d / "chapters.json").write_text(json.dumps([{"title": "One", "text": "x" * 300}]))
    c = TestClient(main.app)
    assert c.get("/api/books/b1/cover").status_code == 404 and c.get("/api/books/b1").json()["cover"] is False
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 20
    assert c.put("/api/books/b1/cover", content=png).status_code == 200      # a poster the user picked
    r = c.get("/api/books/b1/cover")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png" and r.content == png
    assert c.get("/api/books/b1").json()["cover"] is True
    assert c.put("/api/books/b1/cover", content=b"not an image").status_code == 400


def test_queue_runs_same_kind_together_and_cancel_removes_waiting():
    import threading, time
    gate, ran = threading.Event(), []
    for k in ("q:1:render", "q:2:analyze", "q:3:render", "q:4:analyze"):
        main.JOBS.pop(k, None)
    main._last[0] = "render"
    main._job("q:1:render", lambda p: (gate.wait(5), ran.append(1)))   # holds the worker
    time.sleep(0.2)
    main._job("q:2:analyze", lambda p: ran.append(2))
    main._job("q:3:render", lambda p: ran.append(3))
    main._job("q:4:analyze", lambda p: ran.append(4))
    assert main.JOBS["q:2:analyze"]["state"] == "queued"
    c = TestClient(main.app)
    c.post("/api/jobs/q/4/analyze/cancel")
    assert main.JOBS["q:4:analyze"]["state"] == "cancelled"
    gate.set()
    for _ in range(50):
        if main.JOBS["q:2:analyze"]["state"] == "done": break
        time.sleep(0.1)
    assert ran == [1, 3, 2]   # the other render goes before the script; the cancelled one never runs
