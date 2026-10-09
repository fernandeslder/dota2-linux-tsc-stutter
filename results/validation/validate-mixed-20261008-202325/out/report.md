# Stutter report — validate-mixed-20261008-202325

- run-dir: `/path/to/repo/runs/validate-mixed-20261008-202325`
- window: 9.9 min after warm-up (warm-up source: mark), 86428 frames
- hitch rule: frametime_ms > K * rolling_median(+-W, excl. centre) AND frametime_ms > FLOOR (K=2.5, W=1.0s, FLOOR=13.9 ms, merge<=100 ms)

## Hitches
- **224 hitches** (22.55/min); worst 90.9 ms; median 56.0 ms
- isolated/sparse hitches (>15 s from any other): 0 (0.00/min)
- low-severity tier: 386 (38.85/min)

## Frametimes
- p50 6.93 ms | p95 12.68 ms | p99 13.63 ms
- 1% low **41.3 fps**, 0.1% low **13.7 fps**, mean 145.0 fps
- frames below 50% of cap: 0.85%

## Data quality
- frametime rows: 89175 kept / 89175 read; **0 rejected** (> 10000 ms / non-positive / non-finite)

## Periodicity
- verdict: **periodic** (window 10.0 min, sparse assessable: True)
- steady: period 3.55 s (spectral peak 0.50 s, source interval) +- 0.01 s, p=0.002494, significant=True, fraction explained 0.22
- sparse: period 45.96 s (spectral peak 45.96 s, source spectral) +- 16.44 s, p=0.9701, significant=False, fraction explained 0.21
- sparse_residual: period 31.45 s (spectral peak 31.45 s, source spectral) +- 16.89 s, p=0.4838, significant=False, fraction explained 0.24

## Sparse hitches (explicit assessment)
- assessment: **irregular** (38 severe candidate(s) of 224 primary; severity gate 20.8 ms, steady phase 3.55 s removed)
- rate: 3.82/min (95% CI 2.61-5.02, poisson-bootstrap)
- intervals (s): p50 12.6, p90 33.8, CV 0.80
- interval mode 31.5 s; modal cluster n=4 cv=0.058 frac=0.67

## What moved around hitches
| signal.column | feature | cliff's d | z | p | q | hitch | control |
|---|---|---|---|---|---|---|---|
| hwmon.k10temp_temp1_c | step | +0.49 | 0.57 | 3.41e-36 | 1.6e-33 | 0.177 | -0.0295 |
| sys.forks_per_s | mean | +0.43 | 0.47 | 8.66e-28 | 2e-25 | 22.1 | 14.2 |
| cpu.cpu_util_avg | mean | +0.30 | 0.31 | 3.76e-14 | 4.4e-12 | 5.47 | 5.21 |
| gpu.power_w | min | -0.28 | -0.42 | 1.1e-12 | 1e-10 | 11.8 | 14.1 |
| cpu.cpu_util_avg | max | +0.27 | 0.35 | 4.79e-12 | 3.7e-10 | 10.6 | 9.48 |
| gpu.pstate | max | +0.26 | 0.42 | 5.55e-12 | 3.7e-10 | 5.97 | 4.89 |
| gpu.pcie_gen | min | -0.26 | -0.44 | 1.46e-11 | 7.7e-10 | 1.77 | 2.22 |
| gpu.mem_clock_mhz | min | -0.25 | -0.38 | 4.08e-11 | 1.9e-09 | 1.8e+03 | 3.04e+03 |
| sys.procs_running | mean | +0.24 | 0.40 | 6.03e-10 | 2.4e-08 | 4.09 | 3.88 |
| gpu.video_clock_mhz | min | -0.24 | -0.34 | 8.6e-12 | 5.1e-10 | 920 | 1.01e+03 |
| gpu.mem_clock_mhz | mean | -0.24 | -0.44 | 6.09e-10 | 2.4e-08 | 2.88e+03 | 4.34e+03 |
| gpu.mem_util | mean | +0.24 | 0.39 | 8.94e-10 | 3.2e-08 | 13.4 | 9.65 |
| gpu.power_w | mean | -0.24 | -0.38 | 1.59e-09 | 5e-08 | 14.3 | 16.4 |
| gpu.mem_util | max | +0.24 | 0.30 | 1.39e-09 | 4.7e-08 | 18.9 | 14.5 |
| gpu.pstate | mean | +0.24 | 0.36 | 1.79e-09 | 5e-08 | 4.78 | 3.86 |

| log | near hitch | near control | template |
|---|---|---|---|
| dmesg | 10 | 0 | `HOSTNAME kernel: ptrace attach notice (process names omitted)` |
| journal | 10 | 0 | `HOSTNAME kernel: ptrace attach notice (process names omitted)` |
| dmesg | 1 | 0 | `HOSTNAME kernel: __report_access: # callbacks suppressed` |
| journal | 1 | 0 | `HOSTNAME systemd[#]: idle-reaper.service: Deactivated ` |
| journal | 1 | 0 | `HOSTNAME kernel: __report_access: # callbacks suppressed` |
| journal | 1 | 0 | `HOSTNAME systemd[#]: Starting Stop the on-demand background stac` |
| journal | 1 | 0 | `HOSTNAME systemd[#]: Finished Stop the on-demand background stac` |
| journal | 0 | 10 | `HOSTNAME privileged-cmd[#]: <command log line>` |

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

