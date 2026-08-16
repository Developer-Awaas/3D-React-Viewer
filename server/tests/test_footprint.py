"""Building footprint from the OUTER WALL RING (W-1), and the physics check
that a footprint can never exceed its plot (§0.1).

The ring is bridged jamb-to-jamb, never dilated: a fixed morphological kernel
is a guess about the widest opening in the outer wall, and no value is right
(6 ft leaves FLOOR PLAN's balconies open at 1240 sqft against a real plate of
~1951; 14 ft closes them and pushes neelachala FIRST FLOOR past its own plot).
"""
import os

import numpy as np
import pytest

import pdf_vector

PLANS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "plans")
PPX = pdf_vector.NORM_PPX


def _ring(gap_ft=0.0, size_ft=20, thick_ft=0.75):
    """A square wall ring with an optional gap in its right face, plus the
    segment list that traces it. Returns (mask, seg_px)."""
    n = int(size_ft * PPX) + 40
    m = np.zeros((n, n), np.uint8)
    a, b = 20, 20 + int(size_ft * PPX)
    t = max(2, int(thick_ft * PPX))
    segs = []
    m[a:a + t, a:b] = 255; segs.append((a, a, b, a))          # top
    m[b - t:b, a:b] = 255; segs.append((a, b, b, b))          # bottom
    m[a:b, a:a + t] = 255; segs.append((a, a, a, b))          # left
    g = int(gap_ft * PPX)
    mid = (a + b) // 2
    if g:                                                      # right, split
        m[a:mid - g // 2, b - t:b] = 255
        m[mid + g // 2:b, b - t:b] = 255
        segs += [(b, a, b, mid - g // 2), (b, mid + g // 2, b, b)]
    else:
        m[a:b, b - t:b] = 255; segs.append((b, a, b, b))
    return m, segs


class TestFootprint:
    def test_closed_ring_fills_to_its_own_area(self):
        m, segs = _ring()
        foot, bridges, *_ = pdf_vector._footprint_from_walls(m, seg_px=segs)
        assert (foot > 0).sum() / PPX ** 2 == pytest.approx(20 * 20, rel=0.08)
        assert bridges == []                       # nothing to bridge

    def test_open_ring_is_bridged_and_still_fills(self):
        """A 10 ft opening (a balcony face) must not leak the interior away."""
        m, segs = _ring(gap_ft=10.0)
        foot, bridges, *_ = pdf_vector._footprint_from_walls(m, seg_px=segs)
        assert (foot > 0).sum() / PPX ** 2 == pytest.approx(20 * 20, rel=0.10)
        assert any(b == pytest.approx(10.0, abs=1.5) for b in bridges)

    def test_bridge_length_is_the_real_gap_not_a_kernel(self):
        """The bridge is as long as the gap actually is — no kernel involved."""
        for gap in (4.0, 6.0):            # 20 ft face -> plenty of wall left
            m, segs = _ring(gap_ft=gap)
            _f, bridges, *_ = pdf_vector._footprint_from_walls(m, seg_px=segs)
            assert any(b == pytest.approx(gap, abs=1.5) for b in bridges), gap

    def test_a_gap_longer_than_its_wall_is_rejected(self):
        """§0.1: a gap cannot be longer than the wall it is a hole in. An 18 ft
        opening in a 20 ft face leaves ~2 ft of wall — that is not a hole in a
        wall, it is an open side, and §10 (balconies) governs it."""
        m, segs = _ring(gap_ft=18.0)
        _f, bridges, rejected, *_ = pdf_vector._footprint_from_walls(m, seg_px=segs)
        assert any(r == pytest.approx(18.0, abs=1.5) for r in rejected)
        assert not any(b == pytest.approx(18.0, abs=1.5) for b in bridges)

    def test_no_segments_still_returns_a_footprint(self):
        m, _s = _ring()
        foot, bridges, *_ = pdf_vector._footprint_from_walls(m)
        assert foot is not None and bridges == []

    def test_empty_mask_is_none(self):
        foot, bridges, *_ = pdf_vector._footprint_from_walls(
            np.zeros((100, 100), np.uint8))
        assert foot is None and bridges == []


class TestFreeEndpoints:
    def test_a_walls_own_thickness_is_not_an_opening(self):
        """The two faces of one wall end side by side. Capping that closes
        nothing, and consuming the jambs on it would starve the real bridge."""
        segs = [(0, 0, 100, 0), (0, 38, 100, 38)]      # 0.75 ft apart
        pairs = pdf_vector._free_ring_endpoints(
            segs, join_tol=0.35 * PPX, min_gap=1.2 * PPX)
        assert all(d >= 1.2 * PPX for _p, _q, d, _bound in pairs)

    def test_joined_corners_are_not_free(self):
        """An L: the shared corner meets a wall and is not a jamb. Its two
        outer ends ARE jambs, and bridging them is what closes the ring."""
        segs = [(0, 0, 100, 0), (100, 0, 100, 100)]    # share a corner
        pairs = pdf_vector._free_ring_endpoints(
            segs, join_tol=0.35 * PPX, min_gap=1.2 * PPX)
        joined = [p for pair in pairs for p in pair[:2]
                  if abs(p[0] - 100) < 1 and abs(p[1] - 0) < 1]
        assert not joined                              # corner never bridged
        assert len(pairs) == 1                         # the two open ends

    def test_no_segments(self):
        assert pdf_vector._free_ring_endpoints([], 10, 20) == []


@pytest.mark.skipif(not os.path.exists(os.path.join(PLANS, "FLOOR PLAN.pdf")),
                    reason="confidential corpus not present")
@pytest.mark.parametrize("name", ["FLOOR PLAN.pdf", "neelachala FIRST FLOOR.pdf"])
def test_footprint_never_exceeds_the_plot(name):
    """PHYSICS (§0.1): a building cannot be larger than its land. This is the
    check that disqualified the fixed-kernel footprint — at a 14 ft seal
    neelachala FIRST FLOOR came out 2563 sqft on a 2455 sqft plot."""
    path = os.path.join(PLANS, name)
    if not os.path.exists(path):
        pytest.skip(f"corpus file not present: {name}")
    with open(path, "rb") as f:
        meta = pdf_vector.parse(f.read())["meta"]
    fp, plot = meta.get("footprint_sqft"), meta.get("plot_sqft")
    assert fp and plot, "both sheets state a plot; the check must be live"
    assert fp <= plot, f"{name}: footprint {fp} sqft on a {plot} sqft plot"


def test_doctor_fails_a_footprint_above_its_plot():
    import plan_doctor
    d = plan_doctor.diagnose({
        "meta": {"plan_width_ft": 40, "plan_depth_ft": 60,
                 "footprint_sqft": 2563.0, "plot_sqft": 2454.4,
                 "scale": {"source": "dimension_text"}},
        "rooms": [{"id": "r0", "type": "bedroom", "area_sqft": 120}],
        "openings": [{"type": "door", "along": [0, 3]}, {"type": "window"}],
        "area_statement": {"efficiency_pct": 70.0, "carpet_source": "rooms"},
        "vastu": {}, "boq": {}})
    bad = [i for i in d["issues"] if i["tag"] == "footprint_exceeds_plot"]
    assert bad and bad[0]["level"] == "fail"       # fail, never warn
    assert d["grade"] in ("D", "F")


def test_doctor_skips_the_check_when_the_plot_is_unknown():
    import plan_doctor
    d = plan_doctor.diagnose({
        "meta": {"plan_width_ft": 40, "plan_depth_ft": 60,
                 "footprint_sqft": 9999.0, "plot_sqft": None,
                 "scale": {"source": "dimension_text"}},
        "rooms": [{"id": "r0", "type": "bedroom", "area_sqft": 120}],
        "openings": [{"type": "door", "along": [0, 3]}, {"type": "window"}],
        "area_statement": {"efficiency_pct": 70.0, "carpet_source": "rooms"},
        "vastu": {}, "boq": {}})
    assert not any(i["tag"] == "footprint_exceeds_plot" for i in d["issues"])


# --- POSITION GATE (14 Aug 2026) --------------------------------------------
# The gate must be computed from the TRUSTED walls ALONE. Computing it from a
# set that already contains the candidates lets them vouch for themselves:
# FLOOR PLAN's 13 lines on layer `0` at y -13.0..-7.9 ft pair with each other,
# extend the "building", and then pass the gate meant to reject them.
def test_extent_comes_from_paired_lines_only():
    ppf = 50.0
    walls = [(0, 0, 1000, 0), (0, 40, 1000, 40)]          # a 10 in pair
    stray = [(0, -600, 300, -600)]                         # far below, unpaired
    ext = pdf_vector.paired_extent(walls + stray, ppf)
    assert ext[1] >= -1 and ext[3] <= 41                   # stray excluded


def test_a_self_pairing_candidate_cannot_extend_the_building():
    """Two candidate lines that pair with EACH OTHER must not enlarge the
    extent when the extent is computed from the trusted set."""
    ppf = 50.0
    trusted = [(0, 0, 1000, 0), (0, 40, 1000, 40)]
    candidates = [(0, -600, 400, -600), (0, -560, 400, -560)]   # a pair, below
    ext = pdf_vector.paired_extent(trusted, ppf)                # trusted ONLY
    margin = 0.02 * max(ext[2] - ext[0], ext[3] - ext[1])
    assert not pdf_vector.inside_extent(candidates[0], ext, margin)
    assert not pdf_vector.inside_extent(candidates[1], ext, margin)


def test_gate_passes_a_line_inside_the_building():
    ppf = 50.0
    trusted = [(0, 0, 1000, 0), (0, 40, 1000, 40)]
    ext = pdf_vector.paired_extent(trusted, ppf)
    margin = 0.02 * max(ext[2] - ext[0], ext[3] - ext[1])
    assert pdf_vector.inside_extent((100, 5, 400, 5), ext, margin)


def test_no_trusted_walls_means_no_gate():
    """Structural limit, recorded: with no trusted paired walls there is
    nothing to gate against, and everything passes. That is exactly how
    neelachala FIRST FLOOR inflated to 47.6 x 185.3 ft."""
    assert pdf_vector.paired_extent([(0, 0, 100, 0)], 50.0) is None
    assert pdf_vector.inside_extent((0, -9999, 10, -9999), None, 5.0) is True


# --- §4 D-5 DUCTS (16 Aug 2026) ---------------------------------------------
# A duct is a wall-ringed VOID of 2-18 sqft. It cannot be found as free space:
# FLOOR PLAN's are 1.00 ft across and the wall-merge closing kernel is 0.88 ft,
# so the interior fills solid and NO area floor can reach it. It is read from
# the rectangle the drafter drew.
def test_a_small_closed_rectangle_is_found():
    segs = [(25.58, 7.89, 26.58, 7.89), (25.58, 12.90, 26.58, 12.90),
            (25.58, 7.89, 25.58, 12.90), (26.58, 7.89, 26.58, 12.90)]
    assert pdf_vector.enclosed_boxes(segs) == [(25.58, 7.89, 26.58, 12.90)]


def test_an_open_rectangle_is_not_a_duct():
    """Three sides is a recess, not a shaft."""
    segs = [(25.58, 7.89, 26.58, 7.89), (25.58, 12.90, 26.58, 12.90),
            (25.58, 7.89, 25.58, 12.90)]
    assert pdf_vector.enclosed_boxes(segs) == []


def test_a_room_sized_box_is_not_a_duct():
    segs = [(0, 0, 10, 0), (0, 10, 10, 10), (0, 0, 0, 10), (10, 0, 10, 10)]
    assert pdf_vector.enclosed_boxes(segs) == []


@pytest.mark.skipif(not os.path.exists(os.path.join(PLANS, "FLOOR PLAN.pdf")),
                    reason="confidential corpus not present")
def test_floor_plan_finds_both_ducts_and_they_are_common_area():
    import area_statement
    with open(os.path.join(PLANS, "FLOOR PLAN.pdf"), "rb") as f:
        s = pdf_vector.parse(f.read())
    ducts = [r for r in s["rooms"] if r.get("type") == "duct"]
    assert len(ducts) == 2
    assert all(d["void"] for d in ducts)                  # never solid in 3D
    assert sorted(round(d["area_sqft"], 1) for d in ducts) == [2.3, 5.0]
    st = area_statement.compute_area_statement(s)
    assert st["common_area"]["sqft"] == pytest.approx(30.9, abs=0.2)
    carpet_types = {r.get("type") for r in s["rooms"]}
    assert "duct" in carpet_types                          # counted, not dropped
