# "Fixed" statistical definition (FINAL, non-provisional)

Declared **fixed** when, across >= 3 consecutive live-spectate runs (each >= 5 min after the 20 s warm-up, one >= 15 min):

| criterion | threshold | basis (live spectate) |
|---|---|---|
| no steady periodic component | no band < 10 s with p < 0.01 | none found in any run |
| hitches/min (primary tier: frametime > 2.5x rolling median and > 13.9 ms) | <= 6 | unchanged baseline 17-55/min (7 runs); fixed runs 1.8-3.2/min |
| worst hitch | <= 100 ms | baseline 1.7-3.3 s; fixed runs 28-54 ms |
| 0.1 % low | >= 30 fps | baseline 0.8-1.6 fps; fixed runs 32-51 fps (heavy teamfights) |
| run length | every run >= 5 min, at least one >= 15 min | sparse verdicts need >= 5 min |

Run-to-run spread of the unchanged baseline (n=7 spectate runs, different matches): 16.8-54.6 hitches/min, mean ~37, SD ~11; the fixed runs sit more than 3 SD below the baseline mean and below the baseline minimum, and all hitch criteria separate the two groups with no overlap.
Implemented in `detector/analyze/fixed.py` / `fixed_def.json`; `bin/stutter fixed <run-dirs...>`.
Results: `ledger/proof/fixed-after/` (FP1-FP3 passed) and `ledger/proof/fixed-before/` (baseline-1..3 failed).
