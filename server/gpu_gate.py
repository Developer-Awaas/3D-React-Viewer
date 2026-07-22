"""ONE GPU, ONE GATE. A single process-wide semaphore shared by every heavy
GPU consumer (parser/ML inference in main.py AND SDXL/SVD renders in
visualize.py).

Why: these modules used to hold two INDEPENDENT semaphores, so one render and
one ML parse could run at the same time — together they overflow a 12 GB card
(CUDA OOM -> user-facing 503s). Sharing one gate makes the second job queue
for a moment instead.

MAX_CONCURRENT_GPU (default 1) sets the slots; the older MAX_CONCURRENT_INFER
is honoured as a fallback so existing .env files keep working. Note: the gate
is per-process — run uvicorn with ONE worker on the GPU box.
"""
import asyncio
import os


def _slots():
    for var in ("MAX_CONCURRENT_GPU", "MAX_CONCURRENT_INFER"):
        v = os.getenv(var)
        if v:
            try:
                return max(1, int(v))
            except ValueError:
                pass
    return 1


GPU_SLOTS = asyncio.Semaphore(_slots())
