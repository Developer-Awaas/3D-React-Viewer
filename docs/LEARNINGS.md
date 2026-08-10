# Drishti learning log (written by Plan Doctor — one line per parse; Claude reads this each session)

<!-- This file grows automatically: every time a plan is parsed on this machine,
     the Plan Doctor appends one line here (filename | grade | reason). Run the
     backend and upload a plan, or run `python server/doctor_daemon.py`, to see
     it populate. The nightly report lands in docs/DOCTOR-DAILY.md. -->
- 2026-07-23 18:48 | FLOOR PLAN.pdf | grade B (76/100) | tags: rooms_unlabeled, scale_column_guess | Scale was inferred by assuming the columns are 12 inches wide. If this plan uses 9-inch columns, every dimension is ~33% off — cross-check one known room size.
- 2026-07-23 19:10 | download (1).jpg | grade C (40/100) | tags: door_width_odd, efficiency_low, ml_reader, scale_assumed, tiny_rooms | Efficiency 15% is below the typical 55-90% band — some rooms were probably missed, so carpet is under-counted.
