# Stutter report — live-baseline-1

- run-dir: `/path/to/repo/runs/live-baseline-1`
- window: 5.3 min after warm-up (warm-up source: mark), 28293 frames
- hitch rule: frametime_ms > K * rolling_median(+-W, excl. centre) AND frametime_ms > FLOOR (K=2.5, W=1.0s, FLOOR=13.9 ms, merge<=100 ms)

## Hitches
- **288 hitches** (54.57/min); worst 1734.2 ms; median 69.9 ms
- isolated/sparse hitches (>15 s from any other): 0 (0.00/min)
- low-severity tier: 203 (38.47/min)

## Frametimes
- p50 8.51 ms | p95 15.72 ms | p99 28.42 ms
- 1% low **7.1 fps**, 0.1% low **1.6 fps**, mean 89.4 fps
- frames below 50% of cap: 14.00%

## Periodicity
- verdict: **aperiodic** (window 5.3 min, sparse assessable: True)
- steady: period 1.19 s (spectral peak 2.25 s, source interval) +- 0.10 s, p=0.8354, significant=False, fraction explained 0.23
- sparse: period 52.85 s (spectral peak 52.85 s, source spectral) +- 12.59 s, p=0.6808, significant=False, fraction explained 0.24

## What moved around hitches
| signal.column | feature | z | p | hitch | control |
|---|---|---|---|---|---|
| cpufreq.cpu21_mhz | min | 58929470726924.66 | 3.68e-19 | 1.51e+03 | 1.48e+03 |
| threads.busiest_tid | max | 9.88 | 2.96e-292 | 3.6e+06 | 3.6e+06 |
| threads.busiest_cpu_pct | min | -3.86 | 2.11e-115 | 34.5 | 57.9 |
| threads.proc_cpu_pct | min | -2.98 | 2.43e-138 | 150 | 315 |
| threads.main_cpu_pct | min | -2.98 | 7.27e-127 | 15.1 | 55.9 |
| sys.ctxt_per_s | min | -2.69 | 2.55e-133 | 2.45e+04 | 5.92e+04 |
| sys.intr_per_s | min | -2.68 | 4.15e-133 | 1.8e+04 | 3.78e+04 |
| cpu.cpu_util_avg | min | -2.45 | 4.68e-121 | 9.24 | 15.1 |
| threads.busiest_tid | mean | 2.18 | 7.84e-267 | 3.6e+06 | 3.6e+06 |
| threads.busiest_cpu_pct | mean | -2.03 | 2.23e-57 | 79.2 | 83 |
| disk.nvme0n1_read_mbs | mean | 1.83 | 0.0244 | 4.22 | 0.898 |
| disk.nvme0n1_read_mbs | max | 1.67 | 0.00754 | 33.9 | 7.4 |
| disk.nvme0n1_write_mbs | max | 1.66 | 6e-05 | 2.99 | 0.404 |
| threads.proc_cpu_pct | mean | -1.54 | 7.67e-80 | 353 | 407 |
| disk.nvme0n1_write_mbs | mean | 1.53 | 0.000712 | 0.307 | 0.0561 |

| log | near hitch | near control | template |
|---|---|---|---|
| journal | 2 | 0 | `HOSTNAME systemd[#]: Starting Stop the on-demand background stac` |
| journal | 2 | 0 | `HOSTNAME systemd[#]: idle-reaper.service: Deactivated ` |
| journal | 2 | 0 | `HOSTNAME systemd[#]: Finished Stop the on-demand background stac` |

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

