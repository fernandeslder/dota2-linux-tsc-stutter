# Stutter report — live-FP3

- run-dir: `/path/to/repo/runs/live-FP3`
- window: 6.0 min after warm-up (warm-up source: mark), 39835 frames
- hitch rule: frametime_ms > K * rolling_median(+-W, excl. centre) AND frametime_ms > FLOOR (K=2.5, W=1.0s, FLOOR=13.9 ms, merge<=100 ms)

## Hitches
- **19 hitches** (3.17/min); worst 47.5 ms; median 20.2 ms
- isolated/sparse hitches (>15 s from any other): 3 (0.50/min)
- low-severity tier: 586 (97.62/min)

## Frametimes
- p50 7.68 ms | p95 14.59 ms | p99 16.32 ms
- 1% low **53.2 fps**, 0.1% low **32.1 fps**, mean 110.6 fps
- frames below 50% of cap: 8.72%

## Data quality
- frametime rows: 51678 kept / 51678 read; **0 rejected** (> 10000 ms / non-positive / non-finite)

## Periodicity
- verdict: **aperiodic** (window 6.0 min, sparse assessable: True)
- steady: period 3.96 s (spectral peak 1.64 s, source interval) +- 1.24 s, p=0.3791, significant=False, fraction explained 0.32
- sparse: period 36.02 s (spectral peak 36.02 s, source spectral) +- 16.74 s, p=0.01746, significant=False, fraction explained 0.42

## Sparse hitches (explicit assessment)
- assessment: **none** (8 severe candidate(s) of 19 primary; severity gate 20.8 ms)
- rate: 1.33/min (95% CI 0.50-2.33, poisson-bootstrap)
- intervals (s): p50 6.4, p90 77.2, CV 1.61

## What moved around hitches
| signal.column | feature | cliff's d | z | p | q | hitch | control |
|---|---|---|---|---|---|---|---|
| net.netif0_rx_pps | min | +0.47 | 0.68 | 0.000618 | 0.064 | 62.9 | 56.5 |
| cpu.cpu11_util | max | +0.43 | 1.83 | 0.00146 | 0.13 | 41.6 | 27.9 |
| gpu.power_w | step | -0.42 | -0.77 | 0.00225 | 0.17 | -1.57 | 0.0517 |
| net.netif0_tx_pps | min | +0.40 | 0.12 | 0.0029 | 0.17 | 32 | 31 |
| net.netif0_rx_pps | mean | +0.40 | 0.49 | 0.00336 | 0.17 | 715 | 200 |
| cpufreq.cpu23_mhz | max | -0.39 | -0.91 | 0.00416 | 0.17 | 2.74e+03 | 3.71e+03 |
| net.netif0_rx_mbps | mean | +0.39 | 0.49 | 0.00445 | 0.17 | 8.11 | 1.97 |
| net.netif0_tx_mbps | min | +0.37 | 0.07 | 0.00602 | 0.18 | 0.0489 | 0.0477 |
| cpu.cpu8_util | mean | +0.37 | 1.63 | 0.00632 | 0.18 | 30.9 | 24.8 |
| net.netif0_rx_mbps | max | +0.37 | 0.83 | 0.00706 | 0.19 | 31 | 4.55 |
| cpu.cpu13_util | min | +0.35 | 0.82 | 0.00728 | 0.19 | 14.8 | 8.2 |
| threads.busiest_cpu | max | -0.35 | -0.55 | 0.0093 | 0.21 | 21.9 | 25.2 |
| cpufreq.cpu31_mhz | min | -0.35 | -0.49 | 0.00904 | 0.21 | 2.5e+03 | 3.1e+03 |
| cpufreq.cpu31_mhz | mean | -0.34 | -0.61 | 0.0113 | 0.21 | 3.56e+03 | 3.87e+03 |
| mem.mem_slab_mib | min | +0.34 | 0.49 | 0.0122 | 0.22 | 3.37e+03 | 3.36e+03 |

## What the threads were blocked on during hitches

- window per hitch: [hitch_start - max(pre_ms, magnitude_ms), hitch_end] (pre_ms=50); threads seen: 75
- hitches analysed: 19/19 (a bucket counts when it covers >= 5% of the window)
- main thread off-CPU buckets: S/epoll_wait do_epoll_wait (48%); S/futex __futex_wait (23%); S/epoll_wait 0 (11%); S/- 0 (7%)

| thread | state | syscall | wchan | hitches | % hitches | coverage | threads |
|---|---|---|---|---|---|---|---|
| AsyncIOService/ | S | futex | __futex_wait | 19 | 100.0% | 100% | 3.0 |
| dota2 | S | futex | __futex_wait | 19 | 100.0% | 100% | 5.0 |
| [vkrt] Analysis | S | futex | __futex_wait | 19 | 100.0% | 100% | 1.0 |
| [vkps] Update | S | futex | __futex_wait | 19 | 100.0% | 100% | 1.0 |
| Async Pipeline | S | futex | __futex_wait | 19 | 100.0% | 100% | 31.0 |
| VmaDefragThread | S | futex | __futex_wait | 19 | 100.0% | 100% | 1.0 |
| AsyncTextureHoo | S | futex | __futex_wait | 19 | 100.0% | 100% | 1.0 |
| mangohud-hwinfo | S | futex | __futex_wait | 19 | 100.0% | 100% | 1.0 |
| CSteamAudioReve | S | futex | __futex_wait | 19 | 100.0% | 100% | 1.0 |
| CSteamAudioPart | S | futex | __futex_wait | 19 | 100.0% | 100% | 1.0 |
| V8 DefaultWorke | S | futex | __futex_wait | 19 | 100.0% | 100% | 1.0 |
| Panorama Image | S | futex | __futex_wait | 19 | 100.0% | 100% | 1.0 |
| SaveJob/0 | S | futex | __futex_wait | 19 | 100.0% | 100% | 1.0 |
| cuda0000a40002a | S | poll | do_sys_poll | 19 | 100.0% | 100% | 1.0 |
| dota2 | S | clock_nanosleep | hrtimer_nanosleep | 19 | 100.0% | 100% | 1.0 |
| PulseHotplug | S | futex | __futex_wait | 19 | 100.0% | 100% | 1.0 |
| [vkcf] Analysis | S | futex | __futex_wait | 19 | 100.0% | 100% | 1.0 |
| VKRenderThread | S | futex | __futex_wait | 19 | 100.0% | 99% | 8.0 |
| PulseMainloop | S | poll | do_sys_poll | 19 | 100.0% | 99% | 1.0 |
| dota2 | S | poll | do_sys_poll | 19 | 100.0% | 98% | 1.0 |
| SDLAudioP15 | S | futex | __futex_wait | 19 | 100.0% | 98% | 1.0 |
| dota2 | S | epoll_wait | do_epoll_wait | 19 | 100.0% | 98% | 1.0 |
| AudioMixer | S | futex | __futex_wait | 19 | 100.0% | 97% | 1.0 |
| mangohud-nvidia | S | clock_nanosleep | hrtimer_nanosleep | 19 | 100.0% | 91% | 1.0 |
| GlobPool/0 | S | futex | __futex_wait | 19 | 100.0% | 68% | 1.0 |
| GlobPool/3 | S | futex | __futex_wait | 19 | 100.0% | 67% | 1.0 |
| GlobPool/1 | S | futex | __futex_wait | 19 | 100.0% | 66% | 1.0 |
| GlobPool/4 | S | futex | __futex_wait | 19 | 100.0% | 65% | 1.0 |
| GlobPool/5 | S | futex | __futex_wait | 19 | 100.0% | 65% | 1.0 |
| GlobPool/6 | S | futex | __futex_wait | 19 | 100.0% | 63% | 1.0 |

### Per-thread-name CPU (threads_cpu.csv)

| thread | cpu% (mean) | samples | threads |
|---|---|---|---|
| mangohud-nvidia | 1427592.59 | 500 | 1 |
| dota2 | 1020859.70 | 1159 | 6 |
| VKRenderThread | 408558.36 | 1137 | 8 |
| AsyncIOService/ | 393699.31 | 97 | 3 |
| GlobPool/0 | 361730.02 | 452 | 1 |
| GlobPool/5 | 359251.60 | 451 | 1 |
| GlobPool/3 | 356577.78 | 456 | 1 |
| GlobPool/2 | 356179.67 | 460 | 1 |
| GlobPool/6 | 348906.57 | 454 | 1 |
| GlobPool/4 | 346936.64 | 460 | 1 |
| GlobPool/1 | 330263.61 | 453 | 1 |
| AudioMixer | 234858.09 | 90 | 1 |
| mangohud-hwinfo | 198437.10 | 52 | 1 |
| PulseMainloop | 194170.23 | 130 | 1 |
| SDLAudioP15 | 170898.63 | 51 | 1 |


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

