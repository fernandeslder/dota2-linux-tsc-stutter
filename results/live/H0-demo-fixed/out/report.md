# Stutter report — live-H0-demo-fixed

- run-dir: `/path/to/repo/runs/live-H0-demo-fixed`
- window: 6.0 min after warm-up (warm-up source: mark), 51231 frames
- hitch rule: frametime_ms > K * rolling_median(+-W, excl. centre) AND frametime_ms > FLOOR (K=2.5, W=1.0s, FLOOR=13.9 ms, merge<=100 ms)

## Hitches
- **0 hitches** (0.00/min); worst nan ms; median nan ms
- isolated/sparse hitches (>15 s from any other): 0 (0.00/min)
- low-severity tier: 2 (0.33/min)

## Frametimes
- p50 7.03 ms | p95 9.66 ms | p99 10.58 ms
- 1% low **89.3 fps**, 0.1% low **80.3 fps**, mean 142.3 fps
- frames below 50% of cap: 0.00%

## Data quality
- frametime rows: 61655 kept / 61655 read; **0 rejected** (> 10000 ms / non-positive / non-finite)

## Periodicity
- verdict: **insufficient** (window 6.0 min, sparse assessable: True)
- WARNING: only 0 hitch event(s): periodic verdict unreliable

## Sparse hitches (explicit assessment)
- assessment: **none** (0 severe candidate(s) of 0 primary; severity gate 20.8 ms)
- CAVEAT: no severe isolated hitches in the window

## What moved around hitches
_no signal had enough samples around hitches_

| log | near hitch | near control | template |
|---|---|---|---|
| dmesg | 0 | 1 | `HOSTNAME kernel: __report_access: # callbacks suppressed` |
| dmesg | 0 | 10 | `HOSTNAME kernel: ptrace attach notice (process names omitted)` |

## What the threads were blocked on during hitches

- window per hitch: [hitch_start - pre_ms, hitch_end] (pre_ms=50); threads seen: 92
- hitches analysed: 0/0 (a bucket counts when it covers >= 5% of the window)

_no thread/bucket passed the coverage threshold around hitches_

### Per-thread-name CPU (threads_cpu.csv)

| thread | cpu% (mean) | samples | threads |
|---|---|---|---|
| mangohud-nvidia | 2120967.17 | 461 | 1 |
| CHTTPCacheFileT | 2097152.00 | 1 | 1 |
| AsyncIOService/ | 1819676.12 | 55 | 3 |
| AsyncTextureHoo | 1138290.84 | 10 | 1 |
| CJobMgr::m_Work | 1048626.00 | 2 | 1 |
| dota2 | 1010846.57 | 927 | 6 |
| CHTTPCacheIniti | 953501.00 | 2 | 1 |
| VKRenderThread | 549073.72 | 1094 | 8 |
| IPC:CSteamEngin | 323399.86 | 57 | 2 |
| mangohud-hwinfo | 322521.63 | 44 | 1 |
| GlobPool/6 | 314651.37 | 316 | 1 |
| GlobPool/0 | 288763.39 | 305 | 1 |
| PulseHotplug | 286217.09 | 36 | 1 |
| PulseMainloop | 278753.88 | 112 | 1 |
| GlobPool/1 | 270842.46 | 311 | 1 |
- note: no hitches in the analysis window


## Artifacts
- `hitches.csv`
- `stats.json`
- `correlation_signals.csv`
- `correlation_logs.csv`
- `blocked_on.csv`
- `frametime_trace.png`
- `hitch_timeline.png`
- `interval_histogram.png`
- `spectrum_autocorr.png`
- `correlation_panel.png`

