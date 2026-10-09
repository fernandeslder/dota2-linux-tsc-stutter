# Stutter report — validate-borderline-20261008-190826

- run-dir: `/path/to/repo/runs/validate-borderline-20261008-190826`
- window: 6.0 min after warm-up (warm-up source: mark), 51558 frames
- hitch rule: frametime_ms > K * rolling_median(+-W, excl. centre) AND frametime_ms > FLOOR (K=2.5, W=1.0s, FLOOR=13.9 ms, merge<=100 ms)

## Hitches
- **97 hitches** (16.25/min); worst 44.3 ms; median 26.8 ms
- isolated/sparse hitches (>15 s from any other): 0 (0.00/min)
- low-severity tier: 49 (8.21/min)

## Frametimes
- p50 6.94 ms | p95 8.68 ms | p99 12.82 ms
- 1% low **62.2 fps**, 0.1% low **30.4 fps**, mean 144.0 fps
- frames below 50% of cap: 0.30%

## Data quality
- frametime rows: 54255 kept / 54255 read; **0 rejected** (> 10000 ms / non-positive / non-finite)

## Periodicity
- verdict: **periodic** (window 6.0 min, sparse assessable: True)
- steady: period 4.09 s (spectral peak 1.36 s, source interval) +- 0.00 s, p=0.002494, significant=True, fraction explained 0.41
- sparse: period 51.36 s (spectral peak 51.36 s, source spectral) +- 18.14 s, p=1, significant=False, fraction explained 0.20
- sparse_residual: period 89.88 s (spectral peak 89.88 s, source spectral) +- 16.19 s, p=0.9975, significant=False, fraction explained 0.21

## Sparse hitches (explicit assessment)
- assessment: **none** (0 severe candidate(s) of 97 primary; severity gate 20.8 ms, steady phase 4.09 s removed)
- CAVEAT: no severe isolated hitches in the window

## What moved around hitches
| signal.column | feature | cliff's d | z | p | q | hitch | control |
|---|---|---|---|---|---|---|---|
| hwmon.k10temp_temp1_c | step | +0.55 | 0.28 | 3.94e-20 | 1.8e-17 | 0.202 | 0.0338 |
| sys.forks_per_s | mean | +0.38 | 0.08 | 1.49e-10 | 3.4e-08 | 22.2 | 19.4 |
| sys.forks_per_s | max | +0.32 | 0.08 | 6.34e-08 | 9.7e-06 | 233 | 205 |
| cpu.cpu_util_avg | mean | +0.27 | 0.14 | 5.84e-06 | 0.00054 | 4.01 | 3.9 |
| sys.psi_io_some_total | step | -0.24 | -0.41 | 6.41e-05 | 0.0042 | 1.35e+04 | 1.46e+04 |
| cpufreq.cpu19_mhz | max | -0.22 | -0.39 | 0.000294 | 0.012 | 5.09e+03 | 5.11e+03 |
| cpufreq.cpu2_mhz | max | -0.21 | -0.33 | 0.000402 | 0.014 | 5.22e+03 | 5.23e+03 |
| sys.intr_per_s | mean | +0.21 | 0.17 | 0.000631 | 0.02 | 1.45e+04 | 1.4e+04 |
| cpufreq.cpu17_mhz | mean | +0.20 | 0.31 | 0.000656 | 0.02 | 1.85e+03 | 1.74e+03 |
| cpu.cpu_util_avg | step | +0.19 | 0.18 | 0.00119 | 0.032 | 0.22 | 0.0234 |
| hwmon.k10temp_temp3_c | min | +0.19 | 0.26 | 0.00113 | 0.032 | 72.7 | 72.5 |
| cpu.cpu22_util | mean | +0.19 | 0.25 | 0.00134 | 0.034 | 3.3 | 2.85 |
| cpufreq.cpu19_mhz | mean | -0.19 | -0.30 | 0.0015 | 0.036 | 4.12e+03 | 4.27e+03 |
| cpu.cpu21_util | max | +0.19 | 0.41 | 9.71e-05 | 0.0056 | 8.47 | 5.08 |
| cpu.cpu20_util | mean | +0.19 | 0.33 | 0.00197 | 0.044 | 2.54 | 2.16 |

| log | near hitch | near control | template |
|---|---|---|---|
| journal | 0 | 1 | `HOSTNAME systemd[#]: snapshot-cleanup.service: Consumed #ms CPU tim` |
| journal | 0 | 1 | `HOSTNAME systemd[#]: snapshot-cleanup.service: Deactivated successf` |
| journal | 0 | 17 | `HOSTNAME systemd-helper[#]: Running timeline cleanup for 'root'.` |
| journal | 0 | 17 | `HOSTNAME systemd[#]: Started DBus interface for snapshots.` |
| journal | 0 | 17 | `HOSTNAME systemd[#]: Started Hourly Cleanup of Snapshots.` |
| journal | 0 | 17 | `HOSTNAME systemd-helper[#]: Running empty-pre-post cleanup for 'ro` |
| journal | 0 | 17 | `HOSTNAME systemd[#]: Starting DBus interface for snapshots...` |
| journal | 0 | 17 | `HOSTNAME systemd-helper[#]: Running cleanup for 'root'.` |

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

