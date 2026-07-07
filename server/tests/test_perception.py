"""Unit tests for perception helpers. These do NOT load the real model or
weights - they test the pure logic, so they run fast anywhere (incl. CI)."""
import base64
import numpy as np
import torch

import perception


def test_extract_weights_flat_state_dict():
    sd = {"a": torch.zeros(2), "b": torch.ones(3)}
    assert perception._extract_weights(sd) is sd


def test_extract_weights_single_wrapper():
    sd = {"w": torch.zeros(2)}
    ckpt = {"model_state": sd, "epoch": 5, "best_loss": 0.1}
    assert perception._extract_weights(ckpt) is sd


def test_extract_weights_double_wrapper():
    sd = {"w": torch.zeros(2)}
    ckpt = {"model_state": {"model_state": sd, "best_loss": 0.1, "epoch": 3}}
    assert perception._extract_weights(ckpt) is sd


def test_extract_weights_state_dict_key():
    sd = {"w": torch.zeros(2)}
    assert perception._extract_weights({"state_dict": sd}) is sd


def test_extract_weights_none_when_no_tensors():
    assert perception._extract_weights({"epoch": 1, "loss": 0.2}) is None


def test_overlay_png_is_valid_base64_png():
    img = np.zeros((8, 8, 3), dtype=np.uint8)
    pred = np.zeros((8, 8), dtype=int)
    s = perception._overlay_png(img, pred)
    assert isinstance(s, str) and len(s) > 0
    raw = base64.b64decode(s)
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"   # PNG magic header


def test_class_lists_match_split_sizes():
    # split = [heatmaps, rooms, icons]; class lists must match room/icon counts
    assert len(perception.ROOM_CLASSES) == perception.SPLIT[1]
    assert len(perception.ICON_CLASSES) == perception.SPLIT[2]
