"""Tests for the TF2DeepFloorplan adapter's PURE part — the boundary-mask ->
(wall segments, opening boxes) conversion. The TensorFlow inference path needs
the model + GPU and is validated on the user's machine, not here."""
import numpy as np

import tf2_floorplan as tf2


def test_masks_to_detections_extracts_walls_and_openings():
    # synthetic boundary map: a rectangular wall loop (class WALL) with a gap
    # filled by an OPENING patch
    H, W = 200, 300
    b = np.zeros((H, W), dtype=np.int32)
    b[20:180, 20:24] = tf2.WALL_CLASS       # left wall
    b[20:180, 276:280] = tf2.WALL_CLASS     # right wall
    b[20:24, 20:280] = tf2.WALL_CLASS       # top wall
    b[176:180, 20:280] = tf2.WALL_CLASS     # bottom wall
    b[90:110, 276:280] = tf2.OPENING_CLASS  # a door opening in the right wall
    segs, boxes = tf2.masks_to_detections(b, W, H)
    assert len(segs) > 0                    # walls vectorized
    assert len(boxes) >= 1                  # the opening became a box


def test_empty_boundary_gives_nothing():
    b = np.zeros((100, 100), dtype=np.int32)
    segs, boxes = tf2.masks_to_detections(b, 100, 100)
    assert segs == [] or len(segs) == 0
    assert len(boxes) == 0


def test_detections_matches_reader_interface():
    # the module exposes the same callable the cascade expects
    assert callable(tf2.detections)
