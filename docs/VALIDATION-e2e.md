# E2E validation on REAL captured data (vkcube + MangoHud + full collectors → detect/report)

Independent validation of the REAL pipeline. The analysis half was previously
tested only on its own synthetic generator (`docs/VALIDATION.md` — circular by
construction); this document tests on REAL captured MangoHud frametime logs with
independently injected ground truth (SIGSTOP/SIGCONT stalls + CPU-burn bursts).

* Date: 2026-10-08. Machine: CachyOS 6.18.55-1-cachyos-lts, Ryzen 9 7945HX,
  RTX 4080 Laptop (driver 615.71.09), MangoHud 0.8.4-1, display 2560x1440@144 Hz.
* Synthetic game: `vkcube` (native Vulkan implicit layer, `LD_PRELOAD=""`,
  `MANGOHUD=1`), verified on the NVIDIA GPU, VSYNC-capped at ~144.0 fps.
* Stall injector: SIGSTOP/SIGCONT bursts; ground truth = `injected_stall` marks
  (`t_send`/`t_cont`/dur) in `events.csv` via `stutter collect mark`, plus
  `runs/validate-*/e2e-ground-truth.json`. All runs use the collectors' `full`
  profile, 20 s warm-up mark, `K=2.5 / FLOOR=13.9 ms` defaults.
* Harness: `tools/e2e_validate.py` (capture), `tools/e2e_score.py`
  (detect/report + score → `e2e-score.json`). Raw logs stay in gitignored
  `raw/`; committed derived artifacts per run: `out/` (report, verdict,
  hitches, plots), `e2e-ground-truth.json`, `e2e-score.json`.
* NOTE on precision/recall below: the scorer initially matched against ALL
  hitches (primary + low tier). The numbers in the table are recomputed
  **primary-tier-only** (the tier the verdict/FIXED-definition counts);
  low-tier hits are reported separately. Method: §“Scoring method”.
* Shared-GPU caveat: a second worker (trial-wrapper) briefly ran an unlocked
  vkcube during the first clean attempt; that run was discarded. All runs below
  held `/tmp/stutter-test.lock`. The clean run still shows one real
  contamination event (local-LLM-server GPU-clock transition, §1) — reported, not hidden.

## Results table (primary tier; post-warm-up window)

| run | window | GT stalls | primary det. | precision | recall | kind verdict | steady period |
|---|---|---|---|---|---|---|---|
| clean, 10 min, no injection | 600.0 s | 0 | 28 | — (28 FP) | — | aperiodic (correct) | n.s. (p=0.93) |
| periodic 4 s, 6 min | 360.9 s | 87 | 96 | 0.906 | 1.000 | **periodic** (correct) | 4.117 s ±0.015 (+0.35% of GT 4.1026) |
| sparse 45 s, 10 min | 586.4 s | 13 | 37 | 0.351 | 1.000 | aperiodic (see §3) | n.s. |
| mixed 4 s (+45 s attempt), 10 min | 600.6 s | 158 | 172 | 0.872 | 0.949 | **periodic** (sparse unassessable — GT bug, §4) | 4.102 s ±0.008 |
| short 4 s, 2 min | 118.9 s | 29 | 32 | 0.906 | 1.000 | periodic + loud caveat | 4.152 s ±0.456 |
| borderline 20/30 ms, 6 min | 358.1 s | 88 | 97 | 0.907 | 1.000 | **periodic** (correct) | 4.085 s ±0.001 |
| correlation 4 s + 7 s CPU burns, 6 min | 359.3 s | 86 | 119 | 0.723 | 1.000 | **periodic** (correct) | 4.103 s ±0.054 |

Low tier adds ~86–259 extra detections per run (mostly vkcube 12–16 ms VSYNC
misses); recall is 1.000 in all runs except mixed (0.949, 8 FN — see §4).

## 1. CLEAN control (10 min, `runs/validate-clean-20261008-181807`)

* Verdict `aperiodic`, no significant steady (p=0.93) or sparse (p=0.02, n.s.)
  component: the no-periodic-flag half of spec (b) PASSES on real data.
* False positives: 28 primary (2.8/min) + 259 low-tier. ~24/28 primary are
  17–21 ms single frames — vkcube's natural missed-VSYNC tail (raw: 0.35% of
  frames >13.9 ms, 0.043% >17.4 ms), NOT detector bugs: any K/FLOOR setting
  that detects 40 ms stalls will also catch these.
* The remaining 4 (86–102 ms cluster at t≈340 s) are a REAL event: `gpu.csv`
  shows SM clock 210→2460 MHz + mem 405→9001 MHz at the same second, and the
  journal shows a local LLM server's API health checks at 18:24:31 local
  — a local-LLM-server GPU-clock transition preempting vkcube. Every detected hitch was
  thus accounted for: 24 app-jitter + 4 real external event. FP rate on
  genuinely quiet stretches: ~0/min; with desktop background activity: 2.8/min
  primary (mostly 17–21 ms).
* Correlation on this run ranks the LLM-server journal templates at the top of the
  log table, but the top *signal* rows are weak (|z|≤2.9, procs_running/ctxt) —
  the 50 Hz→2460 MHz clock jump did not surface in the top-25. See §7.

## 2. Periodic 4 s (`runs/validate-periodic-20261008-183029`)

* 87/87 GT recovered (recall 1.000), steady period 4.117 s ±0.015 s vs GT median
  interval 4.1026 s → **+0.35%, inside the ±5% requirement**. Flagged
  `periodic` (p=0.0025), sparse correctly not significant. PASS.
* Precision 0.906 primary (9 FP: vkcube jitter); 0.478 if low tier is counted —
  the low tier is *supposed* to be noisy, verdicts must use the primary tier.
* Alignment (marker t_cont → detected spike): median +9.1 ms, p95 +12.6 ms,
  max |err| 13.3 ms except one −83.4 ms outlier (a stall whose spike frame
  straddled the MangoHud poll boundary; the *neighbouring* frame matched).
  Pooled over all 6 injected runs (456 matches): median +8.4 ms, 99.1% within
  ±50 ms — the ≤50 ms target is met with an order of magnitude to spare.
  Residual bias ≈ +5…+13 ms is the documented SIGCONT→present latency, same
  sign and size as the +13.6 ms in `docs/VALIDATION-collect.md`.

## 3. Sparse 45 s (`runs/validate-sparse-20261008-183907`)

* 13/13 GT recovered (recall 1.000), verdict `aperiodic` — the sparse band
  (p=0.33) is NOT significant despite 13 perfectly periodic 45.1 s events.
* This is a **sensitivity finding, not a crash**: with only 13 events the
  uniform-timing null cannot reach p<0.01 in the 30–90 s band against the
  background of ~24 noise hitches. The interval histogram DOES show the truth
  (mode ≈45 s), but `kind` stays `aperiodic`. Spec (b) says the detector "must
  … flag sparse-vs-periodic correctly" — on real noisy data with n=13 it does
  not. Severity: medium. Options: (a) longer windows for sparse claims
  (≥10 min gives ~13 events at 45 s — still marginal); (b) a separate
  interval-mode test for the sparse band that is robust to background FPs;
  (c) document that sparse verdicts need ≥N events, not just ≥5 min.
* Precision 0.351 primary (24 FP from jitter). Same jitter story as clean.

## 4. Mixed 4 s + 45 s (`runs/validate-mixed-20261008-185141`) — HARNESS BUG

* My harness wrote `dur_ms=0` into `e2e-ground-truth.json` for this scenario
  (`gt.append((*inject_stall(...), 0))` discards the real duration) AND the
  sparse injector never fired (GT has 158 stalls, zero intervals >20 s —
  `next_sparse` logic raced the 4 s loop). So this run is really a second
  periodic-4 s run with 158 stalls, NOT a mixed run. The detector result
  (periodic 4.102 s, recall 0.949, 8 FN) is still valid evidence for the
  periodic case, but **mixed 4 s + 45 s was NOT tested**. A re-run with a fixed
  harness is required (left as follow-up; the tool fix is one line).
* The 8 FN: stalls whose spike merged with a neighbour across the 100 ms
  merge gap or fell on a poll boundary — worth a look when the mixed re-run
  lands, but not investigated further here.

## 5. Short window (`runs/validate-short-20261008-190441`)

* 2-minute run: verdict `periodic` for the steady band PLUS the loud warning
  `post-warm-up window 2.0 min < 5 min: sparse (30-90 s) periodicity cannot be
  assessed` and `sparse_assessable=false`. The refuse/caveat half of the spec
  PASSES on real data.
* Period 4.152 s ±0.456 s (wider error as expected with n=29).

## 6. Borderline 20/30 ms (`runs/validate-borderline-20261008-190826`)

* Recall 1.000 for BOTH 20 ms (44/44) and 30 ms (44/44) stalls at K=2.5,
  FLOOR=13.9 ms. Effective detection threshold on this box: stalls ≥20 ms are
  fully detected; the 14–18 ms vkcube jitter band is where FPs live, so the
  operating point sits exactly in the gap between jitter and real stalls.
* Below-20 ms sensitivity was NOT probed (would need 15–18 ms injections
  overlapping the jitter band — suggested follow-up, not a gap in the tool).

## 7. Correlation (`runs/validate-correlation-20261008-191621`) — WEAK PASS

* Design flaw (mine, not the tool's): 100 ms CPU burns every 7 s do NOT move
  any captured signal — PSI `cpu_some_avg10` is identical at burns and at bare
  stalls (1.9–2.1 either way), because a 4-thread `yes`-loop burst on a 32-CPU
  box is invisible in 10-ms-averaged PSI. So there was no true signal for the
  table to rank, and the top rows are degenerate (`cpufreq.*_min` z≈1e13 from
  zero-variance controls; `net_tcp.rtt_max_ms` z=−4.0 on a constant 102 ms).
* What this proves: the correlation machinery runs on real data and ranks
  *something*, but the experiment cannot confirm it ranks the *right* thing.
  A valid test needs a burn that actually moves a captured signal (e.g. 200 ms
  single-core pin causing `procs_running`/PSI excursion, or GPU-clock-affecting
  load) — left as follow-up. The degenerate-z rows are also a robustness
  finding: see bug B3.

## Pass/fail vs `docs/SPEC-detector.md` §Validation (a)(b)

| spec clause | result |
|---|---|
| (a) idle/desktop baseline ~0 FP | PARTIAL: `aperiodic` correct, but 2.8 primary + 25.9 low hitches/min on the real vkcube pipeline (24 app-jitter + 4 real LLM-server event). “~0” holds only for genuinely quiet stretches; the tool cannot distinguish app jitter from game stutter at these magnitudes. Needs a Dota-baseline rate to interpret. |
| (b) 4 s interval ±5% | PASS: +0.35% on real captures (4.117 vs 4.1026 s). |
| (b) flag sparse-vs-periodic correctly | MIXED: periodic→periodic PASS; 45 s sparse→`aperiodic` FAIL (§3, n=13 insufficient for the uniform null); mixed NOT TESTED (harness bug §4). |
| (b) precision/recall vs GT | PASS with caveat: recall 0.95–1.00 primary in all runs; precision 0.35–0.91 primary (0.06–0.59 counting low tier). Low precision is vkcube jitter, not mis-detection — but it sets the noise floor sparse detection must beat. |
| marker↔spike alignment ≤50 ms | PASS: pooled median +8.4 ms, 99.1% ≤50 ms. |

## Bugs / weaknesses found (severity)

* B1 (medium, harness — mine): mixed-scenario GT bug (`dur_ms=0`, sparse never
  injected). Fix: record real durations; decouple sparse schedule from the 4 s
  loop. Re-run mixed. — `tools/e2e_validate.py:scenario_mixed`.
* B2 (medium, detector): sparse band underpowered at n≈13 with real background
  FPs — perfectly periodic 45 s truth verdicts `aperiodic`. Needs either a
  more sensitive sparse test, an event-count (not just window-length) gate, or
  documented limits. — `detector/analyze/periodicity.py`.
* B3 (low, detector): corrupt MangoHud lines (`fps≈1e-5`, `frametime≈1e8 ms`,
  1–2 per 10-min run — MangoHud logging glitch, also noted in the collectors
  review) flow unfiltered into `frametimes.csv` and corrupt `worst_ms`
  (sparse run reports worst=99,673,900 ms). The collector should drop frames
  with `fps<1` or `frametime>1000 ms`. Trivial + local; NOT fixed (bin/stutter
  + collector code frozen for this task — left for the owning worker).
  Reproducer: `runs/validate-sparse-20261008-183907/raw/mangohud/*.csv:13578`.
* B4 (low, detector): degenerate correlation rows on real data —
  zero-variance controls yield z≈1e13 (`cpufreq.*_min`), constant signals yield
  identical z=−4.0 blocks (`net_tcp.rtt_max_ms`). Suggest capping |z| and
  dropping zero-variance (signal,column) pairs from the ranking.
  — `detector/analyze/correlation.py`.
* B5 (info, detector): `hitches.csv` is not time-sorted (negative inter-row
  gaps); harmless but confusing. Consider sorting by `t_epoch` on write.
* B6 (info, harness — mine): `e2e_score.py` initially scored primary+low tiers
  together (precision 0.06–0.59); fixed to primary-tier matching here. The
  committed `e2e-score.json` files predate the fix for the detection block —
  recompute with the current script before citing.
* No quiesce disruption: only `quiesce on --dry-run` / `off` were exercised
  (LLM service `active` before and after); real stop/start was deliberately not
  tested per the brief.

## Scoring method

`stutter detect` + `stutter report` on each run-dir (defaults K=2.5,
FLOOR=13.9 ms @144 fps, n_perm=400), then each GT `t_cont` matched to the
nearest **primary** (`severity=high`) hitch within ±0.5 s (greedy, no reuse);
err = hitch_t − t_cont. `e2e-score.json` per run holds the full verdict +
  detection block. Reproduce: `python3 tools/e2e_score.py runs/validate-<sc>-*`.

## Artifacts (committed)

* `tools/e2e_validate.py`, `tools/e2e_score.py`
* `docs/VALIDATION-e2e.md` (this file)
* per run `runs/validate-*/`: `out/` (report.md, verdict.json, hitches.csv,
  stats.json, correlation_*.csv, *.png), `e2e-ground-truth.json`,
  `e2e-score.json`, `events.csv`, `meta.json`, per-signal CSVs
  (`frametimes.csv`, `gpu.csv`, …). `raw/` excluded by gitignore.

---

## Follow-up: detector fixes on this branch (the detector-fix branch)

The independent validation above found bugs B1-B6. This branch fixes the detector-side
ones and replays the same real captures. Numbers below are from `tools/e2e_score.py`
(primary tier, `K=2.5 / FLOOR=13.9 ms`, `n_perm=400`) on the same run-dirs.

### B3 — corrupt MangoHud frames no longer poison the verdict (FIXED)

MangoHud logged one frame as `fps≈1e-5, frametime≈9.96739e7 ms`; the sparse run's
`worst_ms` was **99,673,900 ms**. Now non-finite / non-positive / `>10 s` frametimes are
rejected on load (and the live collector drops them too), tallied into
`verdict.data_quality`. Replay:

| run | rows rejected | worst_ms before | worst_ms after |
|---|---|---|---|
| sparse | 1 (`over_max`) | 99,673,900 | **82.7** |
| correlation | 2 (`over_max`) | (poisoned) | **123.9** |

### B2 — explicit sparse assessment (FIXED)

A separate, non-spectral sparse test (`verdict.sparse`): severity-gated candidates,
rate/min + bootstrap CI, interval quantiles, and a tight-mode regularity test. Replay:

| run | sparse candidates | `sparse` | period |
|---|---|---|---|
| sparse 45 s | 17 | **regular** | 45.10 s (GT 45.11) |
| clean | 8 | irregular | — |
| periodic 4 s | 90 (all dense) | none | — |
| mixed (old buggy = periodic) | 125 (dense) | none | — |

The sparse periodicity `kind` still reads `aperiodic` (that band's permutation null is
deliberately unchanged), but the explicit field now recovers the truth.

### B4 / §7 — correlation ranking (FIXED)

Ranked by Cliff's delta (z capped at ±20, constant rows dropped, BH-FDR q per row, and a
new `step` feature for clock/pstate steps). The loader also stopped discarding signals
whose rows contain blank cells (`gpu.csv`, `threads.csv` were silently dropped before).
On `runs/validate-clean-*` the LLM-server GPU-clock transition now occupies the top of the
table:

| rank | signal.column | feature | Cliff's δ | z | q |
|---|---|---|---|---|---|
| 1 | gpu.power_w | max | +0.58 | +3.1 | 6e-6 |
| 2 | **gpu.sm_clock_mhz** | max | +0.55 | +3.7 | 9e-8 |
| 3 | gpu.graphics_clock_mhz | max | +0.55 | +3.7 | 9e-8 |
| 6 | gpu.mem_clock_mhz | max | +0.49 | +3.6 | 3e-20 |
| 8 | gpu.pstate | min | −0.49 | −3.0 | 3e-20 |

Previously these rows were absent from the top-25 with `|z|≤2.9`.

### B1 — mixed harness (FIXED, live re-run pending)

`tools/e2e_validate.py:scenario_mixed` used to write `dur_ms=0` and fire the sparse
injector adjacent to the 4 s beat, so "mixed" was really periodic. It now drives two
decoupled schedules (`mixed_schedule`, unit-tested) with real durations. The old
`runs/validate-mixed-20261008-185141` is kept as-is for the record; a live 10-minute
re-run is queued behind the shared GPU lock.

### B5 — hitches.csv time-sortedness

Still open (harmless; `hitches.csv` rows are grouped by tier, not globally time-ordered).

### Primary-tier false-positive floor

On the vkcube pipeline the clean run's ~28 primary hitches are ~24 single 17-21 ms
**missed-VSYNC** frames (plus 4 from the real LLM-server clock transition). These are not
detector bugs: any K/FLOOR that detects a 40 ms stall also catches a 17-21 ms VSYNC miss.
This 17-21 ms band is the noise floor the sparse detector must beat, and it is vkcube's
signature — **for Dota the final FLOOR/K must be set from that game's own baseline
study**, not from these numbers.

### Live re-runs (the detector-fix branch)

* **Correlation (task §4) — PASS.** `runs/validate-correlation-20261008-200240`, real
  6-min vkcube capture: a pinned CPU-load burst co-timed with each 4 s stall. The
  disturbance is verified to move *recorded* signals before ranking — `sys.procs_running`
  mean 6.59 during burns vs 3.72 outside, burn-core `cpu.csv` util 15.6 % vs 6.7 % — and
  the correlation table ranks them **top-5** (`cpu.cpu_util_avg` #1, `sys.procs_running`
  #3, `cpu.cpu_util_avg.max` #5; Cliff's δ 0.63-0.71, BH-FDR q ≤ 6e-43).
* **Mixed 4 s + 45 s (task §3) — HARNESS FIXED; live re-run shows the steady component
  recovered, the sparse component only implicitly.** `scenario_mixed` is fixed and
  unit-tested (`mixed_schedule`: two decoupled schedules, real durations, no more
  `dur_ms=0`, sparse no longer adjacent to a 4 s beat); the live re-run
  (`runs/validate-mixed-20261008-202325`, 596 s window, 156 stalls incl. 13 sparse over
  600 s) confirms it. The steady 4 s component is recovered (robust modal residual
  period **3.998 s**; the interval *median* mis-reads it as 3.55 s under jitter — see
  `sparse.py:_robust_steady_period`). The 45 s sparse component is present in the
  residual (43.1, 45.2 s gaps) but the explicit regularity verdict is `irregular`: the
  real vkcube jitter (~2-7 FP/min, front-loaded while the coordinator's Dota process was
  resident) leaves ~25 extra severe candidates that break the interval-mode test at
  n ≈ 13. The conservative `>= 5` in-band modal-cluster rule keeps this honest rather
  than reporting a false `regular(34 s)`. Fixes not pursued here (needed for a firm
  mixed sparse verdict): make the harness inject sparse stalls distinctly larger than
  the periodic ones (as the synthetic spec already does), so a magnitude-relative gate
  can separate them. The sparse-**only** case — the headline B2 finding — is recovered
  cleanly (`regular(45.1 s)`).
  * Environment note: a first attempt (`validate-mixed-20261008-195219`) was truncated
    at 77 s by an *external* SIGTERM of the collector (`stop_requested signal 15`), and
    the box was contended throughout (the coordinator's live Dota process resident; a
    sibling worktree `offcpu-diag` holding the shared lock and running its own collector,
    whose cleanup can kill ours because `_is_ours` matches `REPO_ROOT in cmdline` and a
    sibling root is a *prefix* of this worktree).
