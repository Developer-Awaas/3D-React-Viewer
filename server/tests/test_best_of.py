"""Tests for the best-of ML arbitration — every active reader runs, the
highest-scoring scene wins, one broken model never blocks the rest."""
import asyncio

import pytest

import main


def _scene(reader, rooms, doors, w=40, d=50):
    return {"meta": {"reader": f"ml:{reader}", "plan_width_ft": w, "plan_depth_ft": d},
            "rooms": [{"id": f"r{i}"} for i in range(rooms)],
            "openings": [{"type": "door"} for _ in range(doors)]}


def _patch(monkeypatch, readers, results):
    monkeypatch.setattr(main, "_ACTIVE_READERS", readers)

    async def fake(reader, name, png, width_ft):
        r = results[name]
        if isinstance(r, Exception):
            raise r
        return r
    monkeypatch.setattr(main, "_one_ml_scene", fake)


def test_best_scene_wins(monkeypatch):
    _patch(monkeypatch, {"cubicasa": 1, "tf2": 2},
           {"cubicasa": _scene("cubicasa", rooms=2, doors=1),
            "tf2": _scene("tf2", rooms=8, doors=9)})
    best = asyncio.run(main._ml_scene_from_png(b"png", 18))
    assert best["meta"]["reader"] == "ml:tf2"
    assert set(best["meta"]["reader_scores"]) == {"cubicasa", "tf2"}
    assert best["meta"]["reader_scores"]["tf2"] > best["meta"]["reader_scores"]["cubicasa"]


def test_broken_model_never_blocks_the_other(monkeypatch):
    _patch(monkeypatch, {"cubicasa": 1, "tf2": 2},
           {"cubicasa": RuntimeError("model exploded"),
            "tf2": _scene("tf2", rooms=5, doors=4)})
    best = asyncio.run(main._ml_scene_from_png(b"png", 18))
    assert best["meta"]["reader"] == "ml:tf2"


def test_single_reader_no_scores_block(monkeypatch):
    _patch(monkeypatch, {"cubicasa": 1},
           {"cubicasa": _scene("cubicasa", rooms=3, doors=2)})
    best = asyncio.run(main._ml_scene_from_png(b"png", 18))
    assert best["meta"]["reader"] == "ml:cubicasa"
    assert "reader_scores" not in best["meta"]        # no contest -> no scoreboard


def test_all_broken_raises_503(monkeypatch):
    _patch(monkeypatch, {"cubicasa": 1, "tf2": 2},
           {"cubicasa": RuntimeError("x"), "tf2": RuntimeError("y")})
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as e:
        asyncio.run(main._ml_scene_from_png(b"png", 18))
    assert e.value.status_code == 503


def test_no_readers_raises_503(monkeypatch):
    monkeypatch.setattr(main, "_ACTIVE_READERS", {})
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as e:
        asyncio.run(main._ml_scene_from_png(b"png", 18))
    assert e.value.status_code == 503
