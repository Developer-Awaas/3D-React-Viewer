# ML training scaffold (run on a GPU — Colab/Kaggle, NOT in this sandbox)

Goal: image -> the plan JSON schema (SCHEMA.md), which builder.py turns into 3D.

Pipeline:
  1. prepare_data.py      — load a labelled floor-plan dataset (CubiCasa5K / R2V / RPLAN)
                            into (image, mask) pairs: wall / door / window / room classes.
  2. train_segmentation.py— train a U-Net to predict those masks. Export to ONNX.
  3. (optional) a YOLO detector for furniture symbols (bed, WC, basin, ...).
  4. infer_to_schema.py   — run the model on a new image, vectorise the masks, and emit
                            plan JSON (rooms, walls, openings) for builder.py.

Datasets:
  - CubiCasa5K  : ~5,000 annotated flats  (best starting point)
  - R2V / RPLAN : additional labelled plans
  - Synthetic   : generate plans with known labels (free) to bootstrap.

These scripts are a STARTING SKELETON, not turnkey — they need a GPU + the dataset.
