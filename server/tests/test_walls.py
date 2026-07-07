"""Tests for the Step A wall vectorizer."""
from walls import _collapse, vectorize_walls


# --- pure geometry (no OpenCV needed) ---
def test_collapse_merges_parallel_lines():
    r = _collapse([{"p": 10, "a": 0, "b": 100}, {"p": 12, "a": 0, "b": 100}], 18, 5, 10)
    assert len(r) == 1 and r[0]["a"] == 0 and r[0]["b"] == 100


def test_collapse_keeps_doorway_gap():
    r = _collapse([{"p": 10, "a": 0, "b": 40}, {"p": 10, "a": 60, "b": 100}], 18, 5, 10)
    assert len(r) == 2   # the doorway opening is preserved


def test_collapse_bridges_small_gap():
    r = _collapse([{"p": 10, "a": 0, "b": 40}, {"p": 10, "a": 60, "b": 100}], 18, 25, 10)
    assert len(r) == 1 and r[0]["b"] == 100


def test_collapse_drops_short_fragments():
    assert _collapse([{"p": 5, "a": 0, "b": 5}], 18, 5, 10) == []


# --- full vectorizer on a synthetic plan (needs numpy + OpenCV; runs in CI) ---
def test_vectorize_walls_on_a_box():
    import numpy as np
    m = np.zeros((300, 400), dtype=np.uint8)
    t = 6
    m[20:20 + t, 20:380] = 1     # top wall
    m[280 - t:280, 20:380] = 1   # bottom wall
    m[20:280, 20:20 + t] = 1     # left wall
    m[20:280, 380 - t:380] = 1   # right wall

    segs = vectorize_walls(m)
    assert len(segs) >= 4                      # the four walls of the box
    assert all(len(s) == 4 for s in segs)      # each is [x1, y1, x2, y2]
