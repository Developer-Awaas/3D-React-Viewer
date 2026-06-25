"""Step 1 — build (image, mask) training pairs from a labelled plan dataset.
Run on a machine with the dataset downloaded (e.g. CubiCasa5K). Sandbox can't."""
import os, glob, numpy as np, cv2
CLASSES = {"background":0,"wall":1,"door":2,"window":3,"room":4}

def load_pair(img_path, svg_or_mask_path):
    img = cv2.imread(img_path)
    # TODO: parse the dataset's annotation (CubiCasa uses SVG; RPLAN uses label images)
    # into a HxW integer mask using CLASSES. Placeholder:
    mask = np.zeros(img.shape[:2], np.uint8)
    return img, mask

def build_dataset(root, out):
    os.makedirs(out, exist_ok=True)
    for i, ip in enumerate(sorted(glob.glob(os.path.join(root,"**","*.png"), recursive=True))):
        img, mask = load_pair(ip, ip)            # adapt to dataset layout
        cv2.imwrite(f"{out}/img_{i:05d}.png", img)
        cv2.imwrite(f"{out}/msk_{i:05d}.png", mask)
    print("wrote pairs to", out)

if __name__ == "__main__":
    import sys; build_dataset(sys.argv[1], sys.argv[2])
