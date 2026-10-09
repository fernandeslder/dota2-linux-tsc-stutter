# Stutter report — live-T1-no-cpu0

- run-dir: `/path/to/repo/runs/live-T1-no-cpu0`
- window: 6.0 min after warm-up (warm-up source: mark), 51234 frames
- hitch rule: frametime_ms > K * rolling_median(+-W, excl. centre) AND frametime_ms > FLOOR (K=2.5, W=1.0s, FLOOR=13.9 ms, merge<=100 ms)

## Hitches
- **0 hitches** (0.00/min); worst nan ms; median nan ms
- isolated/sparse hitches (>15 s from any other): 0 (0.00/min)
- low-severity tier: 4 (0.67/min)

## Frametimes
- p50 7.07 ms | p95 9.64 ms | p99 10.57 ms
- 1% low **89.3 fps**, 0.1% low **79.0 fps**, mean 142.2 fps
- frames below 50% of cap: 0.01%

## Data quality
- frametime rows: 61467 kept / 61467 read; **0 rejected** (> 10000 ms / non-positive / non-finite)

## Periodicity
- verdict: **insufficient** (window 6.0 min, sparse assessable: True)
- WARNING: only 0 hitch event(s): periodic verdict unreliable

## Sparse hitches (explicit assessment)
- assessment: **none** (0 severe candidate(s) of 0 primary; severity gate 20.8 ms)
- CAVEAT: no severe isolated hitches in the window

## What moved around hitches
_no signal had enough samples around hitches_

## What the threads were blocked on during hitches

- window per hitch: [hitch_start - pre_ms, hitch_end] (pre_ms=50); threads seen: 92
- hitches analysed: 0/0 (a bucket counts when it covers >= 5% of the window)

_no thread/bucket passed the coverage threshold around hitches_

### Per-thread-name CPU (threads_cpu.csv)

| thread | cpu% (mean) | samples | threads |
|---|---|---|---|
| AsyncIOService/ | 2688194.53 | 61 | 3 |
| AsyncTextureHoo | 1653380.15 | 9 | 1 |
| mangohud-nvidia | 1652882.83 | 458 | 1 |
| dota2 | 837402.15 | 963 | 7 |
| VKRenderThread | 439399.99 | 1086 | 8 |
| [vkps] Update | 351211.27 | 57 | 1 |
| mangohud-hwinfo | 295358.21 | 44 | 1 |
| IPC:CSteamEngin | 288252.84 | 58 | 2 |
| SDLAudioP15 | 287818.94 | 47 | 1 |
| GlobPool/3 | 271706.25 | 325 | 1 |
| GlobPool/6 | 271500.52 | 315 | 1 |
| GlobPool/0 | 268530.76 | 320 | 1 |
| GlobPool/2 | 258886.79 | 305 | 1 |
| GlobPool/5 | 249978.42 | 319 | 1 |
| GlobPool/1 | 247459.55 | 314 | 1 |
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

