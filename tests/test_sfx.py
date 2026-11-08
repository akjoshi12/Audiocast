import numpy as np

from app import sfx
from app.tts import SR


def test_add_places_effects_at_start_or_end_of_the_line_and_nowhere_else(tmp_path):
    voice = np.zeros(SR * 10, np.float32)
    lines = [{"sfx": [{"prompt": "a knock", "at": "end"}]}, {}, {"sfx": [{"prompt": "a bark", "at": "start"}]}]
    spans = [(0.0, 2.0), (2.5, 4.0), (5.0, 7.0)]
    out = sfx.add(voice, lines, spans, tmp_path, make=lambda prompt, cache: np.full(SR, 0.5, np.float32))
    loud = lambda a, b: float(np.abs(out[int(a * SR): int(b * SR)]).max())
    assert loud(2.0, 3.0) > 0.05 and loud(5.0, 6.0) > 0.05      # after line 0, at the start of line 2
    assert loud(0.0, 1.9) == 0 and loud(3.2, 4.9) == 0 and loud(8.0, 10.0) == 0
    assert len(out) == len(voice)


def test_add_skips_an_effect_that_failed_to_generate(tmp_path):
    voice = np.zeros(SR * 3, np.float32)
    out = sfx.add(voice, [{"sfx": [{"prompt": "x", "at": "start"}]}], [(0.0, 1.0)], tmp_path, make=lambda p, c: None)
    assert not out.any()


def test_effect_running_past_the_end_of_the_chapter_is_cut(tmp_path):
    out = sfx.add(np.zeros(SR, np.float32), [{"sfx": [{"prompt": "x", "at": "start"}]}], [(0.5, 1.0)], tmp_path,
                  make=lambda p, c: np.full(SR * 3, 0.5, np.float32))
    assert len(out) == SR


def test_usable_rejects_near_silence_and_scales_peak():
    assert sfx.usable(np.full(1000, 0.002, np.float32)) is None
    a = sfx.usable(np.concatenate([np.zeros(500), np.full(500, 0.2)]).astype(np.float32))
    assert abs(float(np.abs(a).max()) - sfx.PEAK) < 1e-4
