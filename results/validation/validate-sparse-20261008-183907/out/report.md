# Stutter report — validate-sparse-20261008-183907

- run-dir: `/path/to/repo/runs/validate-sparse-20261008-183907`
- window: 9.8 min after warm-up (warm-up source: mark), 84361 frames
- hitch rule: frametime_ms > K * rolling_median(+-W, excl. centre) AND frametime_ms > FLOOR (K=2.5, W=1.0s, FLOOR=13.9 ms, merge<=100 ms)

## Hitches
- **36 hitches** (3.68/min); worst 82.7 ms; median 20.2 ms
- isolated/sparse hitches (>15 s from any other): 9 (0.92/min)
- low-severity tier: 167 (17.09/min)

## Frametimes
- p50 6.94 ms | p95 12.67 ms | p99 12.96 ms
- 1% low **68.9 fps**, 0.1% low **41.5 fps**, mean 143.9 fps
- frames below 50% of cap: 0.25%

## Data quality
- frametime rows: 87055 kept / 87056 read; **1 rejected** (> 10000 ms / non-positive / non-finite)

## Periodicity
- verdict: **aperiodic** (window 9.8 min, sparse assessable: True)
- steady: period 5.18 s (spectral peak 0.82 s, source interval) +- 1.49 s, p=0.04239, significant=False, fraction explained 0.22
- sparse: period 45.22 s (spectral peak 45.22 s, source interval) +- 5.04 s, p=0.217, significant=False, fraction explained 0.47

## Sparse hitches (explicit assessment)
- assessment: **regular(45.1s)** (17 severe candidate(s) of 36 primary; severity gate 20.8 ms)
- rate: 1.74/min (95% CI 0.92-2.55, poisson-bootstrap)
- intervals (s): p50 45.1, p90 45.1, CV 0.47
- interval mode 46.5 s; modal cluster n=11 cv=0.058 frac=1.00

## What moved around hitches
| signal.column | feature | cliff's d | z | p | q | hitch | control |
|---|---|---|---|---|---|---|---|
| hwmon.k10temp_temp1_c | step | +0.45 | 0.42 | 4.09e-06 | 0.0019 | 0.168 | -0.00347 |
| cpufreq.cpu23_mhz | max | +0.25 | 0.30 | 0.00977 | 0.45 | 4.3e+03 | 3.88e+03 |
| cpu.cpu24_util | mean | +0.25 | 0.48 | 0.0109 | 0.46 | 2.11 | 1.52 |
| cpufreq.cpu24_mhz | mean | +0.24 | 0.44 | 0.0161 | 0.53 | 2.79e+03 | 2.54e+03 |
| cpufreq.cpu21_mhz | step | -0.24 | -0.41 | 0.0159 | 0.53 | -259 | 89.5 |
| cpufreq.cpu5_mhz | mean | +0.23 | 0.39 | 0.0175 | 0.54 | 2.67e+03 | 2.41e+03 |
| sys.load5 | min | +0.23 | 0.37 | 0.019 | 0.54 | 1.68 | 1.53 |
| cpufreq.cpu12_mhz | mean | +0.23 | 0.42 | 0.0212 | 0.54 | 3.17e+03 | 2.9e+03 |
| cpufreq.cpu18_mhz | step | -0.23 | -0.28 | 0.0226 | 0.54 | -255 | 40 |
| sys.load5 | mean | +0.22 | 0.36 | 0.0235 | 0.54 | 1.69 | 1.54 |
| cpufreq.cpu14_mhz | mean | +0.22 | 0.36 | 0.0249 | 0.54 | 3.69e+03 | 3.47e+03 |
| sys.load15 | min | +0.22 | 0.34 | 0.0258 | 0.54 | 1.47 | 1.42 |
| sys.load5 | max | +0.22 | 0.36 | 0.0261 | 0.54 | 1.69 | 1.54 |
| sys.load15 | mean | +0.22 | 0.33 | 0.0277 | 0.54 | 1.47 | 1.42 |
| sys.load1 | min | +0.22 | 0.35 | 0.0289 | 0.54 | 2 | 1.71 |

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

