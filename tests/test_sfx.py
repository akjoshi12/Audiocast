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
    c = ramp.copy(); n = int(0.03 * SR); f = int(0.4 * SR)
    c[:n] *= np.linspace(0, 1, n, dtype=np.float32); c[-f:] *= np.linspace(1, 0, f, dtype=np.float32)
    s1 = int(1.5 * SR); s2 = s1 + round((1.0 - sfx.OVERLAP) * SR)
    assert np.allclose(out[s1:s2], c[:s2 - s1])                       # first clip until the second begins: no cut
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
