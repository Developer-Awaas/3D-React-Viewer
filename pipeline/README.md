# Pipeline — making the room work durable

Two halves of "2D plan -> 3D":

1. **DESCRIPTION -> 3D  (done, deterministic):** `builder.py` + `SCHEMA.md`.
   Rooms are DATA (`sample_plan.json`), not one-off scripts. Edit the JSON, rebuild.
   This is where all the hand-debugged geometry now lives, reusably.

2. **IMAGE -> DESCRIPTION  (needs training, see ml/):** a model reads a plan image and
   outputs the JSON schema. Train it on a GPU (Colab/Kaggle) using `ml/`. Its output
   feeds straight into `builder.py`.

So the manual room work is NOT throwaway — it's half #1 of the real pipeline, and the
schema is the exact thing the model in half #2 will produce.
