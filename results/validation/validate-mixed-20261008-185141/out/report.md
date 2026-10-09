# Stutter report — validate-mixed-20261008-185141

- run-dir: `/path/to/repo/runs/validate-mixed-20261008-185141`
- window: 10.0 min after warm-up (warm-up source: mark), 85561 frames
- hitch rule: frametime_ms > K * rolling_median(+-W, excl. centre) AND frametime_ms > FLOOR (K=2.5, W=1.0s, FLOOR=13.9 ms, merge<=100 ms)

## Hitches
- **172 hitches** (17.18/min); worst 453.1 ms; median 62.5 ms
- isolated/sparse hitches (>15 s from any other): 0 (0.00/min)
- low-severity tier: 184 (18.38/min)

## Frametimes
- p50 6.94 ms | p95 12.65 ms | p99 12.99 ms
- 1% low **41.9 fps**, 0.1% low **12.6 fps**, mean 142.5 fps
- frames below 50% of cap: 0.43%

## Data quality
- frametime rows: 88254 kept / 88254 read; **0 rejected** (> 10000 ms / non-positive / non-finite)

## Periodicity
- verdict: **periodic** (window 10.0 min, sparse assessable: True)
- steady: period 4.10 s (spectral peak 1.03 s, source interval) +- 0.01 s, p=0.002494, significant=True, fraction explained 0.22
- sparse: period 43.00 s (spectral peak 43.00 s, source spectral) +- 15.78 s, p=1, significant=False, fraction explained 0.22
- sparse_residual: period 86.00 s (spectral peak 43.00 s, source spectral) +- 18.52 s, p=1, significant=False, fraction explained 0.24

## Sparse hitches (explicit assessment)
- assessment: **irregular** (90 severe candidate(s) of 172 primary; severity gate 20.8 ms, steady phase 4.10 s removed)
- rate: 8.97/min (95% CI 7.18-10.87, poisson-bootstrap)
- intervals (s): p50 4.1, p90 4.1, CV 1.31
- interval mode 31.5 s; modal cluster n=1 cv=0.000 frac=0.50
- CAVEAT: only 2 interval(s) in the [20, 100] s band (<5): regularity cannot be established

## What moved around hitches
| signal.column | feature | cliff's d | z | p | q | hitch | control |
|---|---|---|---|---|---|---|---|
| hwmon.k10temp_temp1_c | step | +0.65 | 0.61 | 1.39e-47 | 6.3e-45 | 0.246 | -0.0124 |
| sys.forks_per_s | mean | +0.38 | 0.25 | 2.36e-17 | 5.3e-15 | 22 | 16.3 |
| sys.ctxt_per_s | min | -0.36 | -1.21 | 1.01e-15 | 1.5e-13 | 1.08e+04 | 1.17e+04 |
| sys.intr_per_s | min | -0.31 | -0.91 | 1.3e-11 | 1.5e-09 | 8e+03 | 8.61e+03 |
| cpu.cpu_util_avg | mean | +0.27 | 0.18 | 2.84e-09 | 2.6e-07 | 3.76 | 3.63 |
| cpu.cpu_util_avg | step | +0.26 | 0.34 | 4.68e-09 | 3.5e-07 | 0.298 | -0.0312 |
| gpu.power_w | step | -0.25 | -0.04 | 3.41e-08 | 1.9e-06 | -0.0567 | -0.0308 |
| cpu.cpu3_util | max | +0.25 | 0.48 | 1.84e-08 | 1.2e-06 | 54.9 | 48.8 |
| sys.forks_per_s | step | +0.24 | 0.28 | 1.88e-07 | 9.4e-06 | 11.6 | -1.21 |
| cpu.cpu_util_avg | max | +0.22 | 0.17 | 8.67e-07 | 3.9e-05 | 7.96 | 7.42 |
| cpufreq.cpu20_mhz | max | -0.21 | -0.14 | 2.65e-06 | 0.00011 | 5.09e+03 | 5.1e+03 |
| sys.intr_per_s | step | +0.21 | 0.19 | 5.19e-06 | 0.0002 | 633 | -43.6 |
| cpu.cpu3_util | mean | +0.20 | 0.38 | 1.44e-05 | 0.00043 | 21.2 | 19.5 |
| sys.psi_io_some_total | step | -0.19 | -0.26 | 2.92e-05 | 0.00082 | 1.49e+04 | 1.56e+04 |
| cpu.cpu3_util | step | +0.19 | 0.31 | 3.57e-05 | 0.00095 | 2.17 | -0.14 |

| log | near hitch | near control | template |
|---|---|---|---|
| journal | 1 | 0 | `HOSTNAME systemd[#]: idle-reaper.service: Deactivated ` |
| journal | 1 | 0 | `HOSTNAME systemd[#]: Finished Stop the on-demand background stac` |
| journal | 1 | 0 | `HOSTNAME systemd[#]: Starting Stop the on-demand background stac` |

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

