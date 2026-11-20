import numpy as np
import pytest

from app import sfx
from app.tts import SR


def mk(sec, v=0.5, tail=0.0):
    return lambda p, c: np.concatenate([np.full(int(sec * SR), v, np.float32), np.zeros(int(tail * SR), np.float32)])


def two_lines():
    voice = np.zeros(int(3 * SR), np.float32)
    voice[:SR] = 0.1; voice[int(1.5 * SR):int(2.5 * SR)] = 0.2
    return voice, [(0.0, 1.0), (1.5, 2.5)]


def seg(a, x, b): return x[int(a * SR):int(b * SR)]


def test_x1_start_effect_plays_before_the_line_and_shifts_it(tmp_path):
    voice, sp = two_lines()
    lines = [{}, {"sfx": [{"prompt": "x", "at": "start"}]}]
    out, got = sfx.add(voice, lines, sp, tmp_path, make=mk(1.0))
    assert len(out) == len(voice) + round(0.7 * SR) and got == [(0, 1), pytest.approx((2.2, 3.2), abs=1e-3)]
    assert np.array_equal(seg(0, out, 1.0), voice[:SR])
    assert np.array_equal(seg(2.2 + sfx.OVERLAP, out, 3.2), seg(1.5 + sfx.OVERLAP, voice, 2.5))
    assert out[int(1.5 * SR) + SR // 10] > 0.05   # audible in the gap before line 2


def test_x2_end_effect_inserts_only_the_shortfall(tmp_path):
    voice, sp = two_lines()
    out, got = sfx.add(voice, [{"sfx": [{"prompt": "x", "at": "end"}]}, {}], sp, tmp_path, make=mk(1.0))
    assert got == [(0, 1), pytest.approx((1.7, 2.7), abs=1e-3)] and len(out) == len(voice) + int(0.2 * SR)
    assert np.array_equal(seg(0, out, 1.0), voice[:SR]) and out[int(1.1 * SR)] > 0.05 and out[int(1.0 * SR) - 1] == 0.1


def test_x3_end_effect_fits_in_the_existing_pause(tmp_path):
    voice = np.zeros(SR * 5, np.float32)
    out, got = sfx.add(voice, [{"sfx": [{"prompt": "x", "at": "end"}]}, {}], [(0.0, 1.0), (3.0, 4.0)], tmp_path, make=mk(1.0))
    assert got == [(0.0, 1.0), (3.0, 4.0)] and len(out) == len(voice) and out[int(1.5 * SR)] > 0.05


def test_x4_failed_clip_changes_nothing(tmp_path):
    voice, sp = two_lines()
    out, got = sfx.add(voice, [{"sfx": [{"prompt": "x", "at": "start"}]}, {"sfx": [{"prompt": "x", "at": "end"}]}], sp, tmp_path, make=lambda p, c: None)
    assert np.array_equal(out, voice) and got == sp


def test_x5_shifts_accumulate(tmp_path):
    voice = np.zeros(SR * 6, np.float32)
    sp = [(0.0, 1.0), (1.5, 2.5), (3.0, 4.0)]
    lines = [{}, {"sfx": [{"prompt": "x", "at": "start"}]}, {"sfx": [{"prompt": "x", "at": "start"}]}]
    out, got = sfx.add(voice, lines, sp, tmp_path, make=mk(1.0))
    assert got[2][0] == pytest.approx(3.0 + 1.4) and len(out) == len(voice) + int(1.4 * SR)


def test_x6_end_effect_on_last_line_extends_the_track(tmp_path):
    voice = np.zeros(SR * 2, np.float32)
    out, got = sfx.add(voice, [{"sfx": [{"prompt": "x", "at": "end"}]}], [(0.0, 2.0)], tmp_path, make=mk(1.0))
    assert got == [(0.0, 2.0)] and len(out) == 3 * SR and out[int(2.5 * SR)] > 0.05


def test_x7_trailing_silence_of_a_clip_is_trimmed(tmp_path):
    voice, sp = two_lines()
    out, got = sfx.add(voice, [{}, {"sfx": [{"prompt": "x", "at": "start"}]}], sp, tmp_path, make=mk(0.5, tail=2.5))
    assert abs((got[1][0] - 1.5) - (0.5 + 0.15 - sfx.OVERLAP)) < 0.01


def test_x8_start_effect_on_the_first_line(tmp_path):
    voice = np.full(SR, 0.1, np.float32)
    out, got = sfx.add(voice, [{"sfx": [{"prompt": "x", "at": "start"}]}], [(0.0, 1.0)], tmp_path, make=mk(1.0))
    assert got[0][0] == pytest.approx(0.7) and out[int(0.3 * SR)] > 0.05 and out[int(0.5 * SR)] > 0.05 and len(out) == SR + int(0.7 * SR)


def test_usable_rejects_near_silence_and_scales_peak():
    assert sfx.usable(np.full(1000, 0.002, np.float32)) is None
    a = sfx.usable(np.concatenate([np.zeros(500), np.full(500, 0.2)]).astype(np.float32))
    assert abs(float(np.abs(a).max()) - sfx.PEAK) < 1e-4


def test_two_start_effects_on_one_line_stay_intact(tmp_path):
    voice, sp = two_lines()
    ramp = np.linspace(0.1, 0.5, SR, dtype=np.float32)
    out, got = sfx.add(voice, [{}, {"sfx": [{"prompt": "x", "at": "start"}, {"prompt": "x", "at": "start"}]}], sp, tmp_path, make=lambda p, c: ramp)
    c = sfx.soften(ramp, sfx.SOFT["spot"]) * sfx.SPOT_GAIN; n = int(0.03 * SR); f = int(0.4 * SR)
    c[:n] *= np.linspace(0, 1, n, dtype=np.float32); c[-f:] *= np.linspace(1, 0, f, dtype=np.float32)
    s1 = int(1.5 * SR); s2 = s1 + round((1.0 - sfx.OVERLAP) * SR)
    assert np.allclose(out[s1:s2], c[:s2 - s1])                     # first clip until the second begins: no cut
    assert np.allclose(out[s2:s1 + len(c)], c[s2 - s1:] + c[:s1 + len(c) - s2])   # overlap of the two tails
    end = got[1][0]
    assert np.array_equal(seg(end + sfx.OVERLAP, out, got[1][1]), seg(1.5 + sfx.OVERLAP, voice, 2.5))


def test_end_then_start_with_no_pause_keeps_first_clip_off_the_speech(tmp_path):
    voice = np.zeros(SR * 3, np.float32); voice[:SR] = 0.1; voice[SR:2 * SR] = 0.2
    lines = [{"sfx": [{"prompt": "x", "at": "end"}]}, {"sfx": [{"prompt": "x", "at": "start"}]}]
    out, got = sfx.add(voice, lines, [(0.0, 1.0), (1.0, 2.0)], tmp_path, make=mk(1.0, v=0.4))
    a = got[1][0]
    assert a == pytest.approx(1.0 + 0.7 + 0.7, abs=1e-3)
    k = round(a * SR) + round(sfx.OVERLAP * SR)
    assert np.all(out[k:k + SR // 2] == 0.2)   # clean speech after the overlap
    assert np.abs(seg(1.05, out, 1.7)).min() > 0   # first clip intact across the whole gap, nothing cut


def test_fractional_span_keeps_the_last_speech_sample_before_the_gap(tmp_path):
    n = round(69.6776 * SR) + SR * 3
    voice = np.zeros(n, np.float32); voice[:round(69.6776 * SR)] = 0.1
    out, got = sfx.add(voice, [{"sfx": [{"prompt": "x", "at": "end"}]}, {}], [(0.0, 69.6776), (69.6776, 71.0)], tmp_path, make=mk(1.0, v=0.4))
    e = round(69.6776 * SR)
    assert np.all(out[e - 5:e] == 0.1) and out[e + SR // 10] > 0.05


def test_beds_span_same_prompt_lines_and_stay_quiet(tmp_path):
    voice = np.full(SR * 6, 0.1, np.float32)
    sp = [(0.0, 1.0), (1.0, 2.0), (2.0, 3.0)]
    seen = []
    mk3 = lambda p, c, s: (seen.append(p), np.full(int(3 * SR), 0.5, np.float32))[1]
    out = sfx.beds(voice, [{"bed": "rain", "text": "The rain fell."}, {"bed": "rain", "text": "More rain."}, {}], sp, tmp_path, make=mk3)
    assert seen == ["rain"] and np.array_equal(out[3 * SR:], voice[3 * SR:])      # one bed, nothing after the last bed line
    assert 0.1 < out[SR] < 0.1 + 3 * sfx.BED_RMS and out[0] == 0.1                  # audible but quiet; faded in
    assert np.array_equal(sfx.beds(voice, [{"bed": "x", "text": "x marks it"}], [(0, 1)], tmp_path, make=lambda p, c, s: None), voice)


def test_beds_need_grounding_in_the_text_and_events_are_capped(tmp_path):
    voice = np.full(SR * 40, 0.1, np.float32)
    mk3 = lambda p, c, s: np.full(int(6 * SR), 0.5, np.float32)   # longer than loop()'s 3 s crossfade
    sp = [(0.0, 20.0), (20.0, 40.0)]
    out = sfx.beds(voice, [{"text": "He drove away.", "bed": "birds on a quiet street"}, {"text": "A baby screaming.", "bed": "a baby screaming loudly"}], sp, tmp_path, make=mk3)
    assert np.array_equal(out[:20 * SR], voice[:20 * SR])                       # nothing in the text names birds or a street: no bed
    assert out[22 * SR] > 0.1 and np.array_equal(out[30 * SR:], voice[30 * SR:])  # the scream lasts EVENT_S, not the whole 20 s line
    assert sfx.grounded("windscreen wipers and a car engine", "He got into his car") and not sfx.grounded("quiet suburban street, distant birds", "Mr Dursley was the director of a firm")


def test_overlay_effect_sits_under_the_voice_without_moving_the_timeline(tmp_path):
    voice, sp = two_lines()
    out, got = sfx.add(np.zeros_like(voice), [{}, {"sfx": [{"prompt": "x", "at": "start"}]}], sp, tmp_path, make=mk(1.0), overlay=True)
    assert got == sp and len(out) == len(voice) and out[int(1.5 * SR) + SR // 10] > 0.05 and out[int(0.5 * SR)] == 0


def test_stereo_centres_the_narrator_and_places_characters_and_widens_beds():
    n = 3 * SR
    v = np.zeros(n, np.float32); v[:SR] = 0.2; v[SR:2 * SR] = 0.2
    st = sfx.stereo(v, np.zeros(n, np.float32), np.zeros(n, np.float32), [{"speaker": "Narrator"}, {"speaker": "Hagrid"}], [(0.0, 1.0), (1.0, 2.0)])
    assert st.shape == (n, 2) and abs(st[SR // 2, 0] - st[SR // 2, 1]) < 1e-6 and abs(st[SR // 2, 0] - 0.2) < 1e-4   # narrator: same level both sides, unchanged
    assert abs(st[SR + SR // 2, 0] - st[SR + SR // 2, 1]) > 0.01                                                  # a character is off-centre
    bed = np.full(n, 0.05, np.float32)
    w = sfx.stereo(np.zeros(n, np.float32), np.zeros(n, np.float32), bed, [], [])
    assert w[0, 0] == pytest.approx(0.05) and w[0, 1] == 0


def test_chime_rings_before_a_marked_line_and_leaves_others_alone():
    fx = np.zeros(6 * SR, np.float32)
    out = sfx.chimes(fx, [{}, {"chime": True}], [(0.0, 1.0), (3.0, 4.0)])
    assert np.abs(out[: int(2.0 * SR)]).max() == 0 and np.abs(out[int(2.1 * SR): int(3.0 * SR)]).max() > 0.05 and np.abs(out[int(3.2 * SR):]).max() < 0.05
    assert len(sfx.chimes(np.zeros(SR, np.float32), [{"chime": True}], [(0.0, 1.0)])) >= int(sfx.CHIME_S * SR)   # the first line: starts at 0, track grows to fit


def test_prefetch_reports_progress_per_clip(tmp_path, monkeypatch):
    import sys
    fake = tmp_path / "fake_worker.py"   # prints one line per job like tango_worker, writes no audio
    fake.write_text("import json, sys\nfor j in json.load(sys.stdin):\n    print(j['prompt'], flush=True)\n")
    monkeypatch.setattr(sfx, "TANGO_PY", sys.executable)
    monkeypatch.setattr(sfx, "WORKER", fake)
    seen = []
    sfx.prefetch({("a door", 4.0), ("rain", 10.0), ("a bell", 4.0)}, tmp_path / "cache", lambda d, t: seen.append((d, t)))
    assert seen == [(0, 3), (1, 3), (2, 3), (3, 3)]
    assert len(list((tmp_path / "cache").glob("*.none"))) == 3   # no audio came back: marked as unusable, not retried forever
