# Stutter report — live-M1-min

- run-dir: `/path/to/repo/runs/live-M1-min`
- window: 6.0 min after warm-up (warm-up source: mark), 48939 frames
- hitch rule: frametime_ms > K * rolling_median(+-W, excl. centre) AND frametime_ms > FLOOR (K=2.5, W=1.0s, FLOOR=13.9 ms, merge<=100 ms)

## Hitches
- **64 hitches** (10.65/min); worst 2025.8 ms; median 146.7 ms
- isolated/sparse hitches (>15 s from any other): 0 (0.00/min)
- low-severity tier: 6 (1.00/min)

## Frametimes
- p50 7.06 ms | p95 9.57 ms | p99 10.56 ms
- 1% low **22.6 fps**, 0.1% low **3.0 fps**, mean 135.8 fps
- frames below 50% of cap: 0.15%

## Data quality
- frametime rows: 59326 kept / 59326 read; **0 rejected** (> 10000 ms / non-positive / non-finite)

## Periodicity
- verdict: **aperiodic** (window 6.0 min, sparse assessable: True)
- steady: period 2.42 s (spectral peak 0.50 s, source interval) +- 0.72 s, p=0.09975, significant=False, fraction explained 0.23
- sparse: period 30.05 s (spectral peak 30.05 s, source spectral) +- 22.42 s, p=0.07731, significant=False, fraction explained 0.27

## Sparse hitches (explicit assessment)
- assessment: **none** (63 severe candidate(s) of 64 primary; severity gate 20.8 ms)
- rate: 10.48/min (95% CI 7.99-13.15, poisson-bootstrap)
- intervals (s): p50 3.0, p90 14.2, CV 1.11

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

