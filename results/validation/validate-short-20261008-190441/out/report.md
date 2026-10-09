# Stutter report — validate-short-20261008-190441

- run-dir: `/path/to/repo/runs/validate-short-20261008-190441`
- window: 2.0 min after warm-up (warm-up source: mark), 17004 frames
- hitch rule: frametime_ms > K * rolling_median(+-W, excl. centre) AND frametime_ms > FLOOR (K=2.5, W=1.0s, FLOOR=13.9 ms, merge<=100 ms)

## Hitches
- **32 hitches** (16.14/min); worst 82.4 ms; median 56.6 ms
- isolated/sparse hitches (>15 s from any other): 0 (0.00/min)
- low-severity tier: 17 (8.58/min)

## Frametimes
- p50 6.94 ms | p95 8.70 ms | p99 12.76 ms
- 1% low **47.2 fps**, 0.1% low **15.0 fps**, mean 143.0 fps
- frames below 50% of cap: 0.30%

## Data quality
- frametime rows: 19706 kept / 19706 read; **0 rejected** (> 10000 ms / non-positive / non-finite)

## Periodicity
- verdict: **periodic** (window 2.0 min, sparse assessable: False)
- steady: period 4.15 s (spectral peak 0.51 s, source interval) +- 0.46 s, p=0.002494, significant=True, fraction explained 0.34
- sparse: period 30.10 s (spectral peak 30.10 s, source spectral) +- 9.71 s, p=0.9726, significant=False, fraction explained 0.16
- sparse_residual: period 60.20 s (spectral peak 30.10 s, source spectral) +- 12.34 s, p=0.9252, significant=False, fraction explained 0.24
- WARNING: post-warm-up window 2.0 min < 5 min: sparse (30-90 s) periodicity cannot be assessed

## Sparse hitches (explicit assessment)
- assessment: **none** (1 severe candidate(s) of 32 primary; severity gate 20.8 ms, steady phase 4.15 s removed)
- rate: 0.50/min (95% CI 0.00-1.50, poisson-bootstrap)
- CAVEAT: post-warm-up window 2.0 min < 5 min: sparse assessment unreliable
- CAVEAT: only 1 sparse candidate(s) (<8): rate/period estimate is uncertain

## What moved around hitches
| signal.column | feature | cliff's d | z | p | q | hitch | control |
|---|---|---|---|---|---|---|---|
| hwmon.k10temp_temp1_c | step | +0.63 | 1.89 | 1.19e-09 | 2.6e-07 | 0.332 | -0.0508 |
| cpufreq.cpu5_mhz | max | -0.44 | -0.43 | 2.58e-05 | 0.0023 | 4.61e+03 | 4.94e+03 |
| cpufreq.cpu22_mhz | mean | +0.36 | 0.66 | 0.000572 | 0.042 | 3.85e+03 | 3.39e+03 |
| cpu.cpu3_util | step | +0.35 | 0.56 | 0.000959 | 0.055 | 4.66 | 0.427 |
| hwmon.k10temp_temp4_c | max | +0.34 | 0.68 | 0.000994 | 0.055 | 74.5 | 72.6 |
| cpu.cpu_util_avg | step | +0.30 | 0.41 | 0.00375 | 0.16 | 0.33 | -0.126 |
| cpu.cpu22_util | step | +0.30 | 0.46 | 0.0046 | 0.16 | 1.14 | -0.254 |
| cpufreq.cpu19_mhz | step | +0.30 | 0.57 | 0.00473 | 0.16 | 443 | -25.8 |
| cpu.cpu_util_avg | mean | +0.29 | 0.53 | 0.00511 | 0.16 | 4.15 | 3.84 |
| hwmon.k10temp_temp4_c | mean | +0.29 | 0.59 | 0.00567 | 0.16 | 71.4 | 70.6 |
| cpu.cpu3_util | max | +0.28 | 0.65 | 0.00489 | 0.16 | 57.9 | 50.7 |
| cpufreq.cpu2_mhz | mean | +0.28 | 0.45 | 0.00744 | 0.18 | 4.4e+03 | 4.15e+03 |
| cpu.cpu7_util | step | +0.28 | 0.50 | 0.0056 | 0.16 | 0.563 | -0.239 |
| cpufreq.cpu10_mhz | mean | +0.27 | 0.46 | 0.0091 | 0.21 | 2.66e+03 | 2.42e+03 |
| sys.forks_per_s | mean | +0.26 | 0.20 | 0.0115 | 0.25 | 40.4 | 29.9 |

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

