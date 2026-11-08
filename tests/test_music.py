import numpy as np

from app import music
from app.tts import SR


def L(mood): return {"mood": mood}


def test_cues_merge_short_and_same():
    lines = [L("tense"), L("tense"), L("calm"), L("tense")]
    spans = [(0, 30), (30, 60), (60, 70), (70, 120)]   # the 10 s "calm" blip is absorbed
    assert music.cues(lines, spans) == [{"mood": "tense", "start": 0, "end": 120}]
    lines2 = [L("tense"), L("calm")]
    assert [c["mood"] for c in music.cues(lines2, [(0, 40), (40, 100)])] == ["tense", "calm"]


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


def test_all_none_moods_still_get_music_but_headings_stay_silent():
    lines = [{"kind": "heading", "mood": "none"}] + [{"kind": "narration", "mood": "none"} for _ in range(3)] + [{"kind": "heading", "mood": "none"}]
    spans = [(0, 3), (3, 30), (30, 60), (60, 90), (90, 93)]
    got = music.cues(lines, spans)
    assert [c["mood"] for c in got] == ["none", "calm"] and got[1]["start"] == 3 and got[1]["end"] == 93  # closing heading is absorbed
    lines[2]["mood"] = "tense"
    assert [c["mood"] for c in music.cues(lines, spans)][1:] == ["tense"]  # first real mood also fills the lines before it


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
