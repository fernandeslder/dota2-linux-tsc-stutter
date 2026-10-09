# Stutter report — live-S1-sched

- run-dir: `/path/to/repo/runs/live-S1-sched`
- window: 2.0 min after warm-up (warm-up source: mark), 15554 frames
- hitch rule: frametime_ms > K * rolling_median(+-W, excl. centre) AND frametime_ms > FLOOR (K=2.5, W=1.0s, FLOOR=13.9 ms, merge<=100 ms)

## Hitches
- **19 hitches** (9.49/min); worst 2581.8 ms; median 257.0 ms
- isolated/sparse hitches (>15 s from any other): 1 (0.50/min)
- low-severity tier: 2 (1.00/min)

## Frametimes
- p50 7.07 ms | p95 9.55 ms | p99 10.48 ms
- 1% low **12.6 fps**, 0.1% low **1.5 fps**, mean 129.5 fps
- frames below 50% of cap: 0.14%

## Data quality
- frametime rows: 26143 kept / 26143 read; **0 rejected** (> 10000 ms / non-positive / non-finite)

## Periodicity
- verdict: **aperiodic** (window 2.0 min, sparse assessable: False)
- steady: period 3.48 s (spectral peak 0.52 s, source interval) +- 1.60 s, p=0.3466, significant=False, fraction explained 0.32
- sparse: period 60.10 s (spectral peak 60.10 s, source spectral) +- 16.09 s, p=0.3791, significant=False, fraction explained 0.21
- WARNING: post-warm-up window 2.0 min < 5 min: sparse (30-90 s) periodicity cannot be assessed

## Sparse hitches (explicit assessment)
- assessment: **none** (16 severe candidate(s) of 19 primary; severity gate 20.8 ms)
- rate: 7.99/min (95% CI 4.50-11.99, poisson-bootstrap)
- intervals (s): p50 5.6, p90 12.9, CV 0.72
- CAVEAT: post-warm-up window 2.0 min < 5 min: sparse assessment unreliable

## What moved around hitches
_no signal had enough samples around hitches_

## What the threads were blocked on during hitches

_not available: threads_blocked.csv not present (this run predates the offcpu sampler)_


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

