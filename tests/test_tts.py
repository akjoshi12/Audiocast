import pytest
import soundfile as sf

from app import tts

LINES = [
    {"speaker": "Narrator", "text": "The storm had been building.", "emotion": "calm, tense", "pause_after": 0.6},
    {"speaker": "Margaret", "text": "Sorry? Your brother is dead!", "emotion": "angry, bitter", "pause_after": 1.5},
]
CHARS = [{"name": "Margaret", "gender": "female", "age": "adult", "voice": "sharp"}]


def test_auto_cast_distinct_and_gendered():
    chars = [{"name": n, "gender": "female", "age": "adult", "voice": ""} for n in "ABCD"]
    cast = tts.auto_cast(chars)
    assert len({cast[n] for n in "ABCD"}) == 4 and set(cast[n] for n in "ABCD") <= set(tts.VOICES["female"])
    assert cast["Narrator"] == tts.NARRATOR_VOICE


def test_render_and_resume(tmp_path):
    cast = tts.auto_cast(CHARS)
    out = tts.render(LINES, cast, tmp_path)
    d, sr = sf.read(out)
    assert sr == tts.SR and len(d) / sr > 2.1 + 1.0  # speech + both pauses
    first = next((tmp_path / "lines").glob("00000_*.wav")).stat().st_mtime_ns
    tts.render(LINES, cast, tmp_path)  # resume: cached lines untouched
    assert next((tmp_path / "lines").glob("00000_*.wav")).stat().st_mtime_ns == first


def test_exaggeration_and_split():
    assert tts.exaggeration("furious, shouting") > tts.exaggeration("tense") > tts.exaggeration("calm, quiet")
    long = " ".join(f"Sentence number {i} is here." for i in range(40))
    parts = tts.split_text(long)
    assert all(len(p) <= 260 for p in parts) and " ".join(parts) == long


def test_editing_one_line_rerenders_only_that_line(tmp_path):
    cast = tts.auto_cast(CHARS)
    tts.render(LINES, cast, tmp_path)
    second = next((tmp_path / "lines").glob("00001_*.wav")).stat().st_mtime_ns
    edited = [dict(LINES[0], text="The storm had broken."), LINES[1]]
    tts.render(edited, cast, tmp_path)
    assert len(list((tmp_path / "lines").glob("*.wav"))) == 2          # stale file removed
    assert next((tmp_path / "lines").glob("00001_*.wav")).stat().st_mtime_ns == second
    assert len(tts.spans(edited, cast, tmp_path)) == 2


def test_tighten_cuts_long_inner_silence_but_keeps_short_pauses_and_speech():
    import numpy as np
    from app.tts import SR, tighten
    tone = lambda s: (0.3 * np.sin(np.linspace(0, 2000 * s, int(SR * s)))).astype(np.float32)
    z = lambda s: np.zeros(int(SR * s), np.float32)
    clip = np.concatenate([z(0.6), tone(1.0), z(1.2), tone(1.0), z(0.2), tone(1.0), z(0.9)])
    out = tighten(clip)
    assert abs(len(out) / SR - (3.0 + 0.7 + 0.2 + 0.2)) < 0.08   # speech kept, 1.2 s gap -> 0.7 s, 0.2 s pause untouched, lead/tail -> 0.1 s each
    assert abs(float(np.abs(out).sum()) - float(np.abs(clip).sum())) < 1e-3 * float(np.abs(clip).sum())  # no speech lost


def test_stress_and_slow():
    import numpy as np
    from app import tts
    assert tts.stress("He felt a great strength, truly.", ["strength", "he", "nope"]) == "He felt a great STRENGTH, truly."  # short/absent words ignored
    a = (np.sin(np.linspace(0, 2000, tts.SR)) * 0.3).astype("float32")  # 1 s tone
    assert 1.05 < len(tts.slow(a)) / tts.SR < 1.15  # 1/0.92 = 1.087


@pytest.mark.skipif(not tts.VOX_PY.exists(), reason="VoxCPM2 virtualenv not installed")
def test_voxcpm_worker_speaks_with_direction():
    a = tts.speak("The night was dark, and the road was long.", tts.NARRATOR_VOICE, "calm, tired")
    assert 2.0 < len(a) / tts.SR < 9.0 and float(abs(a).max()) > 0.05


def test_split_text_breaks_overlong_sentences_at_commas():
    sentence = ", ".join(["a rather long clause about the weather"] * 30) + "."          # ~1200 chars, one sentence
    parts = tts.split_text(sentence)
    assert len(parts) > 3 and all(len(p) <= 260 for p in parts)
    assert " ".join(parts).replace(" ,", ",") == sentence                                # nothing lost or reordered


def test_split_text_keeps_a_long_word_run_without_commas_in_bounded_pieces():
    run = " ".join(["word"] * 400)                                                       # 2000 chars, no punctuation at all
    parts = tts.split_text(run)
    assert all(len(p) <= 260 for p in parts) and " ".join(parts) == run


def test_speak_vox_retries_in_halves_when_the_worker_fails(monkeypatch):
    import numpy as np
    calls = []

    def fake_ask(job):                                       # fails for long text, like the VoxCPM2 broadcast error on a long piece
        spoken = job["text"].split(") ", 1)[-1]               # drop the "(direction) " prefix
        calls.append(spoken)
        if len(spoken) > 100:
            raise RuntimeError("VoxCPM2: ValueError('operands could not be broadcast together with shapes (6309600,) (6309599,) (6309600,)')")
        sf.write(job["out"], np.full(2400, 0.1, dtype="float32"), 24000)
        return {"ok": True, "sr": 24000}

    monkeypatch.setattr(tts, "_vox_ask", fake_ask)
    text = " ".join(["word"] * 60)                           # 299 chars -> fails, halves (~150) fail, quarters (~75) succeed
    a = tts._speak_vox(text, tts.NARRATOR_VOICE, "calm")
    assert len(a) == 4 * 2400 and float(abs(a).max()) > 0.05


def test_speak_vox_still_raises_when_a_short_piece_fails(monkeypatch):
    def always_fail(job):
        raise RuntimeError("VoxCPM2: boom")

    monkeypatch.setattr(tts, "_vox_ask", always_fail)
    with pytest.raises(RuntimeError, match="boom"):
        tts._speak_vox("Short line.", tts.NARRATOR_VOICE, "calm")


def test_speak_vox_retries_a_short_piece_once_before_giving_up(monkeypatch):
    import numpy as np
    n = {"calls": 0}

    def flaky(job):                                          # fails the first time, works the second (the model samples randomly)
        n["calls"] += 1
        if n["calls"] == 1:
            raise RuntimeError("VoxCPM2: ValueError('operands could not be broadcast together')")
        sf.write(job["out"], np.full(2400, 0.1, dtype="float32"), 24000)
        return {"ok": True, "sr": 24000}

    monkeypatch.setattr(tts, "_vox_ask", flaky)
    a = tts._speak_vox("Short line.", tts.NARRATOR_VOICE, "calm")
    assert n["calls"] == 2 and len(a) == 2400
