"""Building footprint from the OUTER WALL RING (W-1), and the physics check
that a footprint can never exceed its plot (§0.1).

The ring is bridged jamb-to-jamb, never dilated: a fixed morphological kernel
is a guess about the widest opening in the outer wall, and no value is right
(6 ft leaves FLOOR PLAN's balconies open at 1240 sqft against a real plate of
~1951; 14 ft closes them and pushes neelachala FIRST FLOOR past its own plot).
"""
import numpy as np
import pytest

import pdf_vector
from conftest import require_corpus_file

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


@pytest.mark.parametrize("name", ["FLOOR PLAN.pdf", "neelachala FIRST FLOOR.pdf"])
def test_footprint_never_exceeds_the_plot(name):
    """PHYSICS (§0.1): a building cannot be larger than its land. This is the
    check that disqualified the fixed-kernel footprint — at a 14 ft seal
    neelachala FIRST FLOOR came out 2563 sqft on a 2455 sqft plot.

    THAT 2455 WAS NEVER A PLOT (21 Aug 2026). `_plot_sqft` used to fall back to
    `out_w * out_d` — the BUILDING's own envelope — whenever the envelope came
    from overall-dimension text, so on that sheet the check was comparing the
    building to itself and could only fail if the footprint exceeded its own
    bounding box. The 2454.4 is exactly its 38.2 x 64.2 ft extent, and exactly
    the BOTTOM BLOCK's printed 64'-2" x 38'-3". The plot now comes from the
    drawing or the user and from nowhere else; where neither states one the
    check is BLIND and says so (`plan_doctor` raises `plot_area_unknown` as an
    ask). Rahul's real figure for that site is 11,500 sqft."""
    path = require_corpus_file(name)
    with open(path, "rb") as f:
        meta = pdf_vector.parse(f.read())["meta"]
    fp, plot = meta.get("footprint_sqft"), meta.get("plot_sqft")
    assert fp
    if not plot:
        assert meta.get("plot_source") == "unknown", meta.get("plot_source")
        return                                  # BLIND, and it says so
    assert meta.get("plot_source") in ("printed_area_statement", "user")
    assert fp <= plot, f"{name}: footprint {fp} sqft on a {plot} sqft plot"


def test_a_user_supplied_plot_makes_the_physics_check_live_again():
    """The plot may come from the drawing or the USER, never from the building.
    Rahul supplied 11,500 sqft for neelachala FIRST FLOOR, and ground_truth.json
    is not read at runtime, so there has to be a way in (21 Aug 2026)."""
    import corrections
    import plan_doctor
    scene = {"meta": {"plan_width_ft": 38.2, "plan_depth_ft": 64.2,
                      "footprint_sqft": 1652.2, "plot_sqft": None,
                      "plot_source": "unknown",
                      "scale": {"source": "dimension_text"}},
             "rooms": [{"id": "r0", "type": "bedroom", "area_sqft": 120}],
             "openings": [], "walls": []}
    tags = {i["tag"] for i in plan_doctor.diagnose(scene)["issues"]}
    assert "plot_area_unknown" in tags          # blind, and said out loud
    out, info = corrections.apply_corrections(scene, {"plot_area_sqft": 11500})
    assert out["meta"]["plot_sqft"] == 11500.0
    assert out["meta"]["plot_source"] == "user"
    assert "11500" in "".join(info["applied"]).replace(",", "")
    tags = {i["tag"] for i in plan_doctor.diagnose(out)["issues"]}
    assert "plot_area_unknown" not in tags      # a REAL check now, and it passes
    assert "footprint_exceeds_plot" not in tags


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


def test_floor_plan_finds_both_ducts_and_they_are_common_area():
    import area_statement
    with open(require_corpus_file("FLOOR PLAN.pdf"), "rb") as f:
        s = pdf_vector.parse(f.read())
    ducts = [r for r in s["rooms"] if r.get("type") == "duct"]
    assert len(ducts) == 2
    assert all(d["void"] for d in ducts)                  # never solid in 3D
    assert sorted(round(d["area_sqft"], 1) for d in ducts) == [2.3, 5.0]
    st = area_statement.compute_area_statement(s)
    # 30.9 -> 28.7 on 17 Aug: pair-built walls paint each wall at its measured
    # thickness instead of a thin dilated band, so every space is measured to
    # its true faces and the small ones move most.
    assert st["common_area"]["sqft"] == pytest.approx(28.7, abs=0.3)
    carpet_types = {r.get("type") for r in s["rooms"]}
    assert "duct" in carpet_types                          # counted, not dropped


# --- §0.2 CONTRADICTS: a space open on ONE side (16 Aug 2026) ----------------
# On an upper floor a space has a roof and a floor, so it must be closed. The
# only exception is a balcony with exactly one open side. FLOOR PLAN's entire
# common area — 189.9 sqft of lobby + staircase — is DETECTED and then thrown
# away by the border test, because its south edge is drawn 2 in wide on a
# furniture layer. "Not found" and "found then discarded" look identical from
# the output, and were confused for two weeks.
def _three_sided(open_side="S", size_ft=12):
    """A pocket walled on three sides whose open side runs to the image edge —
    the shape of FLOOR PLAN's common area, whose south edge is undrawn so the
    free space reaches the raster border and the border test discards it."""
    n = int(size_ft * PPX) + 40
    m = np.zeros((n, n), np.uint8)
    a, b = 40, 40 + int(size_ft * PPX)
    t = max(3, int(0.75 * PPX))
    m[a:a + t, a:b] = 255                          # north
    m[a:n, a:a + t] = 255                          # west, down to the edge
    m[a:n, b - t:b] = 255                          # east, down to the edge
    if open_side != "S":
        m[n - t:n, a:b] = 255                      # closed: no leak at all
    return m


class TestOpenSideRegions:
    def test_a_three_sided_pocket_is_flagged(self):
        got = pdf_vector.open_side_regions(_three_sided(), PPX, 40, 40, 20.0,
                                           min_sqft=20.0)
        assert len(got) == 1
        assert got[0]["open_side"] == "south"
        assert got[0]["area_if_closed_sqft"] > 0
        assert got[0]["side_backed_pct"]["S"] < 35

    def test_a_closed_room_is_not_flagged(self):
        """It does not touch the border, so it is not this case at all."""
        assert pdf_vector.open_side_regions(_three_sided(open_side="closed"),
                                            PPX, 40, 40, 20.0,
                                            min_sqft=20.0) == []

    def test_open_ground_is_not_flagged(self):
        """The discriminator: outside is backed on ONE side, not three. Without
        it, FLOOR PLAN's 985.5 sqft outside component and its 122.7 sqft
        balcony strip would both come in as 'rooms'."""
        n = 600
        m = np.zeros((n, n), np.uint8)
        m[100:100 + max(3, int(0.75 * PPX)), :] = 255      # one wall, open field
        assert pdf_vector.open_side_regions(m, PPX, 0, 0, 12.0,
                                            min_sqft=20.0) == []


def test_floor_plan_flags_its_common_area_and_nothing_else():
    import plan_doctor
    with open(require_corpus_file("FLOOR PLAN.pdf"), "rb") as f:
        s = pdf_vector.parse(f.read())
    flags = s["meta"]["open_side_regions"]
    assert len(flags) == 1, flags                      # not the outside, not the balcony
    r = flags[0]
    assert r["open_side"] == "south"
    # 189.9 -> 101.4 on 17 Aug: admitting the `ar stairs` wall (Phase 1
    # attempt 7) put the STAIRCASE inside the wall ring, so the flagged
    # open-side region is now the LOBBY ALONE — and it closes to 94.2 sqft
    # against a printed 15'8" x 6'2" = 96.6, within 2.4 sqft. The flag got
    # more precise, not weaker.
    # 101.4 -> 94.6 on 17 Aug with pair-built walls: the lobby is now measured
    # between the true wall faces. Its closed area 88.0 sits against a printed
    # 15'8" x 6'2" = 96.6 — the printed figure is WALL-INCLUSIVE (§10.2 D-10),
    # so a clear-inside measurement reading slightly under it is expected.
    # 94.6 -> 96.9 on 20 Aug with the DERIVED pairing floor: the lobby's short
    # wall ends stopped being painted as two median-thickness plates, so its
    # measured extent grew by the artefact that was there. Re-based on the
    # PRINTED figure per §0.1, not on the new code: 96.9 sits 0.3 sqft from the
    # printed 96.6, where 94.6 sat 2.0 short. The drawing's own number moved
    # this, and it moved TOWARD it.
    assert r["area_as_drawn_sqft"] == pytest.approx(96.9, abs=1.5)
    assert r["side_backed_pct"]["N"] > 90 and r["side_backed_pct"]["E"] > 90 \
        and r["side_backed_pct"]["W"] > 90
    d = plan_doctor.diagnose(s)
    asks = [i for i in d["issues"] if i["tag"] == "space_open_on_one_side"]
    assert len(asks) == 1 and asks[0]["level"] == "ask"
    # an ASK must not change the grade: it is a question, not a defect in us
    assert d["grade"] == "C"


# --- the COLLINEAR SEAL criterion (17 Aug 2026) ------------------------------
# Built, measured, REVERTED — kept because the criterion is right and the
# function is what a future fix builds on. The blanket 4 ft close bridges ANY
# gap of that size, including the gap between two parallel walls, which is a
# room: it filled FLOOR PLAN's C.TOILET (3.9 ft interior) while A.TOILET
# (4.5 ft) survived. Wiring this in instead fixed FLOOR PLAN (+110.3 sqft of
# carpet, R-8 87.2 -> 92.5) and destroyed the fragmented sheets (FIRST FLOOR
# 11 rooms -> 2, R-2 96.8 -> 0.0), whose wall fragments are not collinear.
class TestCollinearBridges:
    def test_a_break_in_one_wall_run_is_bridged(self):
        got = pdf_vector.collinear_bridges([(0, 0, 10, 0), (13, 0, 25, 0)],
                                           4.0, 0.35)
        assert got == [((10, 0.0), (13, 0.0))]

    def test_two_parallel_walls_are_never_bridged(self):
        """This is C.TOILET: a 3.9 ft room, not a 3.9 ft hole in a wall."""
        assert pdf_vector.collinear_bridges([(0, 0, 0, 7), (3.9, 0, 3.9, 7)],
                                            4.0, 0.35) == []

    def test_a_gap_wider_than_the_limit_stays_open(self):
        assert pdf_vector.collinear_bridges([(0, 0, 10, 0), (20, 0, 30, 0)],
                                            4.0, 0.35) == []

    def test_offset_fragments_are_not_collinear(self):
        """Why the fragmented sheets collapsed: their wall pieces are offset,
        so they are not breaks in a run and nothing bridges them."""
        assert pdf_vector.collinear_bridges([(0, 0, 10, 0), (13, 1.2, 25, 1.2)],
                                            4.0, 0.35) == []


# --- PASS 1 / PASS 2 SEPARATION (17 Aug 2026) --------------------------------
# One 4 ft kernel was doing two jobs: welding disconnected fragments into a
# building, and closing doorways. Fixing either half broke the other, so they
# are now separate functions. The separation is CORRECT and INSUFFICIENT: it
# fixes a cleanly drawn sheet and cannot rescue a fragmented one, because
# there the close is not welding a wall network but substituting for one.
class TestWeldVsBreak:
    def test_offset_fragments_of_one_run_are_welded(self):
        """What a fragmented sheet needs: pieces that do not line up."""
        assert pdf_vector.weld_bridges([(0, 0, 10, 0), (13, 1.2, 25, 1.2)], 4.0)

    def test_two_parallel_walls_are_never_welded(self):
        """C.TOILET: a 3.9 ft ROOM, not a 3.9 ft hole. The weld runs ALONG a
        wall; the line between two facing walls runs ACROSS the space."""
        assert pdf_vector.weld_bridges([(0, 0, 0, 7), (3.9, 0, 3.9, 7)], 4.0) == []

    def test_a_doorway_is_the_break_pass_not_the_weld(self):
        segs = [(0, 0, 10, 0), (13, 0, 25, 0)]
        assert pdf_vector.collinear_bridges(segs, 4.0, 0.35) == [((10, 0.0), (13, 0.0))]

    def test_the_index_keeps_far_apart_walls_out_of_the_scan(self):
        """BRICK WORK has 4,960 segments; the naive pass generated 620,275
        candidate pairs. Segments a long way apart must never be compared."""
        far = [(0, 0, 10, 0), (500, 500, 510, 500)]
        assert pdf_vector.weld_bridges(far, 4.0) == []


def test_closest_pair_is_exact_and_uncapped():
    """The MST that bridges footprint components used to search a DECIMATED
    400-point sample of each component's contour (22 Aug 2026, removed). Those
    points are what DECIDES the nearest pair, and the resulting bridge length
    is what `max_bridge` accepts or rejects — so subsampling them moves the
    bridge to whichever sampled point happened to survive. Every sheet in the
    corpus was over the cap: 1491 / 2101 / 4159 / 6719 points in one component.

    The cap existed because the old code built the whole distance matrix.
    `_closest_pair` chunks the rows instead, so it is exact at any size."""
    import numpy as np
    from pdf_vector import _closest_pair
    a = np.array([[0.0, 0.0], [10.0, 10.0]])
    b = np.array([[3.0, 4.0], [100.0, 100.0]])
    assert abs(_closest_pair(a, b, chunk=1)[0] - 5.0) < 1e-9

    rng = np.random.default_rng(0)                 # bigger than any one chunk
    A, B = rng.random((1500, 2)) * 100, rng.random((1300, 2)) * 100
    full = float(np.linalg.norm(A[:, None, :] - B[None, :, :], axis=2).min())
    assert abs(_closest_pair(A, B)[0] - full) < 1e-9
    assert abs(_closest_pair(A, B, chunk=7)[0] - full) < 1e-9   # chunk-invariant


def test_derived_seal_prefers_drawn_then_printed_then_says_underived():
    """The seal's source order is a §0.1 order (24 Aug 2026): DRAWN leaves,
    then the PRINTED opening schedule, then UNDERIVED — never a silent default,
    and never our own cut widths, which come out of the mask the seal makes.

    The derivation is REPORTED, not applied: on real sheets the drawn leaves
    measure 2.2-3.1 ft while the working seal is 4.0, and the difference is the
    FRAGMENT WELD job the same kernel is silently also doing. Wiring it dropped
    GHATIKIA to 1 room and FIRST FLOOR's R-2 to 57.1."""
    from pdf_vector import derived_seal_ft
    ft, src = derived_seal_ft([2.2, 2.5, 3.0, 3.1, 3.2, 7.0])
    assert (ft, src.split()[0]) == (3.2, "p90")      # p90 drops the freak 7 ft
    ft, src = derived_seal_ft([2.5, 3.0], [2.5, 3.0, 3.25, 3.75, 7.0])
    assert ft == 3.75 and "printed schedule" in src  # too few leaves -> schedule
    ft, src = derived_seal_ft([], None)
    assert ft == 4.0 and src.startswith("UNDERIVED")  # said, not defaulted


def test_the_seal_actually_applied_is_still_the_default():
    """Guard on the revert: the derivation is reported only."""
    path = require_corpus_file("FLOOR PLAN.pdf")
    with open(path, "rb") as f:
        seal = pdf_vector.parse(f.read())["meta"]["route"]["seal"]
    assert seal["applied_ft"] == 4.0
    assert seal["status"] == "REPORTED, NOT APPLIED"
    assert seal["derived_ft"] < seal["applied_ft"]


def test_schedule_door_widths_exclude_windows_and_ventilators():
    """A window cannot be a doorway, so it cannot size a doorway derivation
    (24 Aug 2026). BRICK WORK's schedule reads eight rows and three of them —
    a ventilator and two windows — were entering its p90 and taking it to
    6.0 ft where the doors alone give 3.75."""
    from opening_schedule import door_widths_ft
    sched = {"D": {"w_ft": 3.75}, "D1": {"w_ft": 3.25}, "D2": {"w_ft": 3.0},
             "D3": {"w_ft": 2.5}, "SD": {"w_ft": 7.0},
             "V": {"w_ft": 2.0}, "W": {"w_ft": 5.0}, "W1": {"w_ft": 6.0}}
    assert door_widths_ft(sched) == [2.5, 3.0, 3.25, 3.75, 7.0]
    assert door_widths_ft(None) == []


class TestNoThresholdOnACluster:
    """NO THRESHOLD MAY SIT ON A CLUSTER (29 Aug 2026, Rahul) — the whole ppf
    cliff reduces to one sentence, and this turns it into an instrument.

    `_geometry_wall_segs`'s private 11.04 in ceiling sat ON TOP of GHATIKIA's
    11 in external-wall peak (30 pairs at 11 in, 86 at 9 in), so 26 pairs sat
    within 1% above it and a 0.28% scale change moved them across en masse —
    footprint +28.4%."""

    def test_it_reproduces_the_known_cliff(self):
        from pdf_vector import threshold_margins
        gaps = [11.0] * 30 + [9.0] * 86 + [4.0] * 171 + [5.0] * 41
        rows = {r["threshold"]: r for r in threshold_margins(
            gaps, {"ceiling": 11.04, "w3_max": 18.0})}
        assert rows["ceiling"]["latent_cliff"] is True
        assert rows["ceiling"]["nearest_peak_in"] == 11
        assert rows["ceiling"]["pairs_within_5pct"] == 30
        assert rows["w3_max"]["latent_cliff"] is False   # 18 in is near nothing

    def test_a_sizing_threshold_on_its_own_peak_is_not_a_cliff(self):
        """A MEDIAN necessarily lands on its own dominant peak — that is what a
        median does. Without this split the instrument cries wolf on every
        sheet: it flagged `median wall W` on all four."""
        from pdf_vector import threshold_margins
        gaps = [4.0] * 171 + [9.0] * 86
        (r,) = threshold_margins(gaps, {"median_wall": 4.0},
                                 sizing={"median_wall"})
        assert r["on_a_cluster"] is True        # it IS on the peak
        assert r["latent_cliff"] is False       # and that is correct there
        assert r["kind"] == "sizing"
