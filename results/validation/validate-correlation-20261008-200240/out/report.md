# Stutter report — validate-correlation-20261008-200240

- run-dir: `/path/to/repo/runs/validate-correlation-20261008-200240`
- window: 6.0 min after warm-up (warm-up source: mark), 51423 frames
- hitch rule: frametime_ms > K * rolling_median(+-W, excl. centre) AND frametime_ms > FLOOR (K=2.5, W=1.0s, FLOOR=13.9 ms, merge<=100 ms)

## Hitches
- **174 hitches** (29.00/min); worst 109.9 ms; median 49.1 ms
- isolated/sparse hitches (>15 s from any other): 0 (0.00/min)
- low-severity tier: 257 (42.83/min)

## Frametimes
- p50 6.94 ms | p95 12.73 ms | p99 13.74 ms
- 1% low **39.1 fps**, 0.1% low **13.2 fps**, mean 142.9 fps
- frames below 50% of cap: 0.93%

## Data quality
- frametime rows: 54114 kept / 54114 read; **0 rejected** (> 10000 ms / non-positive / non-finite)

## Periodicity
- verdict: **periodic** (window 6.0 min, sparse assessable: True)
- steady: period 2.59 s (spectral peak 1.33 s, source interval) +- 0.31 s, p=0.002494, significant=True, fraction explained 0.22
- sparse: period 40.16 s (spectral peak 40.16 s, source spectral) +- 20.86 s, p=0.9626, significant=False, fraction explained 0.21
- sparse_residual: period 36.14 s (spectral peak 36.14 s, source spectral) +- 19.09 s, p=0.9751, significant=False, fraction explained 0.23

## Sparse hitches (explicit assessment)
- assessment: **irregular** (29 severe candidate(s) of 174 primary; severity gate 20.8 ms, steady phase 2.59 s removed)
- rate: 4.82/min (95% CI 3.15-6.64, poisson-bootstrap)
- intervals (s): p50 11.4, p90 28.4, CV 0.99
- interval mode 37.5 s; modal cluster n=3 cv=0.110 frac=1.00
- CAVEAT: only 3 interval(s) in the [20, 100] s band (<5): regularity cannot be established

## What moved around hitches
| signal.column | feature | cliff's d | z | p | q | hitch | control |
|---|---|---|---|---|---|---|---|
| cpu.cpu_util_avg | mean | +0.71 | 2.16 | 6.78e-57 | 3.5e-54 | 10.2 | 6.87 |
| hwmon.k10temp_temp3_c | max | +0.66 | 1.52 | 1.18e-49 | 2e-47 | 96.2 | 89 |
| sys.procs_running | mean | +0.66 | 1.96 | 2.14e-49 | 2.7e-47 | 4.88 | 3.61 |
| hwmon.k10temp_temp1_c | step | +0.66 | 3.98 | 1.09e-49 | 2e-47 | 1.25 | -0.519 |
| cpu.cpu_util_avg | max | +0.63 | 1.11 | 5.48e-45 | 5.6e-43 | 20.4 | 13.6 |
| hwmon.k10temp_temp1_c | max | +0.63 | 1.26 | 1.56e-44 | 1.3e-42 | 96 | 94.3 |
| hwmon.k10temp_temp3_c | mean | +0.59 | 1.18 | 2.25e-39 | 1.6e-37 | 88.9 | 85 |
| sys.psi_io_some_total | step | -0.59 | -1.17 | 4.89e-39 | 3.1e-37 | 6.59e+03 | 8.92e+03 |
| cpufreq.cpu0_mhz | mean | -0.51 | -0.79 | 1.19e-29 | 6.8e-28 | 4.73e+03 | 4.89e+03 |
| cpu.cpu_util_avg | step | +0.48 | 1.71 | 6.37e-27 | 3.3e-25 | 3.77 | -0.00357 |
| sys.procs_running | step | +0.43 | 0.97 | 9.79e-22 | 4.5e-20 | 0.993 | -0.0706 |
| hwmon.k10temp_temp4_c | max | +0.39 | 1.20 | 1.59e-18 | 6.8e-17 | 88.2 | 83.5 |
| cpufreq.cpu8_mhz | max | -0.39 | -0.96 | 6.13e-18 | 2.4e-16 | 5.02e+03 | 5.07e+03 |
| cpufreq.cpu4_mhz | max | -0.38 | -0.68 | 3.99e-17 | 1.4e-15 | 5.04e+03 | 5.07e+03 |
| sys.procs_running | max | +0.38 | 0.34 | 2.93e-17 | 1.1e-15 | 11.7 | 10.1 |

| log | near hitch | near control | template |
|---|---|---|---|
| dmesg | 20 | 0 | `HOSTNAME kernel: ptrace attach notice (process names omitted)` |
| journal | 20 | 0 | `HOSTNAME kernel: ptrace attach notice (process names omitted)` |
| journal | 2 | 0 | `HOSTNAME privileged-cmd[#]: pam_unix(<svc>:session): session opened for user ` |
| journal | 1 | 0 | `HOSTNAME privileged-cmd[#]: <command log line>` |
| journal | 1 | 0 | `HOSTNAME privileged-cmd[#]: <command log line>` |
| journal | 2 | 21 | `HOSTNAME privileged-cmd[#]: pam_unix(<svc>:session): session closed for user ` |
| dmesg | 2 | 70 | `HOSTNAME kernel: __report_access: # callbacks suppressed` |
| journal | 2 | 70 | `HOSTNAME kernel: __report_access: # callbacks suppressed` |

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

