# Stutter report — live-T2-spectate-no-cpu0

- run-dir: `/path/to/repo/runs/live-T2-spectate-no-cpu0`
- window: 6.0 min after warm-up (warm-up source: mark), 36367 frames
- hitch rule: frametime_ms > K * rolling_median(+-W, excl. centre) AND frametime_ms > FLOOR (K=2.5, W=1.0s, FLOOR=13.9 ms, merge<=100 ms)

## Hitches
- **11 hitches** (1.83/min); worst 28.8 ms; median 24.6 ms
- isolated/sparse hitches (>15 s from any other): 6 (1.00/min)
- low-severity tier: 223 (37.15/min)

## Frametimes
- p50 8.69 ms | p95 15.26 ms | p99 17.16 ms
- 1% low **54.5 fps**, 0.1% low **46.1 fps**, mean 101.0 fps
- frames below 50% of cap: 12.50%

## Data quality
- frametime rows: 48749 kept / 48749 read; **0 rejected** (> 10000 ms / non-positive / non-finite)

## Periodicity
- verdict: **aperiodic** (window 6.0 min, sparse assessable: True)
- steady: period 1.35 s (spectral peak 1.35 s, source spectral) +- 2.19 s, p=0.2594, significant=False, fraction explained 0.45
- sparse: period 45.01 s (spectral peak 30.01 s, source interval) +- 13.50 s, p=0.8753, significant=False, fraction explained 0.36

## Sparse hitches (explicit assessment)
- assessment: **irregular** (9 severe candidate(s) of 11 primary; severity gate 20.8 ms)
- rate: 1.50/min (95% CI 0.67-2.50, poisson-bootstrap)
- intervals (s): p50 19.6, p90 62.6, CV 0.95
- interval mode 46.5 s; modal cluster n=1 cv=0.000 frac=1.00
- CAVEAT: only 1 interval(s) in the [20, 100] s band (<5): regularity cannot be established

## What moved around hitches
| signal.column | feature | cliff's d | z | p | q | hitch | control |
|---|---|---|---|---|---|---|---|
| net.netif0_rx_mbps | max | +0.52 | 1.57 | 0.00345 | 0.46 | 0.671 | 0.513 |
| cpu.cpu2_util | max | -0.48 | -0.79 | 0.00683 | 0.49 | 49.8 | 59.9 |
| sys.psi_io_some_total | step | +0.47 | 1.04 | 0.00623 | 0.49 | 1.84e+03 | 1.33e+03 |
| cpufreq.cpu22_mhz | max | -0.45 | -0.84 | 0.0117 | 0.65 | 4.39e+03 | 4.45e+03 |
| cpu.cpu3_util | max | -0.43 | -0.63 | 0.0149 | 0.71 | 64.2 | 74 |
| net.netif0_rx_pps | max | +0.43 | 1.05 | 0.0157 | 0.71 | 86.2 | 68.1 |
| disk.nvme0n1_read_mbs | max | +0.43 | 0.41 | 0.00355 | 0.46 | 5.2 | 2.27 |
| disk.nvme0n1_read_mbs | mean | +0.43 | 0.27 | 0.00382 | 0.46 | 1.41 | 0.714 |
| disk.nvme0n1_read_iops | max | +0.43 | 0.18 | 0.00389 | 0.46 | 64.9 | 39.2 |
| cpu.cpu2_util | mean | -0.42 | -0.68 | 0.018 | 0.73 | 27.3 | 32.1 |
| disk.nvme0n1_read_iops | mean | +0.42 | 0.15 | 0.00464 | 0.46 | 17.9 | 11.6 |
| sys.ctxt_per_s | min | -0.40 | -0.47 | 0.0239 | 0.74 | 5.97e+04 | 6.24e+04 |
| disk.nvme0n1_util_pct | max | +0.40 | 0.60 | 0.0118 | 0.65 | 2.98 | 1.57 |
| cpufreq.cpu18_mhz | max | -0.40 | -0.90 | 0.027 | 0.74 | 4.38e+03 | 4.44e+03 |
| net.netif0_rx_mbps | mean | +0.39 | 1.02 | 0.03 | 0.74 | 0.499 | 0.434 |

## What the threads were blocked on during hitches

- window per hitch: [hitch_start - max(pre_ms, magnitude_ms), hitch_end] (pre_ms=50); threads seen: 75
- hitches analysed: 11/11 (a bucket counts when it covers >= 5% of the window)
- main thread off-CPU buckets: S/epoll_wait do_epoll_wait (75%); S/- 0 (25%)

| thread | state | syscall | wchan | hitches | % hitches | coverage | threads |
|---|---|---|---|---|---|---|---|
| dota2 | S | futex | __futex_wait | 11 | 100.0% | 100% | 5.0 |
| [vkcf] Analysis | S | futex | __futex_wait | 11 | 100.0% | 100% | 1.0 |
| [vkrt] Analysis | S | futex | __futex_wait | 11 | 100.0% | 100% | 1.0 |
| [vkps] Update | S | futex | __futex_wait | 11 | 100.0% | 100% | 1.0 |
| Async Pipeline | S | futex | __futex_wait | 11 | 100.0% | 100% | 31.0 |
| VmaDefragThread | S | futex | __futex_wait | 11 | 100.0% | 100% | 1.0 |
| VKRenderThread | S | futex | __futex_wait | 11 | 100.0% | 100% | 8.0 |
| AsyncTextureHoo | S | futex | __futex_wait | 11 | 100.0% | 100% | 1.0 |
| mangohud-hwinfo | S | futex | __futex_wait | 11 | 100.0% | 100% | 1.0 |
| CSteamAudioReve | S | futex | __futex_wait | 11 | 100.0% | 100% | 1.0 |
| CSteamAudioPart | S | futex | __futex_wait | 11 | 100.0% | 100% | 1.0 |
| V8 DefaultWorke | S | futex | __futex_wait | 11 | 100.0% | 100% | 1.0 |
| PulseHotplug | S | futex | __futex_wait | 11 | 100.0% | 100% | 1.0 |
| Panorama Image | S | futex | __futex_wait | 11 | 100.0% | 100% | 1.0 |
| SaveJob/0 | S | futex | __futex_wait | 11 | 100.0% | 100% | 1.0 |
| AudioMixer | S | futex | __futex_wait | 11 | 100.0% | 100% | 1.0 |
| cuda0000a40002a | S | poll | do_sys_poll | 11 | 100.0% | 100% | 1.0 |
| dota2 | S | clock_nanosleep | hrtimer_nanosleep | 11 | 100.0% | 100% | 1.0 |
| dota2 | S | epoll_wait | do_epoll_wait | 11 | 100.0% | 100% | 1.0 |
| AsyncIOService/ | S | futex | __futex_wait | 11 | 100.0% | 100% | 3.0 |
| dota2 | S | poll | do_sys_poll | 11 | 100.0% | 98% | 1.0 |
| SDLAudioP15 | S | futex | __futex_wait | 11 | 100.0% | 97% | 1.0 |
| PulseMainloop | S | poll | do_sys_poll | 11 | 100.0% | 95% | 1.0 |
| mangohud-nvidia | S | clock_nanosleep | hrtimer_nanosleep | 11 | 100.0% | 90% | 1.0 |
| GlobPool/6 | S | futex | __futex_wait | 11 | 100.0% | 66% | 1.0 |
| GlobPool/4 | S | futex | __futex_wait | 11 | 100.0% | 62% | 1.0 |
| GlobPool/5 | S | futex | __futex_wait | 11 | 100.0% | 60% | 1.0 |
| GlobPool/2 | S | futex | __futex_wait | 11 | 100.0% | 57% | 1.0 |
| GlobPool/1 | S | futex | __futex_wait | 11 | 100.0% | 57% | 1.0 |
| GlobPool/3 | S | futex | __futex_wait | 11 | 100.0% | 56% | 1.0 |

### Per-thread-name CPU (threads_cpu.csv)

| thread | cpu% (mean) | samples | threads |
|---|---|---|---|
| mangohud-nvidia | 1740848.53 | 503 | 1 |
| dota2 | 1345344.68 | 1153 | 6 |
| AsyncIOService/ | 575836.57 | 84 | 3 |
| VKRenderThread | 530799.95 | 1099 | 8 |
| GlobPool/1 | 466961.61 | 463 | 1 |
| GlobPool/0 | 459724.94 | 459 | 1 |
| GlobPool/6 | 453775.67 | 462 | 1 |
| GlobPool/5 | 439460.05 | 456 | 1 |
| GlobPool/2 | 437997.31 | 463 | 1 |
| GlobPool/3 | 433667.15 | 461 | 1 |
| GlobPool/4 | 431198.47 | 458 | 1 |
| mangohud-hwinfo | 405742.77 | 50 | 1 |
| PulseMainloop | 242229.05 | 124 | 1 |
| AsyncTextureHoo | 235819.01 | 11 | 1 |
| [vkps] Update | 190171.60 | 62 | 1 |


## Artifacts
- `hitches.csv`
- `stats.json`
- `correlation_signals.csv`
- `correlation_logs.csv`
- `blocked_on.csv`
- `frametime_trace.png`
- `hitch_timeline.png`
- `interval_histogram.png`
- `spectrum_autocorr.png`
- `correlation_panel.png`

