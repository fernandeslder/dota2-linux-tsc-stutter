# Stutter report — validate-periodic-20261008-183029

- run-dir: `/path/to/repo/runs/validate-periodic-20261008-183029`
- window: 6.0 min after warm-up (warm-up source: mark), 51544 frames
- hitch rule: frametime_ms > K * rolling_median(+-W, excl. centre) AND frametime_ms > FLOOR (K=2.5, W=1.0s, FLOOR=13.9 ms, merge<=100 ms)

## Hitches
- **96 hitches** (15.96/min); worst 86.0 ms; median 61.2 ms
- isolated/sparse hitches (>15 s from any other): 0 (0.00/min)
- low-severity tier: 86 (14.30/min)

## Frametimes
- p50 6.94 ms | p95 11.91 ms | p99 12.93 ms
- 1% low **45.7 fps**, 0.1% low **14.2 fps**, mean 142.8 fps
- frames below 50% of cap: 0.36%

## Data quality
- frametime rows: 54236 kept / 54236 read; **0 rejected** (> 10000 ms / non-positive / non-finite)

## Periodicity
- verdict: **periodic** (window 6.0 min, sparse assessable: True)
- steady: period 4.12 s (spectral peak 1.37 s, source interval) +- 0.02 s, p=0.002494, significant=True, fraction explained 0.59
- sparse: period 72.46 s (spectral peak 36.23 s, source spectral) +- 20.69 s, p=1, significant=False, fraction explained 0.18
- sparse_residual: period 51.76 s (spectral peak 36.23 s, source interval) +- 17.22 s, p=0.995, significant=False, fraction explained 0.26

## Sparse hitches (explicit assessment)
- assessment: **irregular** (2 severe candidate(s) of 96 primary; severity gate 20.8 ms, steady phase 4.12 s removed)
- rate: 0.33/min (95% CI 0.00-0.83, poisson-bootstrap)
- intervals (s): p50 87.9, p90 87.9, CV 0.00
- interval mode 88.5 s; modal cluster n=1 cv=0.000 frac=1.00
- CAVEAT: only 2 sparse candidate(s) (<8): rate/period estimate is uncertain
- CAVEAT: only 1 interval(s) in the [20, 100] s band (<5): regularity cannot be established

## What moved around hitches
| signal.column | feature | cliff's d | z | p | q | hitch | control |
|---|---|---|---|---|---|---|---|
| hwmon.k10temp_temp1_c | step | +0.62 | 0.68 | 5.16e-25 | 2.3e-22 | 0.221 | -0.0352 |
| sys.forks_per_s | mean | +0.37 | 0.22 | 5.63e-10 | 8.5e-08 | 20.7 | 16 |
| cpu.cpu_util_avg | step | +0.32 | 0.40 | 1.34e-07 | 1.5e-05 | 0.349 | -0.0733 |
| sys.intr_per_s | min | -0.30 | -0.80 | 8.03e-07 | 7.2e-05 | 8.37e+03 | 8.86e+03 |
| cpu.cpu_util_avg | mean | +0.24 | 0.20 | 5.39e-05 | 0.0041 | 3.68 | 3.56 |
| cpu.cpu_util_avg | max | +0.23 | 0.15 | 0.000139 | 0.009 | 8.04 | 7.52 |
| gpu.gpu_util | step | -0.23 | -0.40 | 0.000167 | 0.0094 | -2.3 | 0.0587 |
| gpu.power_w | step | -0.21 | 0.01 | 0.000609 | 0.027 | -0.0349 | -0.0446 |
| sys.forks_per_s | step | +0.20 | 0.16 | 0.000949 | 0.036 | 4.54 | -2.87 |
| cpu.cpu18_util | step | +0.19 | 0.30 | 0.00135 | 0.044 | 0.751 | -0.0473 |
| sys.intr_per_s | step | +0.19 | 0.26 | 0.00162 | 0.049 | 876 | -167 |
| cpufreq.cpu6_mhz | step | +0.18 | 0.36 | 0.00228 | 0.061 | 259 | -99.8 |
| cpu.cpu23_util | mean | +0.18 | 0.31 | 0.00116 | 0.04 | 0.925 | 0.653 |
| cpu.cpu3_util | step | +0.18 | 0.32 | 0.00275 | 0.069 | 2.21 | -0.239 |
| gpu.mem_util | step | -0.18 | -0.28 | 0.00361 | 0.086 | -1.14 | 0.192 |

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

