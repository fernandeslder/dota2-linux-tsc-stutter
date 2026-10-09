# Stutter report — live-H2-threads-16

- run-dir: `/path/to/repo/runs/live-H2-threads-16`
- window: 6.1 min after warm-up (warm-up source: mark), 52289 frames
- hitch rule: frametime_ms > K * rolling_median(+-W, excl. centre) AND frametime_ms > FLOOR (K=2.5, W=1.0s, FLOOR=13.9 ms, merge<=100 ms)

## Hitches
- **0 hitches** (0.00/min); worst nan ms; median nan ms
- isolated/sparse hitches (>15 s from any other): 0 (0.00/min)
- low-severity tier: 1 (0.16/min)

## Frametimes
- p50 7.03 ms | p95 9.70 ms | p99 10.74 ms
- 1% low **88.2 fps**, 0.1% low **79.3 fps**, mean 142.2 fps
- frames below 50% of cap: 0.00%

## Data quality
- frametime rows: 61693 kept / 61693 read; **0 rejected** (> 10000 ms / non-positive / non-finite)

## Periodicity
- verdict: **insufficient** (window 6.0 min, sparse assessable: True)
- WARNING: only 0 hitch event(s): periodic verdict unreliable

## Sparse hitches (explicit assessment)
- assessment: **none** (0 severe candidate(s) of 0 primary; severity gate 20.8 ms)
- CAVEAT: no severe isolated hitches in the window

## What moved around hitches
_no signal had enough samples around hitches_

## What the threads were blocked on during hitches

- window per hitch: [hitch_start - pre_ms, hitch_end] (pre_ms=50); threads seen: 99
- hitches analysed: 0/0 (a bucket counts when it covers >= 5% of the window)

_no thread/bucket passed the coverage threshold around hitches_

### Per-thread-name CPU (threads_cpu.csv)

| thread | cpu% (mean) | samples | threads |
|---|---|---|---|
| mangohud-nvidia | 1260447.91 | 460 | 1 |
| dota2 | 625048.69 | 934 | 6 |
| AsyncIOService/ | 505336.20 | 54 | 3 |
| VKRenderThread | 320782.33 | 1173 | 8 |
| AsyncTextureHoo | 259367.74 | 9 | 1 |
| CJobMgr::m_Work | 246005.57 | 3 | 2 |
| GlobPool/5 | 186362.67 | 273 | 1 |
| AudioMixer | 185195.36 | 80 | 1 |
| GlobPool/8 | 180037.63 | 280 | 1 |
| GlobPool/7 | 177577.79 | 282 | 1 |
| GlobPool/0 | 176552.37 | 279 | 1 |
| GlobPool/2 | 174053.47 | 284 | 1 |
| GlobPool/9 | 173313.08 | 281 | 1 |
| GlobPool/11 | 169614.83 | 270 | 1 |
| GlobPool/1 | 168054.30 | 286 | 1 |
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

