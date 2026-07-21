"""Pre-download EXACTLY the weights the render code will load — no more, no less.

Synchronisation guarantee: the model IDs come from visualize.required_models(),
the SAME function the runtime loaders read. So whatever you download here is
precisely what /visualize/render utilises. If someone changes a model in
visualize.py, this script downloads the new one automatically — they can't drift.

Usage (from server/, venv active):
    python fetch_models.py            # SDXL + canny + depth ControlNets
    python fetch_models.py --video    # also Stable Video Diffusion (gated; needs
                                      # `huggingface-cli login` + license accept)

Verify afterwards:
    python -c "import visualize,json; print(json.dumps(visualize.models_status(), indent=2))"
or hit GET /visualize/health and check "models_ready": true.
"""
import sys

import visualize


def _patterns(variant):
    # fp16 variant -> pull only fp16 weights + all config/tokenizer files (skips
    # the fp32 duplicates, ~halves the SDXL download). None -> take the default.
    if variant == "fp16":
        return ["*.json", "*.txt", "*.model", "**/*.json", "**/*.txt",
                "**/*.model", "**/*.fp16.safetensors"]
    return None


def main():
    include_video = "--video" in sys.argv
    models = visualize.required_models(include_video)

    print("Downloading the exact models visualize.py loads (single source of truth):\n")
    for m in models:
        tag = f" [{m['variant']}]" if m["variant"] else ""
        print(f"  - {m['name']}: {m['id']}{tag}")
    print()

    from huggingface_hub import snapshot_download

    ok = True
    for m in models:
        print(f"==> {m['id']} ...")
        try:
            path = snapshot_download(m["id"], allow_patterns=_patterns(m["variant"]))
            print(f"    done -> {path}")
        except Exception as e:
            ok = False
            print(f"    FAILED: {type(e).__name__}: {e}")
            if m["name"] == "svd":
                print("    (SVD is license-gated: run `huggingface-cli login` and "
                      "accept the license on its HF page, then retry with --video)")
    print()
    status = visualize.models_status(include_video)
    for s in status:
        print(f"  [{'OK ' if s['cached'] else 'MISS'}] {s['id']}")
    print("\nAll synced." if ok and all(s["cached"] for s in status)
          else "\nSome models are missing — see messages above.")


if __name__ == "__main__":
    main()
