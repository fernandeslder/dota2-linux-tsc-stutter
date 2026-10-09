# Stutter report — live-FP2

- run-dir: `/path/to/repo/runs/live-FP2`
- window: 10.3 min after warm-up (warm-up source: mark), 72504 frames
- hitch rule: frametime_ms > K * rolling_median(+-W, excl. centre) AND frametime_ms > FLOOR (K=2.5, W=1.0s, FLOOR=13.9 ms, merge<=100 ms)

## Hitches
- **19 hitches** (1.85/min); worst 31.0 ms; median 23.3 ms
- isolated/sparse hitches (>15 s from any other): 5 (0.49/min)
- low-severity tier: 526 (51.20/min)

## Frametimes
- p50 7.43 ms | p95 13.42 ms | p99 14.89 ms
- 1% low **62.6 fps**, 0.1% low **51.5 fps**, mean 117.7 fps
- frames below 50% of cap: 3.06%

## Data quality
- frametime rows: 85841 kept / 85841 read; **0 rejected** (> 10000 ms / non-positive / non-finite)

## Periodicity
- verdict: **aperiodic** (window 20.0 min, sparse assessable: True)
- steady: period 5.00 s (spectral peak 0.66 s, source interval) +- 2.87 s, p=0.1372, significant=False, fraction explained 0.21
- sparse: period 42.83 s (spectral peak 33.35 s, source interval) +- 12.49 s, p=0.4813, significant=False, fraction explained 0.32

## Sparse hitches (explicit assessment)
- assessment: **irregular** (11 severe candidate(s) of 19 primary; severity gate 20.8 ms)
- rate: 0.55/min (95% CI 0.25-0.90, poisson-bootstrap)
- intervals (s): p50 25.9, p90 133.3, CV 1.04
- interval mode 34.5 s; modal cluster n=1 cv=0.000 frac=0.50
- CAVEAT: only 2 interval(s) in the [20, 100] s band (<5): regularity cannot be established

## What moved around hitches
| signal.column | feature | cliff's d | z | p | q | hitch | control |
|---|---|---|---|---|---|---|---|
| net.netif0_rx_mbps | mean | +0.60 | 2.89 | 1.48e-05 | 0.0017 | 0.597 | 0.39 |
| sys.ctxt_per_s | min | -0.59 | -0.51 | 2.48e-05 | 0.0017 | 6.57e+04 | 6.82e+04 |
| net.netif0_rx_mbps | min | +0.56 | 1.87 | 5.73e-05 | 0.0026 | 0.409 | 0.302 |
| threads.proc_rss_mib | step | +0.53 | 1.32 | 0.000162 | 0.0067 | 1.62 | 0.117 |
| net.netif0_rx_mbps | max | +0.48 | 3.76 | 0.000633 | 0.024 | 0.911 | 0.481 |
| mem.mem_cached_mib | step | +0.46 | 1.26 | 0.000915 | 0.032 | 2.81 | 0.481 |
| net.netif0_rx_pps | min | +0.45 | 1.68 | 0.00125 | 0.035 | 64.4 | 48.1 |
| mem.dirty_mib | step | +0.43 | 0.49 | 0.00188 | 0.039 | 0.245 | -0.0642 |
| gpu.mem_util | min | -0.39 | -0.80 | 0.00175 | 0.038 | 8.42 | 9.07 |
| net.netif0_rx_pps | mean | +0.38 | 1.49 | 0.00709 | 0.12 | 91.6 | 64.2 |
| cpu.cpu6_util | min | +0.35 | 0.58 | 0.00989 | 0.16 | 18.7 | 15.3 |
| cpu.cpu1_util | mean | +0.34 | 0.60 | 0.0145 | 0.22 | 45.2 | 38.6 |
| mem.mem_available_mib | min | -0.34 | -0.49 | 0.0146 | 0.22 | 1.35e+04 | 1.36e+04 |
| mem.mem_available_mib | mean | -0.33 | -0.43 | 0.0171 | 0.23 | 1.35e+04 | 1.36e+04 |
| mem.mem_available_mib | max | -0.33 | -0.42 | 0.0188 | 0.24 | 1.35e+04 | 1.36e+04 |

| log | near hitch | near control | template |
|---|---|---|---|
| dmesg | 0 | 1 | `HOSTNAME kernel: __report_access: # callbacks suppressed` |
| dmesg | 0 | 10 | `HOSTNAME kernel: ptrace attach notice (process names omitted)` |

## What the threads were blocked on during hitches

- window per hitch: [hitch_start - max(pre_ms, magnitude_ms), hitch_end] (pre_ms=50); threads seen: 75
- hitches analysed: 19/19 (a bucket counts when it covers >= 5% of the window)
- main thread off-CPU buckets: S/epoll_wait do_epoll_wait (63%); S/- 0 (16%); S/futex __futex_wait (9%); S/clock_nanosleep hrtimer_nanosleep (4%)

| thread | state | syscall | wchan | hitches | % hitches | coverage | threads |
|---|---|---|---|---|---|---|---|
| AsyncIOService/ | S | futex | __futex_wait | 19 | 100.0% | 100% | 3.0 |
| dota2 | S | futex | __futex_wait | 19 | 100.0% | 100% | 5.0 |
| [vkcf] Analysis | S | futex | __futex_wait | 19 | 100.0% | 100% | 1.0 |
| [vkrt] Analysis | S | futex | __futex_wait | 19 | 100.0% | 100% | 1.0 |
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
| VKRenderThread | S | futex | __futex_wait | 19 | 100.0% | 100% | 8.0 |
| PulseHotplug | S | futex | __futex_wait | 19 | 100.0% | 100% | 1.0 |
| SDLAudioP15 | S | futex | __futex_wait | 19 | 100.0% | 100% | 1.0 |
| [vkps] Update | S | futex | __futex_wait | 19 | 100.0% | 100% | 1.0 |
| PulseMainloop | S | poll | do_sys_poll | 19 | 100.0% | 99% | 1.0 |
| dota2 | S | poll | do_sys_poll | 19 | 100.0% | 97% | 1.0 |
| AudioMixer | S | futex | __futex_wait | 19 | 100.0% | 97% | 1.0 |
| dota2 | S | epoll_wait | do_epoll_wait | 19 | 100.0% | 96% | 1.0 |
| mangohud-nvidia | S | clock_nanosleep | hrtimer_nanosleep | 19 | 100.0% | 88% | 1.0 |
| GlobPool/6 | S | futex | __futex_wait | 19 | 100.0% | 71% | 1.0 |
| GlobPool/2 | S | futex | __futex_wait | 19 | 100.0% | 70% | 1.0 |
| GlobPool/1 | S | futex | __futex_wait | 19 | 100.0% | 70% | 1.0 |
| GlobPool/3 | S | futex | __futex_wait | 19 | 100.0% | 70% | 1.0 |
| GlobPool/5 | S | futex | __futex_wait | 19 | 100.0% | 70% | 1.0 |
| GlobPool/4 | S | futex | __futex_wait | 19 | 100.0% | 69% | 1.0 |

### Per-thread-name CPU (threads_cpu.csv)

| thread | cpu% (mean) | samples | threads |
|---|---|---|---|
| mangohud-nvidia | 1459493.17 | 760 | 1 |
| dota2 | 1030296.51 | 1734 | 6 |
| VKRenderThread | 430774.08 | 1756 | 8 |
| AsyncIOService/ | 360624.34 | 100 | 3 |
| GlobPool/6 | 351944.21 | 709 | 1 |
| GlobPool/0 | 348160.73 | 710 | 1 |
| GlobPool/2 | 347067.18 | 711 | 1 |
| GlobPool/5 | 346123.05 | 711 | 1 |
| GlobPool/1 | 340408.31 | 713 | 1 |
| GlobPool/4 | 340181.98 | 710 | 1 |
| GlobPool/3 | 336707.77 | 710 | 1 |
| AudioMixer | 243600.24 | 141 | 1 |
| SDLAudioP15 | 203538.01 | 87 | 1 |
| PulseHotplug | 188558.35 | 67 | 1 |
| [vkps] Update | 173431.24 | 96 | 1 |


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

