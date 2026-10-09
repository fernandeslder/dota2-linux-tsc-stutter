# Stutter report — live-FP1

- run-dir: `/path/to/repo/runs/live-FP1`
- window: 6.0 min after warm-up (warm-up source: mark), 38137 frames
- hitch rule: frametime_ms > K * rolling_median(+-W, excl. centre) AND frametime_ms > FLOOR (K=2.5, W=1.0s, FLOOR=13.9 ms, merge<=100 ms)

## Hitches
- **18 hitches** (2.99/min); worst 28.1 ms; median 20.0 ms
- isolated/sparse hitches (>15 s from any other): 1 (0.17/min)
- low-severity tier: 428 (71.21/min)

## Frametimes
- p50 8.21 ms | p95 15.16 ms | p99 16.93 ms
- 1% low **55.0 fps**, 0.1% low **46.2 fps**, mean 105.8 fps
- frames below 50% of cap: 11.69%

## Data quality
- frametime rows: 49389 kept / 49389 read; **0 rejected** (> 10000 ms / non-positive / non-finite)

## Periodicity
- verdict: **aperiodic** (window 6.0 min, sparse assessable: True)
- steady: period 2.63 s (spectral peak 0.57 s, source interval) +- 1.90 s, p=0.9875, significant=False, fraction explained 0.33
- sparse: period 51.51 s (spectral peak 30.05 s, source interval) +- 8.14 s, p=0.02743, significant=False, fraction explained 0.44

## Sparse hitches (explicit assessment)
- assessment: **irregular** (7 severe candidate(s) of 18 primary; severity gate 20.8 ms)
- rate: 1.16/min (95% CI 0.33-2.00, poisson-bootstrap)
- intervals (s): p50 52.5, p90 87.2, CV 0.67
- interval mode 43.5 s; modal cluster n=1 cv=0.000 frac=0.33
- CAVEAT: only 7 sparse candidate(s) (<8): rate/period estimate is uncertain
- CAVEAT: only 3 interval(s) in the [20, 100] s band (<5): regularity cannot be established

## What moved around hitches
| signal.column | feature | cliff's d | z | p | q | hitch | control |
|---|---|---|---|---|---|---|---|
| threads.proc_cpu_pct | mean | -0.47 | -0.76 | 0.000855 | 0.19 | 402 | 429 |
| cpu.cpu_util_avg | min | -0.45 | -0.79 | 0.00135 | 0.19 | 16.1 | 17.1 |
| cpufreq.cpu8_mhz | max | +0.44 | 0.73 | 0.00176 | 0.19 | 4.52e+03 | 4.47e+03 |
| threads.nthreads_gt50pct | mean | -0.42 | -0.53 | 0.00244 | 0.19 | 1.19 | 1.43 |
| cpu.cpu5_util | max | -0.41 | -0.74 | 0.00269 | 0.19 | 36.6 | 43.8 |
| threads.proc_cpu_pct | min | -0.41 | -0.63 | 0.00317 | 0.19 | 365 | 388 |
| threads.proc_cpu_pct | max | -0.40 | -0.61 | 0.00438 | 0.24 | 448 | 470 |
| cpufreq.cpu15_mhz | max | +0.35 | 0.52 | 0.0127 | 0.49 | 4.51e+03 | 4.46e+03 |
| cpufreq.cpu16_mhz | step | -0.34 | -0.62 | 0.0139 | 0.49 | -247 | 58.6 |
| threads.proc_rss_mib | step | +0.34 | 0.47 | 0.015 | 0.49 | 2.02 | -0.14 |
| cpufreq.cpu25_mhz | step | +0.33 | 0.53 | 0.0162 | 0.49 | 608 | -20.4 |
| cpu.cpu2_util | min | -0.32 | -0.49 | 0.0189 | 0.54 | 6.79 | 10.7 |
| gpu.power_w | min | -0.32 | -0.49 | 0.0226 | 0.61 | 50.5 | 55.4 |
| cpufreq.cpu24_mhz | max | +0.31 | 0.27 | 0.0268 | 0.61 | 4.45e+03 | 4.39e+03 |
| cpufreq.cpu13_mhz | max | +0.31 | 0.52 | 0.027 | 0.61 | 4.51e+03 | 4.47e+03 |

## What the threads were blocked on during hitches

- window per hitch: [hitch_start - max(pre_ms, magnitude_ms), hitch_end] (pre_ms=50); threads seen: 75
- hitches analysed: 18/18 (a bucket counts when it covers >= 5% of the window)
- main thread off-CPU buckets: S/epoll_wait do_epoll_wait (55%); S/- 0 (23%); D/ioctl_nv os_acquire_rwlock_read (8%); S/- __futex_wait (8%)

| thread | state | syscall | wchan | hitches | % hitches | coverage | threads |
|---|---|---|---|---|---|---|---|
| dota2 | S | futex | __futex_wait | 18 | 100.0% | 100% | 5.0 |
| [vkcf] Analysis | S | futex | __futex_wait | 18 | 100.0% | 100% | 1.0 |
| [vkrt] Analysis | S | futex | __futex_wait | 18 | 100.0% | 100% | 1.0 |
| Async Pipeline | S | futex | __futex_wait | 18 | 100.0% | 100% | 31.0 |
| VmaDefragThread | S | futex | __futex_wait | 18 | 100.0% | 100% | 1.0 |
| VKRenderThread | S | futex | __futex_wait | 18 | 100.0% | 100% | 8.0 |
| AsyncTextureHoo | S | futex | __futex_wait | 18 | 100.0% | 100% | 1.0 |
| mangohud-hwinfo | S | futex | __futex_wait | 18 | 100.0% | 100% | 1.0 |
| CSteamAudioReve | S | futex | __futex_wait | 18 | 100.0% | 100% | 1.0 |
| CSteamAudioPart | S | futex | __futex_wait | 18 | 100.0% | 100% | 1.0 |
| V8 DefaultWorke | S | futex | __futex_wait | 18 | 100.0% | 100% | 1.0 |
| PulseHotplug | S | futex | __futex_wait | 18 | 100.0% | 100% | 1.0 |
| SDLAudioP15 | S | futex | __futex_wait | 18 | 100.0% | 100% | 1.0 |
| Panorama Image | S | futex | __futex_wait | 18 | 100.0% | 100% | 1.0 |
| SaveJob/0 | S | futex | __futex_wait | 18 | 100.0% | 100% | 1.0 |
| cuda0000a40002a | S | poll | do_sys_poll | 18 | 100.0% | 100% | 1.0 |
| PulseMainloop | S | poll | do_sys_poll | 18 | 100.0% | 100% | 1.0 |
| dota2 | S | clock_nanosleep | hrtimer_nanosleep | 18 | 100.0% | 100% | 1.0 |
| dota2 | S | epoll_wait | do_epoll_wait | 18 | 100.0% | 100% | 1.0 |
| AudioMixer | S | futex | __futex_wait | 18 | 100.0% | 99% | 1.0 |
| [vkps] Update | S | futex | __futex_wait | 18 | 100.0% | 99% | 1.0 |
| AsyncIOService/ | S | futex | __futex_wait | 18 | 100.0% | 99% | 3.0 |
| dota2 | S | poll | do_sys_poll | 18 | 100.0% | 98% | 1.0 |
| mangohud-nvidia | S | clock_nanosleep | hrtimer_nanosleep | 18 | 100.0% | 92% | 1.0 |
| GlobPool/6 | S | futex | __futex_wait | 18 | 100.0% | 70% | 1.0 |
| GlobPool/5 | S | futex | __futex_wait | 18 | 100.0% | 66% | 1.0 |
| GlobPool/1 | S | futex | __futex_wait | 18 | 100.0% | 64% | 1.0 |
| GlobPool/2 | S | futex | __futex_wait | 18 | 100.0% | 62% | 1.0 |
| GlobPool/4 | S | futex | __futex_wait | 18 | 100.0% | 62% | 1.0 |
| GlobPool/3 | S | futex | __futex_wait | 18 | 100.0% | 60% | 1.0 |

### Per-thread-name CPU (threads_cpu.csv)

| thread | cpu% (mean) | samples | threads |
|---|---|---|---|
| AsyncIOService/ | 1708743.99 | 97 | 3 |
| mangohud-nvidia | 1401526.56 | 505 | 1 |
| AsyncTextureHoo | 1065226.44 | 11 | 1 |
| dota2 | 953558.32 | 1165 | 6 |
| Async Pipeline | 545670.91 | 93 | 31 |
| VKRenderThread | 373806.43 | 1085 | 8 |
| GlobPool/0 | 327636.72 | 458 | 1 |
| GlobPool/3 | 323676.58 | 458 | 1 |
| GlobPool/4 | 316014.05 | 458 | 1 |
| GlobPool/1 | 305783.93 | 454 | 1 |
| GlobPool/5 | 304385.82 | 455 | 1 |
| GlobPool/6 | 300321.30 | 453 | 1 |
| GlobPool/2 | 296455.04 | 461 | 1 |
| [vkps] Update | 253028.02 | 62 | 1 |
| PulseHotplug | 228594.34 | 47 | 1 |


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

