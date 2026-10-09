# Stutter report — live-baseline-3

- run-dir: `/path/to/repo/runs/live-baseline-3`
- window: 6.0 min after warm-up (warm-up source: mark), 34202 frames
- hitch rule: frametime_ms > K * rolling_median(+-W, excl. centre) AND frametime_ms > FLOOR (K=2.5, W=1.0s, FLOOR=13.9 ms, merge<=100 ms)

## Hitches
- **236 hitches** (39.29/min); worst 3265.2 ms; median 92.7 ms
- isolated/sparse hitches (>15 s from any other): 0 (0.00/min)
- low-severity tier: 199 (33.13/min)

## Frametimes
- p50 7.61 ms | p95 13.53 ms | p99 18.06 ms
- 1% low **5.0 fps**, 0.1% low **0.9 fps**, mean 94.9 fps
- frames below 50% of cap: 3.81%

## Periodicity
- verdict: **aperiodic** (window 6.0 min, sparse assessable: True)
- steady: period 1.32 s (spectral peak 0.71 s, source interval) +- 0.12 s, p=1, significant=False, fraction explained 0.22
- sparse: period 51.46 s (spectral peak 51.46 s, source spectral) +- 23.21 s, p=0.9975, significant=False, fraction explained 0.24

## What moved around hitches
| signal.column | feature | z | p | hitch | control |
|---|---|---|---|---|---|
| mem.mem_total_mib | mean | -6.24 | 0.0359 | 3.18e+04 | 3.18e+04 |
| threads.main_cpu_pct | min | -3.24 | 1.31e-105 | 14.8 | 58.2 |
| net.netif0_rx_mbps | max | 2.89 | 3.46e-12 | 0.986 | 0.584 |
| threads.busiest_cpu_pct | min | -2.84 | 1.57e-91 | 37.2 | 61.7 |
| threads.busiest_tid | max | 2.50 | 7.14e-270 | 3.74e+06 | 3.74e+06 |
| sys.intr_per_s | min | -2.47 | 5.21e-100 | 1.57e+04 | 3.6e+04 |
| threads.proc_cpu_pct | min | -2.47 | 4.07e-102 | 144 | 311 |
| sys.ctxt_per_s | min | -2.39 | 4.21e-99 | 2.21e+04 | 5.81e+04 |
| cpu.cpu_util_avg | min | -2.18 | 2.05e-93 | 7.76 | 14 |
| net_tcp.rtt_max_ms | min | -2.00 | nan | 102 | 102 |
| net_tcp.rtt_max_ms | max | -2.00 | nan | 102 | 102 |
| net_tcp.rtt_max_ms | mean | -1.94 | 0.0206 | 102 | 102 |
| mem.mem_total_mib | min | -1.50 | nan | 3.18e+04 | 3.18e+04 |
| mem.mem_total_mib | max | -1.50 | nan | 3.18e+04 | 3.18e+04 |
| cpu.cpu0_util | max | 1.45 | 1.22e-77 | 93.4 | 69.1 |

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

