# Stutter report — validate-clean-20261008-181807

- run-dir: `/path/to/repo/runs/validate-clean-20261008-181807`
- window: 10.0 min after warm-up (warm-up source: mark), 86290 frames
- hitch rule: frametime_ms > K * rolling_median(+-W, excl. centre) AND frametime_ms > FLOOR (K=2.5, W=1.0s, FLOOR=13.9 ms, merge<=100 ms)

## Hitches
- **28 hitches** (2.80/min); worst 102.1 ms; median 18.9 ms
- isolated/sparse hitches (>15 s from any other): 7 (0.70/min)
- low-severity tier: 259 (25.90/min)

## Frametimes
- p50 6.94 ms | p95 12.64 ms | p99 12.96 ms
- 1% low **67.5 fps**, 0.1% low **39.3 fps**, mean 143.8 fps
- frames below 50% of cap: 0.35%

## Data quality
- frametime rows: 88982 kept / 88982 read; **0 rejected** (> 10000 ms / non-positive / non-finite)

## Periodicity
- verdict: **aperiodic** (window 10.0 min, sparse assessable: True)
- steady: period 3.00 s (spectral peak 5.84 s, source interval) +- 1.49 s, p=0.9277, significant=False, fraction explained 0.29
- sparse: period 42.57 s (spectral peak 54.67 s, source interval) +- 9.43 s, p=0.02494, significant=False, fraction explained 0.32

## Sparse hitches (explicit assessment)
- assessment: **irregular** (8 severe candidate(s) of 28 primary; severity gate 20.8 ms)
- rate: 0.80/min (95% CI 0.30-1.40, poisson-bootstrap)
- intervals (s): p50 58.0, p90 108.4, CV 0.95
- interval mode 58.5 s; modal cluster n=2 cv=0.030 frac=1.00
- CAVEAT: only 2 interval(s) in the [20, 100] s band (<5): regularity cannot be established

## What moved around hitches
| signal.column | feature | cliff's d | z | p | q | hitch | control |
|---|---|---|---|---|---|---|---|
| gpu.power_w | max | +0.58 | 3.07 | 2.64e-07 | 5.9e-06 | 13 | 7.66 |
| gpu.power_w | mean | +0.57 | 1.78 | 3.99e-07 | 8.6e-06 | 9.79 | 7.49 |
| gpu.sm_clock_mhz | max | +0.55 | 3.72 | 2.62e-09 | 8.9e-08 | 651 | 235 |
| gpu.graphics_clock_mhz | max | +0.55 | 3.72 | 2.62e-09 | 8.9e-08 | 651 | 235 |
| gpu.sm_clock_mhz | mean | +0.54 | 3.32 | 5.87e-09 | 1.7e-07 | 401 | 225 |
| gpu.graphics_clock_mhz | mean | +0.54 | 3.32 | 5.87e-09 | 1.7e-07 | 401 | 225 |
| gpu.mem_clock_mhz | max | +0.49 | 3.63 | 1.95e-22 | 3.1e-20 | 1.79e+03 | 440 |
| gpu.pcie_gen | max | +0.49 | 3.10 | 1.95e-22 | 3.1e-20 | 1.82 | 1.05 |
| gpu.pstate | min | -0.49 | -2.99 | 1.95e-22 | 3.1e-20 | 5.68 | 7.84 |
| gpu.mem_clock_mhz | mean | +0.49 | 5.90 | 4.26e-22 | 5e-20 | 923 | 418 |
| gpu.pcie_gen | mean | +0.48 | 2.06 | 8.69e-22 | 7e-20 | 1.33 | 1.03 |
| gpu.pstate | mean | -0.48 | -1.95 | 8.9e-22 | 7e-20 | 7.06 | 7.92 |
| gpu.power_limit_w | max | +0.48 | 2.16 | 1.07e-21 | 7.3e-20 | 168 | 161 |
| gpu.power_limit_w | mean | +0.48 | 1.34 | 2.25e-21 | 1.3e-19 | 163 | 160 |
| cpufreq.cpu10_mhz | mean | +0.44 | 0.79 | 8.5e-05 | 0.0017 | 3.33e+03 | 2.78e+03 |

| log | near hitch | near control | template |
|---|---|---|---|
| journal | 1 | 0 | `HOSTNAME llm-server[#]: <log line>` |
| journal | 1 | 0 | `HOSTNAME llm-server[#]: <log line>` |
| journal | 0 | 2 | `HOSTNAME systemd[#]: Finished Stop the on-demand background stac` |
| journal | 0 | 2 | `HOSTNAME systemd[#]: idle-reaper.service: Deactivated ` |
| journal | 0 | 2 | `HOSTNAME systemd[#]: Starting Stop the on-demand background stac` |

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

