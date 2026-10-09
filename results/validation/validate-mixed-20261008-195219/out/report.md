# Stutter report — validate-mixed-20261008-195219

- run-dir: `/path/to/repo/runs/validate-mixed-20261008-195219`
- window: 0.9 min after warm-up (warm-up source: mark), 8069 frames
- hitch rule: frametime_ms > K * rolling_median(+-W, excl. centre) AND frametime_ms > FLOOR (K=2.5, W=1.0s, FLOOR=13.9 ms, merge<=100 ms)

## Hitches
- **17 hitches** (18.02/min); worst 78.8 ms; median 62.4 ms
- isolated/sparse hitches (>15 s from any other): 0 (0.00/min)
- low-severity tier: 11 (11.66/min)

## Frametimes
- p50 6.94 ms | p95 8.94 ms | p99 12.95 ms
- 1% low **43.3 fps**, 0.1% low **13.9 fps**, mean 142.6 fps
- frames below 50% of cap: 0.38%

## Data quality
- frametime rows: 10757 kept / 10757 read; **0 rejected** (> 10000 ms / non-positive / non-finite)

## Periodicity
- verdict: **periodic** (window 10.0 min, sparse assessable: True)
- steady: period 3.98 s (spectral peak 0.50 s, source interval) +- 0.47 s, p=0.002494, significant=True, fraction explained 0.82
- sparse: period 85.33 s (spectral peak 85.33 s, source spectral) +- 3.25 s, p=0.2469, significant=False, fraction explained 0.24

## Sparse hitches (explicit assessment)
- assessment: **none** (2 severe candidate(s) of 17 primary; severity gate 20.8 ms, steady phase 3.98 s removed)
- rate: 0.20/min (95% CI 0.00-0.50, poisson-bootstrap)
- intervals (s): p50 11.4, p90 11.4, CV 0.00
- CAVEAT: only 2 sparse candidate(s) (<8): rate/period estimate is uncertain

## What moved around hitches
| signal.column | feature | cliff's d | z | p | q | hitch | control |
|---|---|---|---|---|---|---|---|
| cpufreq.cpu28_mhz | mean | +0.74 | 1.34 | 0.000699 | 0.26 | 3.4e+03 | 2.65e+03 |
| sys.forks_per_s | mean | +0.71 | 0.40 | 0.00109 | 0.26 | 53.7 | 26.3 |
| cpufreq.cpu8_mhz | step | +0.57 | 1.14 | 0.00946 | 0.92 | 184 | -517 |
| cpu.cpu6_util | mean | +0.54 | 1.16 | 0.0128 | 0.92 | 11.9 | 9.15 |
| cpufreq.cpu11_mhz | max | -0.52 | -5.96 | 0.017 | 0.92 | 4.39e+03 | 4.88e+03 |
| cpu.cpu28_util | max | +0.52 | 0.94 | 0.00801 | 0.92 | 22.7 | 15.9 |
| threads.busiest_cpu | max | +0.52 | 0.87 | 0.0169 | 0.92 | 25.9 | 21.4 |
| cpu.cpu15_util | step | -0.51 | -0.90 | 0.0202 | 0.92 | -3.06 | 0.799 |
| cpufreq.cpu6_mhz | step | +0.49 | 0.97 | 0.0238 | 0.92 | 253 | -365 |
| cpufreq.cpu28_mhz | max | +0.49 | 0.42 | 0.0238 | 0.92 | 4.86e+03 | 4.47e+03 |
| cpu.cpu2_util | max | +0.49 | 2.28 | 0.0197 | 0.92 | 56.7 | 42 |
| cpu.cpu23_util | mean | +0.48 | 0.81 | 0.0175 | 0.92 | 1.21 | 0.41 |
| cpu.cpu28_util | mean | +0.48 | 1.06 | 0.0283 | 0.92 | 3.41 | 1.92 |
| cpufreq.cpu26_mhz | max | -0.47 | 0.16 | 0.0327 | 0.92 | 4.86e+03 | 4.79e+03 |
| sys.intr_per_s | max | +0.47 | 1.00 | 0.0327 | 0.92 | 4.04e+04 | 3.18e+04 |

| log | near hitch | near control | template |
|---|---|---|---|
| journal | 1 | 0 | `HOSTNAME privileged-cmd[#]: pam_unix(<svc>:session): session closed for user ` |

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

