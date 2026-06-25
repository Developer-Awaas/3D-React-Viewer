"""Step 4 — model output -> plan JSON (the bridge to builder.py).
Runs the trained ONNX model on an image, vectorises the wall mask, and emits the
schema that pipeline/builder.py consumes. Needs onnxruntime + a trained model."""
import sys, json, cv2, numpy as np
# import onnxruntime as ort   # enable when you have the model

def mask_to_rooms(mask, metres_per_pixel):
    """Turn the predicted wall mask into room rectangles + wall openings (schema).
    Reuse the OpenCV logic from tools/auto_plan.py here: threshold walls -> Hough ->
    cluster -> gap-aware merge -> rooms via flood fill -> emit rooms[]."""
    rooms = []   # TODO: fill using the same vectorisation we already wrote
    return {"units":"metres","ceiling_height":2.5,"rooms":rooms}

def run(img_path, mpp, out_json):
    img=cv2.imread(img_path)
    # sess=ort.InferenceSession("plan_unet.onnx"); mask=sess.run(...)   # real inference
    mask=np.zeros(img.shape[:2],np.uint8)                               # placeholder
    plan=mask_to_rooms(mask, mpp)
    json.dump(plan, open(out_json,"w"), indent=2)
    print("wrote", out_json, "-> feed to builder.py")

if __name__ == "__main__":
    run(sys.argv[1], float(sys.argv[2]), sys.argv[3])
