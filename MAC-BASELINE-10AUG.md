# Mac baseline — 10 Aug 2026

Commit: 2c16f6c (branched from fix/all-22)
Python 3.12.13 · Node 24.15.0 · torch 2.13.0 · Mac (no CUDA)

## Must not move without a written reason

Backend:  333 passed, 1 skipped, 0 failed
Frontend: 29 passed
Build:    clean

batch_eval (run from repo root: python server/batch_eval.py)

plan                                          envelope  dr  wn  rm  ty
BRICK WORK LAYOUT.pdf                          30x49ft   9  14  11   9
FLOOR PLAN.pdf                                114x36ft  12   1   9   8
NEELACHALA HOMES GHATIKIA FLAT NUMBERS.pdf     80x48ft  27  42   9   9
neelachala FIRST FLOOR.pdf                     38x64ft  16  19   7   7
4/4 clean, no health flags

## Notes
- ty 0->9 / 0->8: tesseract installed 10 Aug switched ON the G2 OCR room-label
  path (dormant since 22 Jul). Feature, not regression — `DRISHTI_OCR=0`
  reproduces the old 0/0/9/7, every other column unchanged.
- Windows parity confirmed: 311 there = 318 here (+7 corpus tests now run)
- The 1 skip is the GPU render test — expected on Mac
- batch_eval reads PDFs only; the 3 DWGs are covered by pytest
- CubiCasa/TF2 not installed on Mac; "No module named floortrans" at
  startup is expected and harmless
