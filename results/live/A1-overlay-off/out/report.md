# Stutter report — live-A1-overlay-off

- run-dir: `/path/to/repo/runs/live-A1-overlay-off`
- window: 6.0 min after warm-up (warm-up source: mark), 34431 frames
- hitch rule: frametime_ms > K * rolling_median(+-W, excl. centre) AND frametime_ms > FLOOR (K=2.5, W=1.0s, FLOOR=13.9 ms, merge<=100 ms)

## Hitches
- **245 hitches** (40.77/min); worst 2098.9 ms; median 97.1 ms
- isolated/sparse hitches (>15 s from any other): 0 (0.00/min)
- low-severity tier: 251 (41.77/min)

## Frametimes
- p50 7.81 ms | p95 14.23 ms | p99 18.70 ms
- 1% low **6.2 fps**, 0.1% low **1.3 fps**, mean 95.5 fps
- frames below 50% of cap: 6.17%

## Periodicity
- verdict: **aperiodic** (window 6.0 min, sparse assessable: True)
- steady: period 1.42 s (spectral peak 1.06 s, source interval) +- 0.10 s, p=0.9875, significant=False, fraction explained 0.22
- sparse: period 45.05 s (spectral peak 45.05 s, source spectral) +- 22.52 s, p=0.7157, significant=False, fraction explained 0.25

## What moved around hitches
| signal.column | feature | z | p | hitch | control |
|---|---|---|---|---|---|
| cpufreq.cpu21_mhz | min | 180141397570561.06 | 1.47e-23 | 1.52e+03 | 1.48e+03 |
| cpufreq.cpu29_mhz | min | 122441325766597.47 | 9.41e-15 | 1.51e+03 | 1.48e+03 |
| cpufreq.cpu25_mhz | min | 68479391508172.18 | 2.54e-10 | 1.5e+03 | 1.48e+03 |
| mem.mem_total_mib | mean | -40.41 | 0.0102 | 3.18e+04 | 3.18e+04 |
| threads.busiest_tid | max | 3.86 | 1.47e-276 | 3.75e+06 | 3.75e+06 |
| threads.main_cpu_pct | min | -3.18 | 7.29e-109 | 11.6 | 56.5 |
| net_tcp.rtt_max_ms | min | -3.00 | nan | 102 | 102 |
| net_tcp.rtt_max_ms | max | -3.00 | nan | 102 | 102 |
| net_tcp.rtt_max_ms | mean | -3.00 | 4.17e-11 | 102 | 102 |
| sys.intr_per_s | min | -2.80 | 8.17e-111 | 1.55e+04 | 3.57e+04 |
| sys.ctxt_per_s | min | -2.79 | 2.43e-108 | 2.22e+04 | 5.78e+04 |
| threads.proc_cpu_pct | min | -2.69 | 1.82e-113 | 141 | 319 |
| cpu.cpu_util_avg | min | -2.49 | 1.83e-102 | 7.5 | 14.2 |
| threads.busiest_cpu_pct | min | -2.38 | 4.69e-61 | 36.7 | 58.1 |
| threads.busiest_cpu_pct | max | 2.21 | 1.55e-11 | 103 | 101 |

| log | near hitch | near control | template |
|---|---|---|---|
| dmesg | 10 | 0 | `HOSTNAME kernel: ptrace attach notice (process names omitted)` |
| journal | 10 | 0 | `HOSTNAME kernel: ptrace attach notice (process names omitted)` |
| dmesg | 1 | 0 | `HOSTNAME kernel: __report_access: # callbacks suppressed` |
| journal | 1 | 0 | `HOSTNAME kernel: __report_access: # callbacks suppressed` |

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

