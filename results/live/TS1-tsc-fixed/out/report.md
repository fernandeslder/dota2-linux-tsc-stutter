# Stutter report — live-TS1-tsc-fixed

- run-dir: `/path/to/repo/runs/live-TS1-tsc-fixed`
- window: 6.0 min after warm-up (warm-up source: mark), 43317 frames
- hitch rule: frametime_ms > K * rolling_median(+-W, excl. centre) AND frametime_ms > FLOOR (K=2.5, W=1.0s, FLOOR=13.9 ms, merge<=100 ms)

## Hitches
- **11 hitches** (1.83/min); worst 32.8 ms; median 20.4 ms
- isolated/sparse hitches (>15 s from any other): 5 (0.83/min)
- low-severity tier: 268 (44.62/min)

## Frametimes
- p50 7.32 ms | p95 13.19 ms | p99 14.50 ms
- 1% low **64.7 fps**, 0.1% low **53.9 fps**, mean 120.2 fps
- frames below 50% of cap: 2.21%

## Data quality
- frametime rows: 57510 kept / 57510 read; **0 rejected** (> 10000 ms / non-positive / non-finite)

## Periodicity
- verdict: **aperiodic** (window 6.0 min, sparse assessable: True)
- steady: period 5.72 s (spectral peak 0.52 s, source interval) +- 2.54 s, p=0.4239, significant=False, fraction explained 0.36
- sparse: period 72.08 s (spectral peak 72.08 s, source spectral) +- 16.54 s, p=0.6185, significant=False, fraction explained 0.18

## Sparse hitches (explicit assessment)
- assessment: **none** (4 severe candidate(s) of 11 primary; severity gate 20.8 ms)
- rate: 0.67/min (95% CI 0.17-1.33, poisson-bootstrap)
- intervals (s): p50 146.7, p90 150.0, CV 0.69
- CAVEAT: only 4 sparse candidate(s) (<8): rate/period estimate is uncertain

## What moved around hitches
| signal.column | feature | cliff's d | z | p | q | hitch | control |
|---|---|---|---|---|---|---|---|
| sys.ctxt_per_s | min | -0.62 | -0.94 | 0.000558 | 0.14 | 6.45e+04 | 6.9e+04 |
| gpu.gpu_util | step | -0.61 | -1.20 | 0.000647 | 0.14 | -1.98 | -0.0686 |
| sys.load1 | min | -0.60 | -1.29 | 0.000855 | 0.14 | 4.93 | 5.54 |
| sys.load5 | min | -0.56 | -1.00 | 0.00159 | 0.14 | 4.96 | 5.09 |
| mem.mem_slab_mib | step | -0.56 | -0.78 | 0.00165 | 0.14 | -0.107 | 0.0171 |
| sys.procs_running | max | +0.55 | 1.19 | 0.00171 | 0.14 | 14.6 | 12.2 |
| sys.load1 | mean | -0.54 | -1.17 | 0.00255 | 0.15 | 5 | 5.57 |
| gpu.mem_util | step | -0.54 | -1.16 | 0.00204 | 0.14 | -0.627 | -0.0245 |
| cpufreq.cpu26_mhz | min | +0.50 | 0.68 | 0.00459 | 0.22 | 4.07e+03 | 3.37e+03 |
| sys.load1 | max | -0.50 | -1.10 | 0.00493 | 0.22 | 5.05 | 5.58 |
| cpufreq.cpu26_mhz | mean | +0.49 | 0.68 | 0.00607 | 0.22 | 4.23e+03 | 3.99e+03 |
| sys.load5 | mean | -0.49 | -0.92 | 0.00626 | 0.22 | 4.98 | 5.09 |
| cpu.cpu5_util | max | +0.48 | 0.81 | 0.00625 | 0.22 | 47.7 | 41.2 |
| cpu.cpu27_util | step | +0.48 | 0.82 | 0.00789 | 0.25 | 3.65 | -0.107 |
| cpufreq.cpu26_mhz | max | +0.47 | 0.57 | 0.00906 | 0.27 | 4.38e+03 | 4.33e+03 |

## What the threads were blocked on during hitches

- window per hitch: [hitch_start - max(pre_ms, magnitude_ms), hitch_end] (pre_ms=50); threads seen: 76
- hitches analysed: 11/11 (a bucket counts when it covers >= 5% of the window)
- main thread off-CPU buckets: S/epoll_wait do_epoll_wait (64%); S/futex __futex_wait (16%); S/- 0 (10%); S/- hrtimer_nanosleep (5%)

| thread | state | syscall | wchan | hitches | % hitches | coverage | threads |
|---|---|---|---|---|---|---|---|
| dota2 | S | clock_nanosleep | hrtimer_nanosleep | 11 | 100.0% | 100% | 1.0 |
| dota2 | S | futex | __futex_wait | 11 | 100.0% | 100% | 5.0 |
| [vkcf] Analysis | S | futex | __futex_wait | 11 | 100.0% | 100% | 1.0 |
| [vkrt] Analysis | S | futex | __futex_wait | 11 | 100.0% | 100% | 1.0 |
| Async Pipeline | S | futex | __futex_wait | 11 | 100.0% | 100% | 31.0 |
| VmaDefragThread | S | futex | __futex_wait | 11 | 100.0% | 100% | 1.0 |
| AsyncTextureHoo | S | futex | __futex_wait | 11 | 100.0% | 100% | 1.0 |
| mangohud-hwinfo | S | futex | __futex_wait | 11 | 100.0% | 100% | 1.0 |
| CSteamAudioReve | S | futex | __futex_wait | 11 | 100.0% | 100% | 1.0 |
| CSteamAudioPart | S | futex | __futex_wait | 11 | 100.0% | 100% | 1.0 |
| V8 DefaultWorke | S | futex | __futex_wait | 11 | 100.0% | 100% | 1.0 |
| PulseHotplug | S | futex | __futex_wait | 11 | 100.0% | 100% | 1.0 |
| SDLAudioP15 | S | futex | __futex_wait | 11 | 100.0% | 100% | 1.0 |
| Panorama Image | S | futex | __futex_wait | 11 | 100.0% | 100% | 1.0 |
| SaveJob/0 | S | futex | __futex_wait | 11 | 100.0% | 100% | 1.0 |
| AudioMixer | S | futex | __futex_wait | 11 | 100.0% | 100% | 1.0 |
| cuda0000a40002a | S | poll | do_sys_poll | 11 | 100.0% | 100% | 1.0 |
| dota2 | S | poll | do_sys_poll | 11 | 100.0% | 100% | 1.0 |
| dota2 | S | epoll_wait | do_epoll_wait | 11 | 100.0% | 100% | 2.0 |
| PulseMainloop | S | poll | do_sys_poll | 11 | 100.0% | 99% | 1.0 |
| VKRenderThread | S | futex | __futex_wait | 11 | 100.0% | 99% | 8.0 |
| AsyncIOService/ | S | futex | __futex_wait | 11 | 100.0% | 99% | 3.0 |
| [vkps] Update | S | futex | __futex_wait | 11 | 100.0% | 98% | 1.0 |
| mangohud-nvidia | S | clock_nanosleep | hrtimer_nanosleep | 11 | 100.0% | 90% | 1.0 |
| GlobPool/5 | S | futex | __futex_wait | 11 | 100.0% | 59% | 1.0 |
| GlobPool/6 | S | futex | __futex_wait | 11 | 100.0% | 57% | 1.0 |
| GlobPool/0 | S | futex | __futex_wait | 11 | 100.0% | 56% | 1.0 |
| GlobPool/3 | S | futex | __futex_wait | 11 | 100.0% | 55% | 1.0 |
| GlobPool/2 | S | futex | __futex_wait | 11 | 100.0% | 53% | 1.0 |
| GlobPool/4 | S | futex | __futex_wait | 11 | 100.0% | 53% | 1.0 |

### Per-thread-name CPU (threads_cpu.csv)

| thread | cpu% (mean) | samples | threads |
|---|---|---|---|
| AsyncIOService/ | 1036007.07 | 92 | 3 |
| mangohud-nvidia | 913619.50 | 495 | 1 |
| AsyncTextureHoo | 703090.64 | 13 | 1 |
| dota2 | 613428.17 | 1178 | 7 |
| VKRenderThread | 268384.57 | 1185 | 8 |
| GlobPool/1 | 226662.59 | 461 | 1 |
| GlobPool/5 | 220386.64 | 454 | 1 |
| GlobPool/6 | 219719.78 | 457 | 1 |
| GlobPool/4 | 218351.27 | 454 | 1 |
| GlobPool/2 | 218209.83 | 456 | 1 |
| GlobPool/3 | 216681.43 | 457 | 1 |
| GlobPool/0 | 210003.77 | 456 | 1 |
| SDLAudioP15 | 159363.45 | 53 | 1 |
| mangohud-hwinfo | 133248.37 | 50 | 1 |
| PulseMainloop | 106412.64 | 130 | 1 |


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

