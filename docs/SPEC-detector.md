# Stutter detector — spec (Phase 0)

Goal: a re-runnable, trusted measurement of Dota 2 stutter. One trial in -> one verdict out.
Layout (all under repo root): `detector/` (python3 stdlib + numpy/scipy/matplotlib if installed via pacman),
`bin/stutter` (single entry; subcommands below), `runs/<run-id>/` (raw logs + derived), `docs/`.
POSIX sh for shell glue (login shell is fish; never rely on it).

## Subcommands
- `stutter collect start|stop|mark <label> [--run-dir D]` — start/stop all collectors on ONE clock
  (CLOCK_REALTIME epoch seconds, float, written in every CSV; MangoHud's relative `elapsed` ns is mapped to
  epoch via a documented sync method, accuracy <= 50 ms, validated). `mark warmup_end` etc. append to events.csv.
- `stutter detect <run-dir> [--warmup 20]` — hitch events + stats (excludes everything before warm-up end).
- `stutter report <run-dir>` — markdown + PNG plots (frametime trace, hitch timeline, interval histogram,
  autocorrelation/spectrum, correlation panel) + machine-readable `verdict.json`.
- `stutter compare <runA...> -- <runB...>` — A/B with run-to-run variance, effect size, verdict.
- `stutter selftest` — idle baseline + injected-stutter validation (see Validation).
- `stutter trial --launch-opts "..." [--minutes N]` — (later, GUI-driven by agents) wrapper that sequences
  quiesce -> launch -> warm-up mark -> window -> cleanup.

## Signals (>= 10 Hz unless noted; every row has `t_epoch`)
1. Frametimes: MangoHud CSV log (`MANGOHUD_CONFIG=output_folder=..,log_duration=..,autostart_log=1,fps_only=0,...`
   incl. per-frame frametime). Verify the real column names/format on this machine's MangoHud version.
   Also verify and document Dota's own sources (console `-condebug`/console.log, `cl_showfps`, `net_graph`,
   Source 2 profiling/perf logging). Only keep what actually exists and is useful; do not assume.
2. GPU: NVML via python (preferred, low overhead) or `nvidia-smi --loop-ms`: util, SM/mem clocks, power, temp,
   VRAM, pstate, clocks_throttle_reasons (bitmask), PCIe link. Confirm which GPU the Dota process runs on
   (`nvidia-smi pmon`/`--query-compute-apps`, /proc/<pid>/maps, vulkaninfo device).
3. CPU: per-core util + freq (/proc/stat, cpufreq), /proc/pressure/{cpu,io,memory}, ctxt switches, procs_running,
   per-thread CPU of the Dota process (top thread saturation), core/CCD placement of the busiest thread
   (CCD0 = cpu 0-7,16-23 on 7945HX; verify via lscpu -e).
4. Memory/swap (/proc/meminfo, vmstat incl. dirty/writeback), disk I/O (/proc/diskstats + btrfs paths),
   network (/proc/net/dev + `ss -ti` for the spectate stream: retrans/loss; Dota `net_graph` if loggable),
   PipeWire xruns (`pw-top`/`pw-cli`/journal), KWin frame stats (qdbus/journal/`KWIN_*` debug if feasible),
   `dmesg -w`/`journalctl -f -k` (Xid, thermal, PCIe AER), temperatures (sensors/hwmon), RAPL/ppt if readable.
5. Collector overhead MUST be quantified (nvidia-smi spawns are a known hitch source): run Dota with MangoHud only
   vs MangoHud+all collectors and report the difference. Collectors run at low priority / pinned away from game cores
   when possible. If overhead is non-negligible, use a "lite" profile for final proofs and document it.

## Hitch definition (initial; final numbers set from validation + baseline variance)
Frame i with frametime f_i is a hitch iff  f_i > K * rolling_median(f, +-W frames/seconds)  AND  f_i > FLOOR.
Start with K=2.5, W=1 s centered (exclude i from median), FLOOR = max(2 * target (13.9 ms @144 Hz), 12 ms);
justify/tune on data (sensitivity table K in 2..4, FLOOR 10..25 ms). Adjacent hitch frames within 100 ms merge
into one event (event time = start, magnitude = max, duration = sum of excess). Also report a low-severity tier.
Report: hitches/min, worst hitch, 1% / 0.1% lows (fps and ms), p50/p95/p99 frametime, frame-drop-to-<fps_cap>%,
inter-hitch interval distribution (hist + quantiles).

## Periodicity
From hitch event timestamps (not just frametimes): (a) autocorrelation of the binned (e.g. 50-100 ms) hitch
series, find peaks in 0.5-60 s with a significance test (permutation / shuffled-interval null, p<0.01);
(b) Lomb-Scargle / FFT of the event series; (c) interval histogram with mode detection.
Must flag: steady rhythm < 10 s (esp. ~4 s) and sparse 30-90 s hitches. Windows < 5 min cannot assess sparse;
the tool must refuse (or loudly caveat) sparse verdicts on short windows. Report period estimate +/- error and
fraction of hitches explained by it.

## Correlation
For every hitch, extract all other signals in [-500, +500] ms (+ -2 s for slow ones), compare against the
same-length windows at random non-hitch times (z-score / enrichment). Output a ranked "what moved around hitches"
table (e.g. GPU clock dip, pstate change, busiest thread migrated CCD, PSI cpu spike, IO stall, dmesg line, xrun).

## Validation (the detector is not trusted until all pass; results in docs/VALIDATION.md)
a. Idle/desktop baseline (>=10 min, no game): ~0 false positives on the synthetic-app pipeline too.
b. Synthetic game: a Vulkan/GL app at ~144 fps under MangoHud (e.g. vkcube/glxgears/own tiny program; install via
   pacman if needed) with an injected stall: SIGSTOP burst (e.g. 40-80 ms) every 4 s, and separately every 45 s,
   and a mixed 4 s + sparse run. Detector must recover interval within +-5% and flag sparse-vs-periodic correctly;
   report precision/recall of hitch detection vs injected ground truth.
c. Unchanged Dota baseline x3 (done by trial agents later) -> run-to-run variance of hitches/min, 1%/0.1% lows.
d. "Fixed" statistical definition written to docs/FIXED-DEFINITION.md after (c): e.g. no periodic component
   (p>=0.01 at all periods <10 s), sparse rate <= upper bound derived from baseline variance (and absolute cap),
   0.1% low >= X fps, across >=3 consecutive live-spectate runs incl. one 15-20 min.

## Deliverables of Phase 0
Working `bin/stutter` with README (docs/README-detector.md: how any worker runs one trial and gets a verdict),
unit tests (pytest or plain asserts) with synthetic traces, docs/VALIDATION.md, docs/DOTA-SIGNAL-SOURCES.md.

## Run-dir data contract (so collectors and analysis can be built in parallel)
`runs/<run-id>/`:
- `meta.json` — run id, label, launch options, host/driver/kernel info, collector profile (full|lite), t_start_epoch, warmup_s.
- `events.csv` — `t_epoch,label,detail` (marks: run_start, game_launched, match_loaded, warmup_end, window_end, injected_stall...).
- `frametimes.csv` — `t_epoch,frametime_ms`, ONE ROW PER FRAME, derived from MangoHud raw by the collector (raw kept in `raw/`).
- Every other signal is `<name>.csv` with header `t_epoch,<numeric cols...>` (gpu.csv, cpu.csv, sys.csv, mem.csv, disk.csv, net.csv,
  threads.csv, ...). The analysis treats EVERY numeric column of every such CSV as a signal for correlation (generic; no hardcoding).
- Text event streams: `<name>.log` with each line prefixed `<t_epoch> <text>` (dmesg.log, journal.log, kwin.log, pipewire.log, dota-console.log).
- `raw/` — untouched raw logs (MangoHud csv etc.). Derived outputs go to `out/` (hitches.csv, stats.json, verdict.json, *.png, report.md).
