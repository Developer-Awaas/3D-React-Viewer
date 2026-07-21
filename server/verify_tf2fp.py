"""Verify the TF2DeepFloorplan reader end-to-end on THIS machine:
    python verify_tf2fp.py path\to\model.tflite
Draws a synthetic floor plan, runs the full detections() path (model inference
-> wall mask -> vectorized walls + opening boxes) and prints what it found.
Passing = the model file is good and the cascade can use it."""
import os
import sys


def main():
    if len(sys.argv) > 1:
        os.environ["TF2FP_MODEL"] = sys.argv[1]
    if not os.getenv("TF2FP_MODEL"):
        print("usage: python verify_tf2fp.py <model.tflite | SavedModel dir>")
        sys.exit(2)

    import io

    from PIL import Image, ImageDraw

    # synthetic plan: white sheet, black wall rectangle with a doorway gap
    img = Image.new("RGB", (800, 600), "white")
    dr = ImageDraw.Draw(img)
    dr.rectangle([100, 100, 700, 500], outline="black", width=12)
    dr.line([400, 100, 400, 500], fill="black", width=10)     # inner wall
    dr.rectangle([395, 260, 405, 340], fill="white")          # doorway gap
    buf = io.BytesIO()
    img.save(buf, "PNG")

    import tf2_floorplan as tf2
    segs, boxes, w, h = tf2.detections(buf.getvalue())
    print(f"model loaded OK ({os.environ['TF2FP_MODEL']})")
    print(f"image {w}x{h} -> wall segments: {len(segs)}, opening boxes: {len(boxes)}")
    if len(segs) == 0:
        print("WARNING: no walls detected on the synthetic plan — check the "
              "class order (TF2FP_WALL_CLASS/TF2FP_OPENING_CLASS) against the "
              "model card.")
        sys.exit(1)
    print("VERIFY PASSED — set ML_READER=tf2 to enable in the cascade.")


if __name__ == "__main__":
    main()
