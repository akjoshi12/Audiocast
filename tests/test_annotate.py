"""units()/merge()/frame() are pure; the live tests call LM Studio (skipped if it is down)."""
import re

import pytest

from app.annotate import agreement, annotate_chapter, chunk, frame, merge, number_words, units

TEXT = (
    "The storm had been building all afternoon. Thomas stood at the window, watching the sea.\n\n"
    "\"You said you would be back by dusk,\" said Margaret, her voice barely steady.\n\n"
    "\"The boat was late,\" he answered quietly. \"I am sorry, Maggie.\"\n\n"
    "She threw the letter at his feet. “Sorry? Your brother is dead and you are sorry?”"
)
MESSY = (
    "Mr. Hale called it the 'so-called miracle' and laughed. He didn't believe it.\n\n"
    "— Where were you last night? asked Anna.\n\n"
    "— Out, he said.\n\n"
    "Liar, she thought. He is lying again.\n\n"
    "The sign on the door read \"CLOSED FOR REPAIRS\" and nothing else."
)
strip = lambda s: re.sub(r"[\s\"“”‘’'—–-]+", "", s)


def test_units_lose_nothing_and_keep_hints():
    for text in (TEXT, MESSY):
        us = units(text)
        assert strip("".join(u["text"] for u in us)) == strip(text)
        assert [u["id"] for u in us] == list(range(len(us)))
    us = units(TEXT)
    q = next(u for u in us if u["text"].startswith("You said"))
    assert q["text"] == "You said you would be back by dusk," and q["hint"] == "QUOTED"
    assert us[0]["hint"] == "" and us[0]["text"].endswith("afternoon.")


def test_messy_units():
    us = units(MESSY)
    texts = [u["text"] for u in us]
    assert texts[0].startswith("Mr. Hale called it the")           # abbreviation not split
    assert "so-called miracle" in texts and next(u for u in us if u["text"] == "so-called miracle")["hint"] == "QUOTED"
    assert "He didn't believe it." in texts                         # apostrophe is not a quote
    assert [u["hint"] for u in us if u["text"].startswith(("Where", "Out"))] == ["DASH", "DASH"]
    assert any(u["text"] == "CLOSED FOR REPAIRS" for u in us)
    assert sum(u["para_end"] for u in us) == 5


def test_chunk_splits_at_paragraph_ends_and_keeps_all():
    us = units("\n\n".join(f"Paragraph {i} " + "word " * 50 + "end." for i in range(40)))
    parts = chunk(us, 1000)
    assert len(parts) > 1 and sum(map(len, parts)) == len(us) and all(p[-1]["para_end"] for p in parts)


def test_merge_joins_same_voice_only():
    L = lambda t, sp, pe=False, k="narration": {"id": 0, "text": t, "kind": k, "speaker": sp, "emotion": "calm",
                                               "pause_after": 0.3, "mood": "none", "unsure": False, "para_end": pe}
    out = merge([L("a.", "Narrator"), L("b.", "Narrator", True), L("c.", "Narrator"), L("d.", "Tom", k="speech")])
    assert [l["text"] for l in out] == ["a. b.", "c.", "d."]


def test_split_tags_only_when_prefix_matches():
    from app.annotate import _split_tags
    u = lambda t, sp: {"id": 0, "text": t, "kind": "speech", "speaker": "Anna", "emotion": "curious", "pause_after": 0.3,
                       "mood": "none", "unsure": False, "para_end": True, "spoken_part": sp}
    out = _split_tags([u("Out, he said.", "Out,"), u("Where?", ""), u("Hello there friend", "Goodbye")])
    assert [(x["text"], x["speaker"]) for x in out] == [("Out,", "Anna"), ("he said.", "Narrator"), ("Where?", "Anna"), ("Hello there friend", "Anna")]


def test_parse_compact_labels():
    from app.annotate import parse_labels
    us = [{"id": i, "text": "x", "hint": "", "para_end": pe} for i, pe in [(0, False), (1, False), (2, True), (3, True), (4, True)]]
    reply = """MOOD: Tense
0 N
1 S | Anna | curious, probing
2 N | | tense ~
3 S | Mr. Hale | casual, evasive | Out, ?
MOOD: calm
4 T | Anna | quiet ?
"""
    out = parse_labels(reply, us, "none")
    assert [o["kind"] for o in out] == ["narration", "speech", "narration", "speech", "thought"]
    assert [o["speaker"] for o in out] == ["Narrator", "Anna", "Narrator", "Mr. Hale", "Anna"]
    assert [o["mood"] for o in out] == ["tense"] * 4 + ["calm"]
    assert out[2]["emotion"] == "tense" and out[2]["pause_after"] == 1.5 and out[0]["pause_after"] == 0.3
    assert out[3]["spoken_part"] == "Out," and out[3]["unsure"] and out[4]["emotion"] == "quiet" and out[4]["unsure"]
    assert parse_labels("0 N\n1 N", us, "none") is None          # missing ids -> retry


def test_agreement():
    u = lambda s, k="speech": {"speaker": s, "kind": k}
    a = [dict(u("Anna"), id=0), dict(u("Narrator", "narration"), id=1), dict(u("Tom"), id=2)]
    b = [dict(u("Anna Smith"), id=0), dict(u("Narrator", "narration"), id=1), dict(u("Bob"), id=2)]
    assert agreement(a, b)["ids"] == [2]


def test_frame_and_numbers():
    assert [number_words(n) for n in (1, 13, 20, 26, 101)] == ["one", "thirteen", "twenty", "twenty six", "one hundred one"]
    body = [{"kind": "narration", "speaker": "Narrator", "text": "x", "emotion": "calm", "pause_after": 0.3, "mood": "calm", "unsure": False}]
    ch = frame("Chapter 3", body)
    assert ch[0]["text"] == "Chapter three." and ch[-1]["text"] == "End of chapter three." and ch[1] is body[0]
    assert frame("Opening", body)[0]["text"] == "Preface." and frame("Opening", body)[-1]["text"] == "End of preface."


def test_annotate_live_messy():
    try:
        r = annotate_chapter(MESSY)
    except Exception as e:
        pytest.skip(f"LM Studio unavailable: {e}")
    by = {u["text"]: u for u in r["units"]}
    assert by["so-called miracle"]["speaker"] == "Narrator"          # quotes that are not a voice
    assert by["CLOSED FOR REPAIRS"]["speaker"] == "Narrator"
    out = next(u for t, u in by.items() if t.startswith("Out"))
    assert out["kind"] == "speech" and out["speaker"] != "Narrator"  # voice without quote marks
    assert "said" not in out["text"]                                  # dialogue tag cut off the spoken part
    thought = next(u for t, u in by.items() if t.startswith("Liar"))
    assert thought["kind"] in ("thought", "narration")
    r2 = annotate_chapter(TEXT)
    sp = {u["text"]: u["speaker"] for u in r2["units"]}
    assert any("Margaret" in s for t, s in sp.items() if "dusk" in t)
    assert any("Thomas" in s for t, s in sp.items() if "boat was late" in t)


def test_speaker_label_prefix_not_spoken():
    from app.annotate import _split_tags
    u = {"id": 0, "text": "Interviewer: So you turned?", "kind": "speech", "speaker": "Interviewer", "emotion": "x",
         "pause_after": 0.3, "mood": "none", "unsure": False, "para_end": True, "spoken_part": ""}
    assert _split_tags([u])[0]["text"] == "So you turned?"


def test_fill_moods_never_leaves_story_lines_without_music():
    from app.annotate import fill_moods
    # labeller changed mood once and left gaps: keep its choices, gaps take the next real mood, headings stay silent
    us = [{"kind": "heading", "mood": "none"}, {"kind": "narration", "mood": "none"}, {"kind": "speech", "mood": ""}, {"kind": "narration", "mood": "tense"}, {"kind": "speech", "mood": "none"}]
    fill_moods(us, "text", "m", pick=lambda t, m: "SHOULD NOT BE ASKED")
    assert [u["mood"] for u in us] == ["none", "tense", "tense", "tense", "tense"]
    # labeller gave one mood (or none) for the whole chunk: a dedicated call decides
    for given in ("none", "calm"):
        us = [{"kind": "heading", "mood": "none"}] + [{"kind": "narration", "mood": given} for _ in range(3)]
        fill_moods(us, "text", "m", pick=lambda t, m: "mysterious")
        assert [u["mood"] for u in us] == ["none", "mysterious", "mysterious", "mysterious"]


def test_fix_tags_forces_narrator_and_flows():
    from app.annotate import fix_tags
    mk = lambda t, h, kind, sp, pe=False: {"text": t, "hint": h, "kind": kind, "speaker": sp, "emotion": "x", "pause_after": 0.3, "para_end": pe}
    us = [mk("Look,", "QUOTED", "speech", "Anna"), mk("I answered.", "", "speech", "Anna"),
          mk("Then he left the room and said nothing at all to anyone in the long dark hall of the old house.", "", "narration", "Narrator")]
    fix_tags(us)
    assert us[1]["speaker"] == "Narrator" and us[1]["kind"] == "narration" and us[0]["pause_after"] == 0.15
    us2 = [mk("No.", "QUOTED", "speech", "Anna", pe=True), mk("He said so.", "", "speech", "Bob")]
    fix_tags(us2)
    assert us2[1]["speaker"] == "Bob"  # new paragraph: not a tag


PASSAGE = ('“Looking for lodgings,” I answered.\n\n“That’s a strange thing,” remarked my companion; “you are the second man to-day.”\n\n'
           '“And who was the first?” I asked.\n\n“A fellow at the laboratory.”\n\n“By Jove!” I cried, “I am the very man for him.”\n\n'
           'Young Stamford looked strangely at me. “You don’t know Holmes yet,” he said.\n\n“I should like to meet him,” I said.\n\n'
           '“It is not easy,” he answered with a laugh.\n\n“Yes,” said Stamford, “it is hard.”\n\n“Very well,” I said.')


def _llm_all_watson():
    """What the labeller really did on chapter 1: every quote credited to the narrator-I, tags as narration."""
    us = units(PASSAGE)
    for u in us:
        quoted = u["hint"] == "QUOTED"
        u.update(kind="speech" if quoted else "narration", speaker="John Watson" if quoted else "Narrator",
                 emotion="calm", pause_after=0.3, unsure=False, mood="calm")
    return us


def test_fix_turns_gives_the_other_person_their_own_quotes():
    from app.annotate import fix_turns
    us = _llm_all_watson()
    fix_turns(us)
    who = {u["text"][:12]: u["speaker"] for u in us if u["kind"] == "speech"}
    assert who["Looking for "] == "John Watson" and who["And who was "] == "John Watson" and who["By Jove!"] == "John Watson"
    assert who["That’s a str"] == "Stamford" and who["A fellow at "] == "Stamford"   # "remarked my companion" and a bare reply
    assert who["You don’t kn"] == "Stamford" and who["It is not ea"] == "Stamford"  # "he said" / "he answered"
    assert who["Yes,"] == "Stamford" and who["I should lik"] == "John Watson"
    assert all(u["speaker"] == "Narrator" for u in us if u["kind"] == "narration")


def test_fix_turns_leaves_third_person_books_alone():
    from app.annotate import fix_turns
    us = units("“Hello,” said Anna.\n\n“Hi,” said Bob.")
    for u in us:
        u.update(kind="speech" if u["hint"] == "QUOTED" else "narration", speaker="Anna" if u["hint"] == "QUOTED" else "Narrator", emotion="x", pause_after=0.3, unsure=False, mood="calm")
    fix_turns(us)
    assert [u["speaker"] for u in us if u["kind"] == "speech"] == ["Anna", "Anna"]  # no narrating "I": nothing to infer from


def test_mark_sfx_keeps_only_clean_sounds(monkeypatch):
    import json as _j
    from types import SimpleNamespace as NS
    from app import annotate
    reply = _j.dumps({"lines": [{"id": 0, "sound": "fingers tapping on a wooden table", "at": "start"},
                                {"id": 1, "sound": "", "at": "start"},
                                {"id": 2, "sound": "a dog barking", "at": "sideways"},
                                {"id": 9, "sound": "thunder", "at": "end"}]})
    monkeypatch.setattr(annotate.LLM.chat.completions, "create", lambda **k: NS(choices=[NS(message=NS(content=reply))]))
    ls = [{"text": "He drummed his fingers on the table."}, {"text": "Fine."}, {"text": "A dog barked."}]
    annotate.mark_sfx(ls, "m")
    assert ls[0]["sfx"] == [{"prompt": "fingers tapping on a wooden table", "at": "start"}]
    assert "sfx" not in ls[1]                     # empty sound
    assert ls[2]["sfx"][0]["at"] == "start"       # unknown placement falls back to the start of the line; id 9 is out of range and ignored


def _u(text, kind="narration", emo="calm", pe=False, sp="Narrator"):
    return {"text": text, "kind": kind, "speaker": sp, "emotion": emo, "para_end": pe, "hint": "", "pause_after": 0.3, "mood": "calm", "unsure": False}


def test_fix_emotions_manner_moves_from_tag_to_quote():
    from app.annotate import fix_emotions
    e1 = [_u('"I am gonna burn this,"', "speech", sp="Bob"), _u("he said angrily.", emo="angry", pe=True)]
    fix_emotions(e1)
    assert (e1[0]["emotion"], e1[1]["emotion"]) == ("angrily", "calm")
    e2 = [_u("He said angrily,", emo="furious"), _u('"I am gonna burn this."', "speech", sp="Bob", pe=True)]
    fix_emotions(e2)
    assert (e1[0]["emotion"], e2[0]["emotion"], e2[1]["emotion"]) == ("angrily", "calm", "angrily")
    e3 = [_u('"Come."', "speech", sp="Bob"), _u("she whispered.", pe=True)]
    fix_emotions(e3)
    assert (e3[0]["emotion"], e3[1]["emotion"]) == ("whispering", "calm")
    e4 = [_u('"Come."', "speech", emo="furious, voice shaking", sp="Bob"), _u("he said angrily.", emo="angry", pe=True)]
    fix_emotions(e4)
    assert (e4[0]["emotion"], e4[1]["emotion"]) == ("furious, voice shaking", "calm")


def test_fix_emotions_pure_narration_keeps_emotion():
    from app.annotate import fix_emotions
    us = [_u("The wind howled.", emo="tense", pe=True), _u('"Hi."', "speech", sp="Bob", pe=True)]
    fix_emotions(us)
    assert us[0]["emotion"] == "tense"


def test_fix_emotions_no_false_manner():
    from app.annotate import fix_emotions
    for tag in ("said Lily.", "he said finally.", "said Billy.", "said the elderly man.", "she said, faintly smiling."):
        us = [_u('"Hi."', "speech", sp="Bob"), _u(tag, emo="sad", pe=True)]
        fix_emotions(us)
        assert (us[0]["emotion"], us[1]["emotion"]) == ("calm", "calm"), tag
    us = [_u('"Hi."', "speech", sp="Bob"), _u("She walked slowly to the door.", emo="sad", pe=True)]   # no tag verb: untouched
    fix_emotions(us)
    assert (us[0]["emotion"], us[1]["emotion"]) == ("calm", "sad")
    us = [_u("The room was a furnace of old grievances and dust that nobody had cleaned in years.", emo="tense"), _u('"Hi."', "speech", sp="Bob", pe=True)]
    fix_emotions(us)
    assert us[0]["emotion"] == "tense"   # long non-tag narration in a dialogue paragraph keeps its emotion


def test_fix_emotions_cues():
    from app.annotate import fix_emotions
    for tag, want in (("he angrily said.", "angrily"), ("cried Elizabeth.", "exclaiming"), ("said Sherlock Holmes sharply.", "sharply"),
                      ("cried his wife, impatiently.", "impatiently"), ("returned the King reproachfully.", "reproachfully")):
        us = [_u('"Hi."', "speech", sp="Bob"), _u(tag, pe=True)]
        fix_emotions(us)
        assert us[0]["emotion"] == want, tag


def test_fix_emotions_between_different_speakers():
    from app.annotate import fix_emotions
    us = [_u('"A,"', "speech", sp="Bob"), _u("he said angrily,"), _u('"B."', "speech", sp="Ann", pe=True)]
    fix_emotions(us)
    assert [u["emotion"] for u in us] == ["angrily", "calm", "calm"]


def test_split_tag_then_fix_emotions_then_merge():
    from app.annotate import _split_tags, fix_emotions
    u = _u("Out, he said angrily.", "speech", sp="Bob", pe=True)
    u["spoken_part"] = "Out,"
    us = _split_tags([u])
    fix_emotions(us)
    assert [(x["kind"], x["text"], x["emotion"]) for x in us] == [("speech", "Out,", "angrily"), ("narration", "he said angrily.", "calm")]
    assert len(merge(us)) == 2


def test_fix_emotions_tag_between_two_quotes():
    from app.annotate import fix_emotions
    us = [_u('"A,"', "speech", sp="Bob"), _u("he said angrily,"), _u('"B."', "speech", sp="Bob", pe=True)]
    fix_emotions(us)
    assert [u["emotion"] for u in us] == ["angrily", "calm", "angrily"]


def test_mark_sfx_skips_speech_and_consecutive_lines(monkeypatch):
    import json as _j
    from types import SimpleNamespace as NS
    from app import annotate
    monkeypatch.setattr(annotate, "_preset", lambda: {})
    reply = _j.dumps({"lines": [{"id": i, "sound": "a loud bell ringing", "at": "start"} for i in range(3)]})
    monkeypatch.setattr(annotate.LLM.chat.completions, "create", lambda **k: NS(choices=[NS(message=NS(content=reply))]))
    ls = [{"text": "Hear the bell?", "kind": "speech"}, {"text": "A bell rang.", "kind": "narration"}, {"text": "Another bell rang.", "kind": "narration"}]
    annotate.mark_sfx(ls, "m")
    assert ["sfx" in l for l in ls] == [False, True, False]


def _fake_run(monkeypatch, progress):
    from app import annotate
    from app.annotate import LABEL_W, SFX_W
    text = "\n\n".join(f"Paragraph {i}. " + "The rain fell on the quiet street. " * 8 for i in range(60))
    lab = lambda us, *a, **k: [{"id": u["id"], "kind": "narration", "speaker": "Narrator", "emotion": "calm", "pause_after": 0.4,
                                "mood": "calm", "unsure": False, "spoken_part": ""} for u in us]
    monkeypatch.setattr(annotate, "label_chunk", lab)
    monkeypatch.setattr(annotate, "describe", lambda *a, **k: [])
    monkeypatch.setattr(annotate, "fill_moods", lambda *a, **k: None)
    monkeypatch.setattr(annotate, "_preset", lambda: {})
    monkeypatch.setattr(annotate, "_chat", lambda **k: (_ for _ in ()).throw(RuntimeError("no network")))
    return annotate.annotate_chapter(text, progress=progress), len(annotate.chunk(annotate.units(text))), LABEL_W, SFX_W


def test_progress_is_monotonic_and_ends_at_total(monkeypatch):
    calls = []
    r, nchunks, LW, SW = _fake_run(monkeypatch, lambda d, t, msg="": calls.append((d, t, msg)))
    assert nchunks >= 3 and len(r["lines"]) > 20
    ds = [d for d, _, _ in calls]
    assert ds == sorted(ds) and all(d <= t for d, t, _ in calls)
    assert calls[-1][0] == calls[-1][1]
    assert len({t for _, t, _ in calls}) <= 2      # estimate, then one correction at merge
    assert calls[-1][1] == LW * nchunks + SW * -(-len(r["lines"]) // 20)


def test_progress_optional_and_no_emphasis(monkeypatch):
    r, *_ = _fake_run(monkeypatch, None)
    assert all("emphasis" not in l for l in r["lines"])
