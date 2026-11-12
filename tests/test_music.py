import numpy as np

from app import music
from app.tts import SR


def L(mood): return {"mood": mood}


def test_cues_merge_short_and_same():
    lines = [L("tense"), L("tense"), L("calm"), L("tense")]
    spans = [(0, 20), (20, 40), (40, 50), (50, 70)]   # the 10 s "calm" blip is absorbed
    assert music.cues(lines, spans) == [{"mood": "tense", "start": 0, "end": 70}]
    lines2 = [L("tense"), L("calm")]
    assert [c["mood"] for c in music.cues(lines2, [(0, 40), (40, 100)])] == ["tense", "none"]


def test_loop_length():
    clip = np.ones(SR * 5, dtype=np.float32)
    assert len(music.loop(clip, SR * 17)) == SR * 17


def test_mix_ducks_under_speech_and_silent_for_none(tmp_path, monkeypatch):
    monkeypatch.setattr(music, "bed", lambda mood, s, cache, setting="": np.full(int(s * SR), 0.5, np.float32))
    voice = np.zeros(SR * 20, np.float32)
    spans = [(10, 20)]
    out = music.mix(voice, spans, [{"mood": "calm", "start": 0, "end": 20}], tmp_path)
    quiet, talking = np.abs(out[SR * 5]), np.abs(out[SR * 15])
    assert talking < quiet * 0.6 and quiet > 0
    none = music.mix(voice, spans, [{"mood": "none", "start": 0, "end": 20}], tmp_path)
    assert not none.any()


def seq(*parts):
    """parts of (mood, seconds) -> lines, spans"""
    lines, spans, t = [], [], 0
    for m, d in parts:
        lines.append({"kind": "narration", "mood": m}); spans.append((t, t + d)); t += d
    return lines, spans


def audible(parts):
    return [c for c in music.cues(*seq(*parts)) if c["mood"] not in music.QUIET]


def test_m1_calm_or_none_chapters_have_no_music(tmp_path):
    for m in ("calm", "none"):
        lines, spans = seq((m, 60), (m, 60))
        assert not [c for c in music.cues(lines, spans) if c["mood"] not in music.QUIET]
        v = np.full(SR * 120, 0.1, np.float32)
        assert np.array_equal(music.mix(v, spans, music.cues(lines, spans), tmp_path), v)


def test_m2_music_enters_at_the_mood_change_and_leaves(tmp_path):
    assert audible([("calm", 60), ("tense", 60), ("calm", 60)]) == [{"mood": "tense", "start": 60, "end": 120}]


def test_m3_a_long_scene_is_capped():
    got = audible([("tense", 300)])
    assert len(got) == 1 and got[0]["end"] - got[0]["start"] == music.MAX_CUE_S


def test_m4_music_does_not_restart_until_a_later_cue():
    got = audible([("tense", 100), ("calm", 60), ("tense", 100)])
    assert len(got) == 2 and got[1]["start"] == 160 and all(c["end"] - c["start"] == music.MAX_CUE_S for c in got)


def test_m5_a_short_blip_in_a_calm_chapter_is_silent():
    assert not audible([("calm", 100), ("tense", 10), ("calm", 100)])


def test_m6_a_short_calm_dip_does_not_split_a_tense_scene():
    got = audible([("tense", 20), ("tense", 20), ("calm", 10), ("tense", 20)])
    assert len(got) == 1 and got[0]["start"] == 0 and got[0]["end"] == 70


def test_m7_headings_are_always_silent():
    lines = [{"kind": "heading", "mood": "tense"}, {"kind": "narration", "mood": "tense"}]
    got = music.cues(lines, [(0, 40), (40, 80)])
    assert got[0]["mood"] == "none"


def test_mix_survives_float_rounding_of_cue_length(tmp_path, monkeypatch):
    monkeypatch.setattr(music, "bed", lambda mood, s, cache, setting="": np.full(int(s * SR), 0.5, np.float32))
    n = 6309600  # the length from the real crash; (n/SR)*SR truncates to n-1
    out = music.mix(np.zeros(n, np.float32), [], [{"mood": "calm", "start": 0, "end": n / SR}], tmp_path)
    assert len(out) == n


def test_music_is_audible_under_speech(tmp_path, monkeypatch):
    """Chapter 1 shipped with the bed ~19 dB under the voice and the listener heard no music at all: keep it within 12.5 dB."""
    monkeypatch.setattr(music, "bed", lambda mood, s, cache, setting="": np.full(int(s * SR), 0.1, np.float32))  # real beds are normalised to rms 0.1
    out = music.mix(np.zeros(SR * 40, np.float32), [(0, 40)], [{"mood": "calm", "start": 0, "end": 40}], tmp_path)
    assert out[SR * 20] > 0.1 * 10 ** (-12.5 / 20)
