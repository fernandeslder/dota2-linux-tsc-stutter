# Stutter detector — README

Single entry point: `bin/stutter <subcommand> ...` (POSIX sh; works from any shell,
including fish, and from any directory). Data model: the **run-dir data contract** in
[`docs/SPEC-detector.md`](SPEC-detector.md) → "Run-dir data contract".

The project has two independent halves writing to the same contract:

| subcommands | code | owner |
|---|---|---|
| `detect` `report` `compare` `selftest` `fixed` `synth` | `detector/analyze/` | **Analysis** (this section) |
| `collect` `trial` | `detector/collect/` | Collectors (separate section of this file) |

`bin/stutter` dispatches by subcommand, so the two halves never edit each other's code.

---

## Analysis

Turns **any** run-dir that follows the contract into a verdict. Nothing here launches
Dota or touches the GUI; it runs entirely off files.

### Quickstart

```sh
./bin/stutter synth   --kind mixed --seed 1 --out /tmp/run    # synthetic run-dir (dev only)
./bin/stutter detect  /tmp/run                                # hitches + stats -> /tmp/run/out
./bin/stutter report  /tmp/run                                # + PNGs, verdict.json, report.md
./bin/stutter compare /tmp/a1 /tmp/a2 -- /tmp/b1 /tmp/b2      # A (before) vs B (after)
./bin/stutter fixed   /tmp/r1 /tmp/r2 /tmp/r3                 # check the 'fixed' definition
./bin/stutter selftest --seeds 50                             # synthetic ground-truth validation
```

Requires python3 with numpy/scipy/matplotlib (all present on this machine); plots use
the headless `Agg` backend. Unit tests: `python3 -m pytest detector/analyze/tests`.

### Hitch definition (`detector/analyze/hitches.py`)

Frame *i* is a hitch iff

```
frametime_ms[i] > K * rolling_median(frametime_ms, +-W seconds, excluding i)  AND
frametime_ms[i] > FLOOR
```

* defaults: `K=2.5`, `W=1.0 s` (centred, the centre frame is **always** excluded),
  `FLOOR = max(2 * 1000/fps_cap, 12 ms)` = 13.9 ms at 144 fps. Override with
  `--k --w --floor-ms --floor-min-ms --target-fps`.
* adjacent hitch frames whose timestamps are within `merge_gap_ms` (100 ms) merge into
  **one event**; the event time is the first hitched frame, magnitude is the max
  frametime, duration is the summed excess over FLOOR.
* a **low-severity tier** (`K=2.0`, `FLOOR=max(1.5*target, 8ms)`) is reported separately
  and never mixed into the primary hitches.
* everything before **warm-up end** is excluded. Warm-up end = the `warmup_end` mark in
  `events.csv`, else `run_start + 20 s` (documented in `verdict.json` as
  `window.warmup_source`).

Reported per run: hitches/min, worst hitch, isolated (sparse) hitches/min, 1% / 0.1%
lows (fps and ms), p50/p95/p99 frametime, frame-drop fraction, and the inter-hitch
interval distribution (histogram + quantiles + CV).

### Periodicity (`detector/analyze/periodicity.py`)

From the hitch-event timestamps, three views: **autocorrelation** of the 100 ms-binned
hitch series (FFT), a **Lomb-Scargle / periodogram** spectrum, and an **interval
histogram** with mode detection.

* Two bands are evaluated independently: **steady** 0.5-10 s (spec: steady rhythm < 10 s,
  esp. ~4 s) and **sparse** 30-90 s.
* Significance is a **uniform-timing (Poisson) null**: drop the same number of events
  uniformly at random in the same window, rebin, recompute the in-band peak power.
  `p = (1 + #null >= observed)/(1 + n_perm)`, `p < 0.01` required (default 400 perms).
  A *shuffled-interval* null is deliberately **not** used: for a near-constant interval
  (a perfect 4 s rhythm) it reproduces the same rhythm and can never reject.
* The reported period is the **median in-band inter-hitch interval** (snapped to a
  nearby spectral peak), because an impulse train's spectrum peaks at `P, P/2, P/3, ...`
  and the spectral argmax is harmonic-ambiguous. Period error is a bootstrap SD;
  `fraction_explained` is the largest fraction of hitches falling within +-10% of a
  common phase.
* If a significant steady component exists, hitches not explained by its phase are
  re-searched in the sparse band (`sparse_residual`), so a **mixed** run flags both.
* A post-warm-up window < **5 min** sets `sparse_assessable=false` and adds a loud
  warning: sparse (30-90 s) verdicts are **refused/caveated** on short windows.
* `kind` ∈ `periodic | sparse | mixed | aperiodic | insufficient`.

### Sparse hitches (`detector/analyze/sparse.py`)

The sparse *band* permutation test above is underpowered when the sparse rhythm
contributes only ~10-15 events (the uniform-timing null cannot beat the vkcube jitter
floor), so a perfect 45 s rhythm can still verdict `aperiodic`. On top of it, an
**explicit sparse assessment** answers the sparse question directly and cheaply:

* **candidates** = post-warm-up primary hitches with magnitude ≥
  `max(1.5·FLOOR, FLOOR + 6 ms)` — real sparse stalls are much larger than the jitter
  that sits just above FLOOR. If a significant steady rhythm exists, hitches explained
  by its phase are removed first, so a *mixed* 4 s + 45 s run reduces to its sparse
  residual. The phase uses a **robust modal steady period** (the interval median is
  fragile under jitter: a real mixed capture read 3.55 s by median vs 4.00 s by mode).
* **rate**/min with a Poisson bootstrap CI, and the interval quantiles + CV.
* **sparse-regular test**: take the inter-candidate intervals in the 30-90 s band, find
  the histogram mode, and require a tight modal cluster (≥ 5 intervals, within ±25 % of
  the mode, CV ≤ 0.15, ≥ 50 % of band intervals). Period = median of the cluster. ≥ 5 is
  conservative on purpose: with fewer, an n≈13 rhythm cannot be separated from the FP
  background and the tool prefers `irregular` over a confident false positive.

Reported in `verdict.json` as `sparse`: `assessment ∈ none | irregular | regular`
with `period_s`/`label` when regular, `residual_period_s`, and sample-size caveats.

### Correlation (`detector/analyze/correlation.py`)

Generic — **no signal names are hardcoded**. For *every* numeric column of *every*
`<name>.csv` in the run-dir, the signal in a window centred on each hitch is compared
against the same window at many random non-hitch control times (`20x`, min 200). Fast
signals (median sample interval <= 1 s) use **+-500 ms**; slow signals use **+-2 s**.
Per (signal, column, feature∈{mean,min,max,step}) it reports hitch mean, control
mean/SD, `z`, Cohen's d, Cliff's delta, Mann-Whitney `p` and its BH-FDR `q`, and the
enrichment ratio; the ranked table goes to `out/correlation_signals.csv` (top 25 in
`verdict.json`).

* **ranked by effect size** (|Cliff's delta|), not by the unbounded `z`;
* `z` is capped at ±20 and features that are constant across hitches *and* controls are
  dropped (kills the `z≈1e13` zero-variance rows);
* the `step` feature (second-half − first-half window mean) catches a *step change* in a
  clock / pstate / power signal that a window mean would dilute;
* blank cells in a signal CSV become `NaN` (not a dropped row — the old loader silently
  discarded whole signals like `gpu.csv`/`threads.csv`).

Text streams (`<name>.log`) are handled at the line level: each line is normalised into
a template (digits/hex → `#`) and counted near hitches vs near controls
(`out/correlation_logs.csv`, top 15 in `verdict.json`).

### Blocked-on analysis (`detector/analyze/blocked.py`)

The `offcpu` collector writes a **transition log** of every game thread's
`(state, syscall, wchan)` in `threads_blocked.csv` (see
[`docs/DETECTOR-COLLECT.md`](DETECTOR-COLLECT.md)). For every hitch this module
looks at the window `[hitch_start - max(50 ms, magnitude_ms), hitch_end]` and, per
thread, measures how much of the window its intervals cover in each bucket —
producing a ranked table of *what each thread was blocked on*:

* rows are keyed by `(thread name, state, syscall, wchan)`; the main thread
  (`tid == meta.game_pid`) is labelled `comm [main]` so it is not merged with the
  other threads of the same name;
* `hitches` / `% hitches` = share of hitches in which the most-blocked thread of
  that name spent `>= 5%` of the window in the bucket (e.g. *main thread in
  `futex`/`futex_wait_queue_me` in 70% of hitches*);
* `coverage` = mean fraction of the window covered when present;
* `R` (running) is excluded from the ranking — a running thread is not blocked;
* a **per-thread-name CPU table** comes from `threads_cpu.csv` (1 Hz per-thread
  `cpu_pct`, aggregated by name); when that file is absent, the fraction of wall
  time each name spent in state `R` is reported instead (`cpu_source`).

Results land in `verdict.json → blocked`, `out/blocked_on.csv` and a
`## What the threads were blocked on during hitches` section of `report.md`. Run-dirs
without the off-CPU data (e.g. `runs/live-baseline-1`) return
`{"available": false, ...}` and the report says so instead of guessing. The raw
`threads_blocked.csv` / `threads_cpu.csv` are **not** fed into the generic
correlation table.

### Outputs

* `out/hitches.csv` — `t_epoch,t_end,magnitude_ms,excess_ms,duration_ms,n_frames,severity`
* `out/stats.json`, `out/verdict.json`, `out/report.md`
* `out/correlation_signals.csv`, `out/correlation_logs.csv`
* `out/blocked_on.csv` — ranked blocked-on table (see below)
* `out/*.png` — frametime trace with hitches, hitch timeline, interval histogram,
  autocorrelation/spectrum, correlation panel (headless `Agg`).

#### `verdict.json` schema (version `1.0`)

| key | meaning |
|---|---|
| `schema_version` | `"1.0"` |
| `tool` | `"stutter"` |
| `run_id`, `run_dir`, `generated_utc` | identity + ISO-8601 UTC timestamp |
| `config` | resolved hitch config (K, W, FLOOR, merge gap, target fps, derived `target_ms`) |
| `hitch_definition` | human-readable rule + low tier |
| `window` | `t_start, warmup_end, t_end, duration_s, n_frames, warmup_source` |
| `hitches` | `count, per_min, worst_ms, worst_t, median_ms, low_count, low_per_min, isolated_count, sparse_per_min` |
| `frametime` | `p50_ms, p95_ms, p99_ms, fps_1pct_low, fps_0.1pct_low, mean_fps, frame_drop_frac, n_frames` |
| `data_quality` | `rows_total, rows_kept, rows_rejected, reasons{nonfinite,nonpositive,over_max}, max_plausible_ms, rejected_examples` |
| `intervals` | `count, min/max/mean/p50/p90/p95/p99_s, cv, hist{edges_s,counts}` |
| `periodicity` | `kind, window_s, window_min, sparse_assessable, steady, sparse, sparse_residual, interval_hist, autocorr_peak, lombscargle_peak, warnings`; each band: `period_s, spectral_peak_s, period_source, power, p_value, period_err_s, fraction_explained, significant` |
| `sparse` | explicit sparse assessment: `assessment(none\|irregular\|regular), label, period_s, residual_period_s, n_sparse_candidates, severity_min_ms, rate_per_min, rate_ci95_per_min, rate_ci_method, interval_quantiles_s, mode_s, mode_cluster{n,cv,fraction}, residual_applied, steady_period_s, caveats` |
| `correlation` | `{signals: [...top 25...], logs: [...top 15...]}` |
| `blocked` | blocked-on table: `available`, `window_rule`, `n_hitches(_with_data)`, `rows` (thread/state/syscall/wchan/hitches/frac/coverage), `main_thread`, `per_thread_cpu`, `cpu_source` |
| `warnings` | list of strings |
| `artifacts` | relative paths of produced files |

### `compare` — A/B with run-to-run variance

```sh
./bin/stutter compare <A runs...> -- <B runs...> [--effect-threshold 0.5]
```

For each metric (hitches/min, worst hitch, p95/p99 frametime, 1% / 0.1% lows, mean fps,
steady-periodic flag) it reports mean±SD in A and B, the bootstrap CI of the **B-A**
difference, Cohen's d and Cliff's delta, and a verdict:

* `inconclusive` if the CI contains 0, or `|d| < effect_threshold`, or either side has
  < 2 runs (run-to-run variance is unknown then);
* otherwise `improved` / `worse` by the metric's direction.

Overall = `worse` if any metric is worse (no improvements), `improved` if any improves
and none worsens, `mixed` if both, else `inconclusive`. Writes `compare.json`/`compare.md`.

### `fixed` — the "fixed" definition

Reads thresholds from `detector/analyze/fixed_def.json` (**PROVISIONAL** — see
[`docs/FIXED-DEFINITION.md`](FIXED-DEFINITION.md)) and checks a set of run verdicts:
no significant periodic component < 10 s, sparse rate <= bound, 0.1% low >= bound,
minimum run duration, minimum consecutive runs. Exit code 0 = pass, 2 = fail. Writes
`fixed.json`/`fixed.md`.

### `selftest` — synthetic ground truth

`./bin/stutter selftest --seeds 50 --scenario-seeds 12`

Generates synthetic runs (4 s periodic, 45 s sparse, mixed, clean) with injected ground
truth plus companion signals correlated with a *subset* of the hitches, and asserts:
period recovery within +-5%, hitch precision/recall >= 0.95, **no** periodic flag on
clean traces over >= 50 seeds, warm-up exclusion, and prints a K/FLOOR sensitivity
table. Real numbers are in [`docs/VALIDATION.md`](VALIDATION.md). Nothing here runs Dota.

### Known gaps / limitations (honest)

* Validated against synthetic traces **and** the real vkcube+MangoHud e2e captures
  ([`docs/VALIDATION-e2e.md`](VALIDATION-e2e.md)). Live-Dota numbers (run-to-run
  variance, the final FLOOR/K, real signal names) are still pending; `fixed_def.json`
  thresholds are PROVISIONAL until a baseline variance study is done.
* Periodicity with very few events (< ~6) is unreliable; the tool says
  `insufficient`/caveats rather than guessing. The explicit `sparse` assessment needs
  >= 5 min and >= 8 candidates for a firm call; below that it caveats.
* Correlation is a *ranking* tool (Cliff's delta / z / Mann-Whitney + BH-FDR), not
  proof of causation; with few hitches the control distribution is small.
* **Noise floor (primary tier).** On the vkcube pipeline ~24/28 primary hitches in the
  clean run are 17-21 ms single frames — vkcube's natural missed-VSYNC tail, not detector
  bugs: any K/FLOOR that detects 40 ms stalls also catches them. This is the noise floor
  sparse detection must beat. For **Dota** the final FLOOR/K are to be set from that
  game's own baseline study, not from the vkcube numbers.
* `--k/--floor` sensitivity is reported, not auto-tuned.

### Layout

```
bin/stutter                 # POSIX sh entry (dispatches analysis vs collectors)
detector/analyze/
  config.py  rundir.py  hitches.py  periodicity.py  sparse.py  correlation.py
  stats.py   reporting.py  compare.py  fixed.py  fixed_def.json  synth.py
  selftest.py  cli.py  __main__.py
  tests/test_analyze.py    # pytest, synthetic, deterministic
```

---

## Trial (orchestration-friendly wrapper)

The `trial` half wraps the collectors into **one call** so a GUI-driving agent can run a
whole measurement and get a verdict. Code: `detector/trial/`; the collectors themselves
are documented in [`docs/DETECTOR-COLLECT.md`](DETECTOR-COLLECT.md).

| subcommand | purpose |
|---|---|
| `stutter preflight` | read-only **PASS/WARN/FAIL** go/no-go checks before a trial |
| `stutter launchopts` | read/write Dota 2 (appid **570**) Steam `LaunchOptions`; build the launch string |
| `stutter trial run` | quiesce → collect → wait → warm-up → window → stop → quiesce off → detect + report |
| `stutter trial cleanup` | stop collectors/loggers and restore quiesce (idempotent, safe anytime) |

### `preflight` — is this box ready?

```sh
./bin/stutter preflight           # human-readable
./bin/stutter preflight --json    # machine-readable (list of {name,status,detail,data})
```

Every check is independent, read-only, and returns `PASS`, `WARN` (works but can bias the
numbers), or `FAIL` (do not trust a run). Checks: NVIDIA GPU + driver, the Vulkan device
Dota would use (`vulkaninfo --summary`), pstate/clocks/persistence, `nvidia-powerd`,
a local LLM server, running containers, Steam, MangoHud + its Vulkan layer, Dota install + the current
`LaunchOptions`, display mode/refresh/VRR/compositing (`kscreen-doctor` + KWin DBus), CPU
governor/EPP, platform profile, free disk, kernel/driver versions, and **AC power**.
Exit code is `1` iff any check `FAIL`s. On this laptop AC unplugged is a hard `FAIL`.

### `launchopts` — the exact string, without hand-editing VDF

Dota's launch options live in `userdata/<id>/config/localconfig.vdf` under
`Software/Valve/Steam/apps/570/LaunchOptions`. A machine can have **several** Steam accounts, so
the tool enumerates them all and picks the one that actually holds a `570` node, preferring
one that already sets `LaunchOptions` and the most-recently-logged-in account. Override
with `--account <id>` or `--vdf <path>`. (`detector/trial/vdf.py` is a real KeyValues
parser that edits **only** the `LaunchOptions` token/line, leaving the other 90 KB
byte-identical.)

```sh
./bin/stutter launchopts --get                 # print current value (raw)
./bin/stutter launchopts --get --json          # {steamid, vdf, launch_options}
./bin/stutter launchopts --build --mangohud --base "-threads 8 +fps_max 144"
#   -> native / proton / wrapper strings combining MangoHud env + the options under test
./bin/stutter launchopts --set "MANGOHUD=1 MANGOHUD_CONFIGFILE=/... %command% -vulkan"
./bin/stutter launchopts --backup              # copy to ledger/backups/ with a timestamp
./bin/stutter launchopts --restore ledger/backups/localconfig.vdf.<id>.<ts>.bak
./bin/stutter launchopts --steam-shutdown      # helper: quit Steam so writes stick
```

Safety: **Steam must be quit for a write to stick** (it rewrites the file on exit), so
`--set` refuses while Steam is running unless `--force`; every write first backs the file
up to `ledger/backups/`, writes atomically, and **re-reads to verify**.

### `trial run` — one sequenced measurement

```sh
./bin/stutter trial run --label baseline --minutes 15 --quiesce
./bin/stutter trial run --label test --minutes 15 --warmup 20 --profile lite
# tests (synthetic app instead of Dota):
./bin/stutter trial run --label vkcube --minutes 0.3 --wait-process vkcube --launch vkcube
```

Sequence (all marks land in the run-dir `events.csv`):

```
quiesce on (optional)
  -> collect start           -> runs/<ts>-<label>/ + meta.json
  -> wait for the process (default dota2) AND MangoHud frames flowing (--timeout)
  -> mark match_loaded
  -> warm-up sleep (--warmup)
  -> mark warmup_end
  -> record N minutes        (1-minute heartbeats; abort if the process dies
                              or frames stop for >10 s)
  -> mark window_end
  -> collect stop
  -> quiesce off             (ALWAYS, incl. Ctrl-C/SIGTERM/exception)
  -> detect + report (out/verdict.json, report.md, PNGs)
  -> print verdict
```

`meta.json` records the launch options under test, git rev, kernel, driver, GPU, profile
and the trial parameters. The verdict line reports hitches/min, worst hitch, 1%/0.1% lows,
`periodic` yes/no, `sparse` yes/no/`insufficient-window`, and the `fixed` pass/fail
(PROVISIONAL thresholds). The GUI-driving steps are in
[`docs/TRIAL-PROCEDURE.md`](TRIAL-PROCEDURE.md).

`--launch` is a **dev/test** hook (it starts the app under MangoHud itself); in production
the agent launches Dota from Steam and the wrapper only waits. `--wait-process` names the
process to watch.

### `trial cleanup`

```sh
./bin/stutter trial cleanup
```

Stops every collector and stray MangoHud wrapper **belonging to this repo/worktree**,
restores quiesce, purges `runs/.quiesce-state.json`, and verifies nothing is left. It is
scoped by process `cwd`/argv to this worktree, so on a shared box it cannot disturb another
agent's run. Safe to run at any time.

### Layout

```
detector/trial/
  vdf.py         Valve KeyValues reader + surgical editor
  steam.py       locate localconfig.vdf, get/set/restore LaunchOptions, backup, shutdown
  launchopts.py  build launch strings (MangoHud + options under test), native & Proton
  preflight.py   PASS/WARN/FAIL environment checks
  runner.py      `trial run` sequencing + `trial cleanup`
  cli.py         `preflight`/`launchopts`/`trial` dispatch
tests/test_trial_{vdf,steam,launchopts,cli,runner}.py
```

