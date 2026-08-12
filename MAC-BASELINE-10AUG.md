# Mac baseline — 10 Aug 2026

Commit: 2c16f6c (branched from fix/all-22)
Python 3.12.13 · Node 24.15.0 · torch 2.13.0 · Mac (no CUDA)

## Must not move without a written reason

Backend:  405 passed, 1 skipped, 0 failed
Frontend: 29 passed
Build:    clean

batch_eval (run from repo root: python server/batch_eval.py)

plan                                          envelope  dr  wn  rm  ty  col   foot
BRICK WORK LAYOUT.pdf                          30x49ft  11  20  11   9   15   1244
FLOOR PLAN.pdf                                 95x30ft  12   1  12  12   26   1414
NEELACHALA HOMES GHATIKIA FLAT NUMBERS.pdf     80x48ft  27  42  16  15   40   2661
neelachala FIRST FLOOR.pdf                     38x64ft  16  19   9   9    0   1664
4/4 clean, no health flags

## Notes
- col/foot columns added 12 Aug after columns moved 26 -> 0 UNSEEN on
  FLOOR PLAN (fixed-point tolerance left behind by a scale change). BRICK WORK
  14 -> 15 columns: the acceptance band is now the SHORT side per C-4, which
  admits one more box on that sheet.
- rm/ty rose 11 Aug (FLOOR PLAN 9->11, GHATIKIA 9->14, FIRST FLOOR 7->9):
  footprint now comes from the outer wall RING (W-1) instead of the raster
  border, so interior rooms no longer leave with the outside. GHATIKIA and
  FIRST FLOOR are NOT accepted on this - both FAIL R-2 (58.6% / 31.1%) and are
  parked in ground_truth.json. Only FLOOR PLAN is validated (R-2 96.0%).
- FLOOR PLAN 114x36 -> 95x30 (11 Aug): golden RE-BASELINED, not a regression.
  The sheet's own printed room dimensions disproved the old envelope six times
  (R-2 median match 61.5% -> 96.4%); evidence + superseded value in
  plans/ground_truth.json -> envelope_rebaseline. BRICK WORK dr/wn 9/14 ->
  11/20: opening tags now read by OCR (Stage A) at the sheet's own schedule
  sizes (TG-5).
- R-8 (printed vs parsed built-up) is KNOWINGLY RED on FLOOR PLAN: 1161 parsed
  vs 1705 printed = 68.1%. Room COVERAGE is the open gap (9 pockets of ~16
  rooms); sizes are now right. It must RISE, never silently fall.
- ty 0->9 / 0->8: tesseract installed 10 Aug switched ON the G2 OCR room-label
  path (dormant since 22 Jul). Feature, not regression — `DRISHTI_OCR=0`
  reproduces the old 0/0/9/7, every other column unchanged.
- Windows parity confirmed: 311 there = 318 here (+7 corpus tests now run)
- The 1 skip is the GPU render test — expected on Mac
- batch_eval reads PDFs only; the 3 DWGs are covered by pytest
- CubiCasa/TF2 not installed on Mac; "No module named floortrans" at
  startup is expected and harmless
