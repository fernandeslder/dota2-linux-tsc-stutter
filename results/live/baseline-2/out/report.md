# Stutter report — live-baseline-2

- run-dir: `/path/to/repo/runs/live-baseline-2`
- window: 6.0 min after warm-up (warm-up source: mark), 33301 frames
- hitch rule: frametime_ms > K * rolling_median(+-W, excl. centre) AND frametime_ms > FLOOR (K=2.5, W=1.0s, FLOOR=13.9 ms, merge<=100 ms)

## Hitches
- **237 hitches** (39.46/min); worst 2958.4 ms; median 82.3 ms
- isolated/sparse hitches (>15 s from any other): 0 (0.00/min)
- low-severity tier: 285 (47.45/min)

## Frametimes
- p50 7.84 ms | p95 14.56 ms | p99 18.61 ms
- 1% low **5.3 fps**, 0.1% low **0.8 fps**, mean 92.4 fps
- frames below 50% of cap: 7.61%

## Periodicity
- verdict: **aperiodic** (window 6.0 min, sparse assessable: True)
- steady: period 1.40 s (spectral peak 4.74 s, source interval) +- 0.15 s, p=0.9975, significant=False, fraction explained 0.24
- sparse: period 45.04 s (spectral peak 45.04 s, source spectral) +- 19.04 s, p=0.4339, significant=False, fraction explained 0.25

## What moved around hitches
| signal.column | feature | z | p | hitch | control |
|---|---|---|---|---|---|
| cpufreq.cpu17_mhz | min | 44820458311040.27 | 7.78e-06 | 1.49e+03 | 1.48e+03 |
| mem.mem_total_mib | mean | -13.70 | 0.24 | 3.18e+04 | 3.18e+04 |
| net.netif0_rx_mbps | max | 5.70 | 4.85e-05 | 1.29 | 0.598 |
| disk.nvme0n1_read_iops | mean | 4.89 | 2.24e-06 | 39.6 | 2.49 |
| disk.nvme0n1_read_iops | max | 3.52 | 2.88e-06 | 258 | 22.1 |
| net.netif0_tx_pps | max | 3.09 | 4.15e-32 | 103 | 54.5 |
| threads.busiest_tid | max | 2.51 | 2.52e-124 | 3.73e+06 | 3.73e+06 |
| net.netif0_rx_pps | max | 2.35 | 3.07e-11 | 173 | 103 |
| threads.busiest_cpu_pct | min | -2.26 | 6.62e-95 | 35 | 62.7 |
| net.netif0_tx_mbps | max | 2.13 | 9.53e-27 | 0.455 | 0.124 |
| disk.nvme0n1_read_mbs | mean | 2.07 | 2.12e-06 | 1.62 | 0.209 |
| threads.main_cpu_pct | min | -2.00 | 2.98e-91 | 13.2 | 53.8 |
| threads.proc_cpu_pct | min | -1.97 | 2.4e-83 | 147 | 311 |
| sys.intr_per_s | min | -1.85 | 6.63e-83 | 1.68e+04 | 3.52e+04 |
| sys.ctxt_per_s | min | -1.85 | 4.01e-80 | 2.34e+04 | 5.53e+04 |

| log | near hitch | near control | template |
|---|---|---|---|
| journal | 1 | 0 | `HOSTNAME systemd[#]: Finished Stop the on-demand background stac` |
| journal | 1 | 0 | `HOSTNAME systemd[#]: idle-reaper.service: Deactivated ` |
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

