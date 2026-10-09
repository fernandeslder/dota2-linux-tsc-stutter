# Stutter report — live-smoke

- run-dir: `/path/to/repo/runs/live-smoke`
- window: 0.0 min after warm-up (warm-up source: mark), 0 frames
- hitch rule: frametime_ms > K * rolling_median(+-W, excl. centre) AND frametime_ms > FLOOR (K=2.5, W=1.0s, FLOOR=13.9 ms, merge<=100 ms)

## Hitches
- **0 hitches** (nan/min); worst nan ms; median nan ms
- isolated/sparse hitches (>15 s from any other): 0 (nan/min)
- low-severity tier: 0 (nan/min)

## Frametimes
- p50 nan ms | p95 nan ms | p99 nan ms
- 1% low **nan fps**, 0.1% low **nan fps**, mean nan fps
- frames below 50% of cap: nan%

## Periodicity
- verdict: **insufficient** (window 0.2 min, sparse assessable: False)
- WARNING: post-warm-up window 0.2 min < 5 min: sparse (30-90 s) periodicity cannot be assessed
- WARNING: only 0 hitch event(s): periodic verdict unreliable

## What moved around hitches
_no signal had enough samples around hitches_

## Artifacts
- `hitches.csv`
- `stats.json`
- `correlation_signals.csv`
- `correlation_logs.csv`
- `frametime_trace.png`
- `hitch_timeline.png`
- `interval_histogram.png`
- `spectrum_autocorr.png`
- `correlation_panel.png`

