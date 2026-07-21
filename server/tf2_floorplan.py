"""TF2DeepFloorplan reader adapter — the COMMERCIAL-viable ML fallback.

Drop-in replacement for perception.py (CubiCasa): exposes the SAME
`detections(image_bytes) -> (segments, opening_boxes, width_px, height_px)`
interface, so the vector-first/ML-fallback cascade uses it unchanged. Select it
with env `ML_READER=tf2`.

It reuses Drishti's existing wall vectorizer + opening-box extractor — the model
only has to produce a WALL mask and an OPENING mask; everything downstream is
shared with CubiCasa.

SAFE TO IMPORT on a CPU/slim deploy: TensorFlow is imported lazily inside the
functions, exactly like perception.py, so the API still boots without TF.

Setup (on the GPU box) — see docs/TF2_SETUP.md:
  1. pip install tensorflow (CUDA build) + this repo's deps.
  2. git clone https://github.com/zcemycl/TF2DeepFloorplan and download its
     pretrained weights (Google Drive link in that repo).
  3. Point env TF2FP_MODEL at the SavedModel / weights dir.
  4. Verify the class order (see WALL_CLASS/OPENING_CLASS below) against the
     model card, then set them if they differ.

NOTE: this adapter's inference path can only be validated on a machine with TF +
the weights; the pure mask->geometry conversion is unit-tested here.
"""
import os

# Room-boundary head class indices (TF2DeepFloorplan convention: 0 background,
# 1 door/window opening, 2 wall). Override via env if the model card differs.
WALL_CLASS = int(os.getenv("TF2FP_WALL_CLASS", "2"))
OPENING_CLASS = int(os.getenv("TF2FP_OPENING_CLASS", "1"))
INPUT_SIZE = int(os.getenv("TF2FP_INPUT", "512"))

_MODEL = None      # ("tflite", interpreter) | ("saved", callable)


def _load():
    """Lazily load the TF2DeepFloorplan model once. TF2FP_MODEL points at either
    a .tflite file (RECOMMENDED — loads with zero repo code) or a SavedModel
    dir. Kept out of import time so the slim deploy boots."""
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    path = os.getenv("TF2FP_MODEL")
    if not path:
        raise RuntimeError("set TF2FP_MODEL to the TF2DeepFloorplan .tflite file "
                           "or SavedModel dir (run setup_tf2fp.bat)")
    if path.lower().endswith(".tflite"):
        import tensorflow as tf
        interp = tf.lite.Interpreter(model_path=path)
        interp.allocate_tensors()
        _MODEL = ("tflite", interp)
    else:
        import tensorflow as tf
        _MODEL = ("saved", tf.saved_model.load(path))
    return _MODEL


def _pick_heads(outputs):
    """The net has two heads: room-type logits (many channels) and room-BOUNDARY
    logits (3: bg/opening/wall). Pick by channel count so head order never
    matters. outputs: list of np arrays [1,H,W,C]."""
    boundary = min(outputs, key=lambda a: a.shape[-1])
    room = max(outputs, key=lambda a: a.shape[-1])
    return room, boundary


def _infer(image_bytes):
    """Image bytes -> (rgb_uint8, boundary_argmax HxW, room_argmax HxW).
    boundary encodes wall / opening / background per pixel."""
    import io

    import numpy as np
    from PIL import Image

    kind, model = _load()
    rgb = np.array(Image.open(io.BytesIO(image_bytes)).convert("RGB"))
    h, w = rgb.shape[:2]
    small = np.array(Image.fromarray(rgb).resize((INPUT_SIZE, INPUT_SIZE)),
                     dtype=np.float32)[None] / 255.0

    if kind == "tflite":
        interp = model
        inp_det = interp.get_input_details()[0]
        interp.set_tensor(inp_det["index"], small.astype(inp_det["dtype"]))
        interp.invoke()
        outs = [interp.get_tensor(d["index"]) for d in interp.get_output_details()]
    else:
        import tensorflow as tf
        res = model(tf.constant(small))
        outs = [np.asarray(t) for t in (res if isinstance(res, (list, tuple))
                                        else res.values() if isinstance(res, dict)
                                        else [res])]
    room_l, bound_l = _pick_heads(outs)
    boundary = np.argmax(bound_l[0], axis=-1).astype("int32")
    room = np.argmax(room_l[0], axis=-1).astype("int32")
    # resize label maps back to the original size (nearest keeps labels intact)
    boundary = np.array(Image.fromarray(boundary.astype("uint8")).resize((w, h), Image.NEAREST), dtype="int32")
    room = np.array(Image.fromarray(room.astype("uint8")).resize((w, h), Image.NEAREST), dtype="int32")
    return rgb, boundary, room


def masks_to_detections(boundary, width_px, height_px):
    """PURE: boundary label map -> (wall segments, opening boxes) using Drishti's
    shared vectorizer. Unit-tested with synthetic masks (no TF needed)."""
    import numpy as np

    import openings
    import walls
    wall_mask = (boundary == WALL_CLASS).astype(np.uint8)
    open_mask = (boundary == OPENING_CLASS).astype(np.uint8)
    segs = walls.vectorize_walls(wall_mask)
    boxes = openings.boxes_from_mask(
        open_mask, min_area=max(30, int(0.00015 * width_px * height_px)))
    return segs, boxes


def detections(image_bytes):
    """ONE inference pass -> wall segments + opening boxes. Same contract as
    perception.detections, so the cascade uses this reader interchangeably."""
    rgb, boundary, _room = _infer(image_bytes)
    h, w = rgb.shape[:2]
    segs, boxes = masks_to_detections(boundary, w, h)
    return segs, boxes, int(w), int(h)
