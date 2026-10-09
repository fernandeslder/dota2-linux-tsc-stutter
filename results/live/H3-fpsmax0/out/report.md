# Stutter report — live-H3-fpsmax0

- run-dir: `/path/to/repo/runs/live-H3-fpsmax0`
- window: 6.0 min after warm-up (warm-up source: mark), 110324 frames
- hitch rule: frametime_ms > K * rolling_median(+-W, excl. centre) AND frametime_ms > FLOOR (K=2.5, W=1.0s, FLOOR=13.9 ms, merge<=100 ms)

## Hitches
- **0 hitches** (0.00/min); worst nan ms; median nan ms
- isolated/sparse hitches (>15 s from any other): 0 (0.00/min)
- low-severity tier: 3 (0.50/min)

## Frametimes
- p50 3.02 ms | p95 5.31 ms | p99 6.09 ms
- 1% low **150.3 fps**, 0.1% low **123.6 fps**, mean 306.1 fps
- frames below 50% of cap: 0.00%

## Data quality
- frametime rows: 131101 kept / 131101 read; **0 rejected** (> 10000 ms / non-positive / non-finite)

## Periodicity
- verdict: **insufficient** (window 6.0 min, sparse assessable: True)
- WARNING: only 0 hitch event(s): periodic verdict unreliable

## Sparse hitches (explicit assessment)
- assessment: **none** (0 severe candidate(s) of 0 primary; severity gate 20.8 ms)
- CAVEAT: no severe isolated hitches in the window

## What moved around hitches
_no signal had enough samples around hitches_

## What the threads were blocked on during hitches

- window per hitch: [hitch_start - pre_ms, hitch_end] (pre_ms=50); threads seen: 93
- hitches analysed: 0/0 (a bucket counts when it covers >= 5% of the window)

_no thread/bucket passed the coverage threshold around hitches_

### Per-thread-name CPU (threads_cpu.csv)

| thread | cpu% (mean) | samples | threads |
|---|---|---|---|
| CNet Encrypt:0 | 1398101.33 | 1 | 1 |
| mangohud-nvidia | 1053477.86 | 460 | 1 |
| dota2 | 673038.94 | 969 | 7 |
| CJobMgr::m_Work | 474644.49 | 3 | 2 |
| AsyncIOService/ | 473926.25 | 54 | 3 |
| VKRenderThread | 348521.68 | 1674 | 8 |
| GlobPool/5 | 228730.55 | 431 | 1 |
| GlobPool/3 | 219468.32 | 433 | 1 |
| GlobPool/1 | 213264.58 | 429 | 1 |
| GlobPool/6 | 212574.51 | 432 | 1 |
| GlobPool/4 | 208306.34 | 431 | 1 |
| SDLAudioP15 | 208069.84 | 52 | 1 |
| GlobPool/0 | 206706.14 | 430 | 1 |
| GlobPool/2 | 203313.42 | 432 | 1 |
| AudioMixer | 161010.45 | 117 | 1 |
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

