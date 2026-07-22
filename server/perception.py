"""CubiCasa perception: image bytes -> detected rooms / icons.

Load the model ONCE (call load_model() at server startup), then call detect()
per request. Mirrors the working Colab inference.
"""
import io
import os
import sys
import base64
import threading
import numpy as np
from PIL import Image

import torch
import torch.nn.functional as F
from skimage import transform

ROOM_CLASSES = ["Background", "Outdoor", "Wall", "Kitchen", "Living Room",
                "Bed Room", "Bath", "Entry", "Railing", "Storage", "Garage", "Undefined"]
ICON_CLASSES = ["No Icon", "Window", "Door", "Closet", "Electrical Applience",
                "Toilet", "Sink", "Sauna Bench", "Fire Place", "Bathtub", "Chimney"]
N_CLASSES = 44
SPLIT = [21, 12, 11]

_PALETTE = np.array([
    [30, 60, 90], [240, 180, 120], [255, 140, 90], [120, 200, 180], [150, 210, 230],
    [200, 150, 220], [230, 120, 140], [250, 220, 120], [140, 180, 120], [120, 140, 200],
    [180, 120, 90], [160, 160, 160]], dtype=np.uint8)

_MODEL = None
_ROT = None
_LOAD_LOCK = threading.Lock()   # lazy load_model() races (it os.chdir()s!)


def _device():
    return "cuda" if torch.cuda.is_available() else "cpu"


def _extract_weights(obj):
    """Dig through a (possibly multiply-wrapped) checkpoint until we reach the
    dict whose values are actual tensors (the real state_dict)."""
    if isinstance(obj, dict):
        if obj and all(torch.is_tensor(v) for v in obj.values()):
            return obj
        for key in ("model_state", "state_dict", "model", "net", "weights"):
            if isinstance(obj.get(key), dict):
                w = _extract_weights(obj[key])
                if w is not None:
                    return w
        for v in obj.values():
            if isinstance(v, dict):
                w = _extract_weights(v)
                if w is not None:
                    return w
    return None


def load_model():
    global _MODEL, _ROT
    if _MODEL is not None:
        return _MODEL
    # double-checked lock: concurrent lazy loads raced through the process-
    # global os.chdir() below (and loaded the model twice)
    with _LOAD_LOCK:
        if _MODEL is not None:
            return _MODEL

        repo = os.path.abspath(os.getenv("CUBICASA_REPO", "./CubiCasa5k"))
        weights = os.path.abspath(os.getenv(
            "CUBICASA_WEIGHTS", os.path.join(repo, "model_best_val_loss_var.pkl")))
        if repo not in sys.path:
            sys.path.insert(0, repo)

        from floortrans.models import get_model
        from floortrans.loaders import RotateNTurns

        _ROT = RotateNTurns()

        # get_model() loads its pretrained backbone via a RELATIVE path
        # ("floortrans/models/model_1427.pth"), so it must run with the repo as the
        # working directory - otherwise it grabs the wrong copy. Restore cwd after.
        prev_cwd = os.getcwd()
        os.chdir(repo)
        try:
            model = get_model("hg_furukawa_original", 51)
        finally:
            os.chdir(prev_cwd)

        model.conv4_ = torch.nn.Conv2d(256, N_CLASSES, bias=True, kernel_size=1)
        model.upsample = torch.nn.ConvTranspose2d(N_CLASSES, N_CLASSES, kernel_size=4, stride=4)

        ckpt = torch.load(weights, map_location="cpu", weights_only=False)
        state = _extract_weights(ckpt) or ckpt
        state = {(k[7:] if k.startswith("module.") else k): v for k, v in state.items()}
        missing, unexpected = model.load_state_dict(state, strict=False)
        matched = len(state) - len(unexpected)
        print(f"Weights loaded. matched_keys={matched} "
              f"missing={len(missing)} unexpected={len(unexpected)}")
        if matched == 0:
            raise RuntimeError("No weight tensors matched the model - wrong/corrupt checkpoint.")

        model.eval().to(_device())
        _MODEL = model
        return _MODEL


def _overlay_png(base_rgb, pred):
    color = _PALETTE[pred % len(_PALETTE)]
    blend = (0.5 * base_rgb + 0.5 * color).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(blend).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _infer(image_bytes):
    """Run CubiCasa once. Returns (img_uint8 HxWx3, rooms_pred HxW, icons_pred HxW)."""
    from floortrans.post_prosessing import split_prediction

    model = load_model()
    device = _device()

    img = np.array(Image.open(io.BytesIO(image_bytes)).convert("RGB"))

    max_side = int(os.getenv("MAX_SIDE_GPU", "1024")) if device == "cuda" \
        else int(os.getenv("MAX_SIDE_CPU", "512"))
    H0, W0 = img.shape[:2]
    scale = min(1.0, max_side / max(H0, W0))
    if scale < 1.0:
        img = transform.resize(img, (int(H0 * scale), int(W0 * scale)),
                               preserve_range=True, anti_aliasing=True).astype(np.uint8)
    h, w = img.shape[:2]

    x = 2 * (img.astype(np.float32) / 255.0) - 1
    x = torch.tensor(x.transpose(2, 0, 1)).unsqueeze(0).to(device)

    rotations = [(0, 0), (1, -1), (2, 2), (-1, 1)] if device == "cuda" else [(0, 0)]
    with torch.no_grad():
        preds = torch.zeros([len(rotations), N_CLASSES, h, w])
        for i, (fwd, back) in enumerate(rotations):
            rimg = _ROT(x, "tensor", fwd)
            p = model(rimg)
            p = _ROT(p, "tensor", back)
            p = _ROT(p, "points", back)
            p = F.interpolate(p, size=(h, w), mode="bilinear", align_corners=True)
            preds[i] = p[0].cpu()
            del p, rimg
            if device == "cuda":
                torch.cuda.empty_cache()
        prediction = torch.mean(preds, 0, True)

    _, rooms, icons = split_prediction(prediction, (h, w), SPLIT)
    rooms_pred = np.argmax(np.array(rooms).squeeze(), axis=0).astype(int)
    icons_pred = np.argmax(np.array(icons).squeeze(), axis=0).astype(int)
    return img, rooms_pred, icons_pred


def detect(image_bytes):
    """What did the model see? -> rooms/icons lists + preview overlays."""
    img, rooms_pred, icons_pred = _infer(image_bytes)
    h, w = img.shape[:2]
    return {
        "device": _device(),
        "width": int(w),
        "height": int(h),
        "rooms_found": [ROOM_CLASSES[i] for i in np.unique(rooms_pred) if i < len(ROOM_CLASSES)],
        "icons_found": [ICON_CLASSES[i] for i in np.unique(icons_pred) if i < len(ICON_CLASSES)],
        "rooms_overlay_png_base64": _overlay_png(img, rooms_pred),
        "icons_overlay_png_base64": _overlay_png(img, icons_pred),
    }


def wall_segments(image_bytes):
    """Run detection and vectorize the WALL pixels into line segments.
    Returns (segments, width_px, height_px)."""
    import walls
    img, rooms_pred, _ = _infer(image_bytes)
    h, w = img.shape[:2]
    wall_idx = ROOM_CLASSES.index("Wall")
    wall_mask = (rooms_pred == wall_idx).astype(np.uint8)
    return walls.vectorize_walls(wall_mask), int(w), int(h)


def detections(image_bytes):
    """ONE inference pass -> wall segments + door/window boxes (all pixels).
    Returns (segments, opening_boxes, width_px, height_px)."""
    import walls
    import openings
    img, rooms_pred, icons_pred = _infer(image_bytes)
    h, w = img.shape[:2]
    wall_idx = ROOM_CLASSES.index("Wall")
    segs = walls.vectorize_walls((rooms_pred == wall_idx).astype(np.uint8))
    boxes = openings.boxes_from_mask(icons_pred, min_area=max(30, int(0.00015 * w * h)))
    return segs, boxes, int(w), int(h)
