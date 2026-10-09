# Stutter report — validate-correlation-20261008-191621

- run-dir: `/path/to/repo/runs/validate-correlation-20261008-191621`
- window: 6.0 min after warm-up (warm-up source: mark), 51334 frames
- hitch rule: frametime_ms > K * rolling_median(+-W, excl. centre) AND frametime_ms > FLOOR (K=2.5, W=1.0s, FLOOR=13.9 ms, merge<=100 ms)

## Hitches
- **119 hitches** (19.87/min); worst 123.9 ms; median 57.0 ms
- isolated/sparse hitches (>15 s from any other): 0 (0.00/min)
- low-severity tier: 89 (14.86/min)

## Frametimes
- p50 6.94 ms | p95 10.84 ms | p99 12.95 ms
- 1% low **42.0 fps**, 0.1% low **13.3 fps**, mean 142.9 fps
- frames below 50% of cap: 0.46%

## Data quality
- frametime rows: 53963 kept / 53965 read; **2 rejected** (> 10000 ms / non-positive / non-finite)

## Periodicity
- verdict: **periodic** (window 6.0 min, sparse assessable: True)
- steady: period 4.10 s (spectral peak 1.39 s, source interval) +- 0.05 s, p=0.002494, significant=True, fraction explained 0.24
- sparse: period 60.12 s (spectral peak 30.06 s, source spectral) +- 17.99 s, p=0.3267, significant=False, fraction explained 0.32
- sparse_residual: period 36.07 s (spectral peak 36.07 s, source spectral) +- 24.76 s, p=0.394, significant=False, fraction explained 0.30

## Sparse hitches (explicit assessment)
- assessment: **irregular** (79 severe candidate(s) of 119 primary; severity gate 20.8 ms, steady phase 4.10 s removed)
- rate: 13.14/min (95% CI 10.32-16.14, poisson-bootstrap)
- intervals (s): p50 4.1, p90 4.3, CV 1.46
- interval mode 55.5 s; modal cluster n=1 cv=0.000 frac=1.00
- CAVEAT: only 1 interval(s) in the [20, 100] s band (<5): regularity cannot be established

## What moved around hitches
| signal.column | feature | cliff's d | z | p | q | hitch | control |
|---|---|---|---|---|---|---|---|
| hwmon.k10temp_temp1_c | step | +0.74 | 6.32 | 1.07e-42 | 5.4e-40 | 1.12 | -0.243 |
| cpu.cpu_util_avg | mean | +0.63 | 0.93 | 5.8e-31 | 1.5e-28 | 5.36 | 3.98 |
| cpu.cpu_util_avg | max | +0.53 | 0.82 | 6.06e-23 | 3.4e-21 | 13.4 | 8.43 |
| cpu.cpu2_util | max | +0.49 | 1.32 | 9.22e-21 | 4.6e-19 | 57.3 | 40.6 |
| sys.procs_running | mean | +0.47 | 0.69 | 6.77e-18 | 2.6e-16 | 3 | 2.55 |
| cpu.cpu0_util | max | +0.46 | 1.58 | 5.36e-18 | 2.2e-16 | 60.9 | 42.8 |
| sys.forks_per_s | mean | +0.45 | 0.24 | 5.87e-17 | 2e-15 | 27.7 | 20 |
| cpu.cpu3_util | max | +0.44 | 1.19 | 2.58e-16 | 5.6e-15 | 58.8 | 39.6 |
| hwmon.k10temp_temp1_c | max | +0.43 | 0.68 | 1.82e-15 | 3.6e-14 | 84.1 | 83 |
| cpu.cpu4_util | mean | +0.43 | 1.39 | 2.53e-15 | 4.9e-14 | 5.41 | 3.24 |
| cpu.cpu1_util | max | +0.43 | 1.47 | 6.5e-16 | 1.4e-14 | 60.4 | 41.1 |
| hwmon.k10temp_temp3_c | mean | +0.41 | 1.01 | 2.88e-14 | 5.3e-13 | 77.7 | 75.7 |
| hwmon.k10temp_temp3_c | max | +0.40 | 1.30 | 1.1e-13 | 2e-12 | 84.6 | 79.6 |
| cpu.cpu15_util | max | +0.39 | 1.17 | 2.24e-13 | 3.9e-12 | 47.5 | 29.4 |
| cpu.cpu2_util | mean | +0.39 | 0.85 | 1.14e-12 | 1.7e-11 | 17.1 | 13 |

| log | near hitch | near control | template |
|---|---|---|---|
| journal | 10 | 28 | `HOSTNAME llm-server[#]: <log line>` |
| journal | 7 | 0 | `HOSTNAME llm-server[#]: <log line>` |
| journal | 7 | 0 | `HOSTNAME llm-server[#]: <log line>` |
| journal | 7 | 0 | `HOSTNAME llm-server[#]: <log line>` |
| journal | 7 | 0 | `HOSTNAME llm-server[#]: <log line>` |
| journal | 7 | 0 | `HOSTNAME llm-server[#]: <log line>` |
| journal | 7 | 0 | `HOSTNAME llm-server[#]: <log line>` |
| journal | 7 | 0 | `HOSTNAME llm-server[#]: <log line>` |

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

