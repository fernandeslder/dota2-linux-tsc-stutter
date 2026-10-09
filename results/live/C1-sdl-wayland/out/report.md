# Stutter report — live-C1-sdl-wayland

- run-dir: `/path/to/repo/runs/live-C1-sdl-wayland`
- window: 6.0 min after warm-up (warm-up source: mark), 30413 frames
- hitch rule: frametime_ms > K * rolling_median(+-W, excl. centre) AND frametime_ms > FLOOR (K=2.5, W=1.0s, FLOOR=13.9 ms, merge<=100 ms)

## Hitches
- **223 hitches** (37.15/min); worst 2519.5 ms; median 97.7 ms
- isolated/sparse hitches (>15 s from any other): 0 (0.00/min)
- low-severity tier: 217 (36.15/min)

## Frametimes
- p50 7.94 ms | p95 18.52 ms | p99 22.41 ms
- 1% low **6.0 fps**, 0.1% low **1.2 fps**, mean 84.5 fps
- frames below 50% of cap: 24.40%

## Data quality
- frametime rows: 41048 kept / 41048 read; **0 rejected** (> 10000 ms / non-positive / non-finite)

## Periodicity
- verdict: **aperiodic** (window 6.0 min, sparse assessable: True)
- steady: period 1.53 s (spectral peak 0.82 s, source interval) +- 0.10 s, p=0.7257, significant=False, fraction explained 0.28
- sparse: period 36.01 s (spectral peak 36.01 s, source spectral) +- 20.44 s, p=0.1097, significant=False, fraction explained 0.19

## Sparse hitches (explicit assessment)
- assessment: **none** (213 severe candidate(s) of 223 primary; severity gate 20.8 ms)
- rate: 35.49/min (95% CI 30.66-40.32, poisson-bootstrap)
- intervals (s): p50 1.2, p90 3.9, CV 0.93

## What moved around hitches
| signal.column | feature | cliff's d | z | p | q | hitch | control |
|---|---|---|---|---|---|---|---|
| cpu.cpu0_util | max | +0.75 | 1.51 | 1.89e-81 | 9.9e-79 | 95 | 67.2 |
| sys.ctxt_per_s | min | -0.74 | -1.74 | 2.95e-78 | 7.7e-76 | 2.04e+04 | 4.5e+04 |
| sys.intr_per_s | min | -0.71 | -1.36 | 6.74e-72 | 9.4e-70 | 1.48e+04 | 2.75e+04 |
| cpu.cpu0_util | mean | +0.71 | 1.39 | 7.2e-72 | 9.4e-70 | 46.5 | 29.9 |
| sys.ctxt_per_s | step | +0.55 | 1.83 | 5.44e-44 | 5.7e-42 | 1.14e+04 | -1.23e+03 |
| sys.intr_per_s | step | +0.53 | 2.60 | 1.2e-40 | 1e-38 | 8.05e+03 | -544 |
| cpufreq.cpu6_mhz | mean | -0.53 | -1.56 | 2.61e-40 | 1.8e-38 | 4.35e+03 | 4.61e+03 |
| cpu.cpu0_util | step | -0.53 | -1.62 | 2.8e-40 | 1.8e-38 | -19.5 | 0.147 |
| threads.main_cpu_pct | step | +0.50 | 4.43 | 3.87e-37 | 2.2e-35 | 15.1 | -0.327 |
| threads.busiest_cpu_pct | max | +0.47 | 0.92 | 1.05e-32 | 5e-31 | 96.8 | 68.7 |
| cpufreq.cpu6_mhz | min | -0.43 | -0.85 | 2.79e-27 | 1e-25 | 2.88e+03 | 3.78e+03 |
| cpu.cpu_util_avg | step | +0.42 | 1.95 | 9.11e-27 | 3.2e-25 | 1.99 | -0.112 |
| cpufreq.cpu8_mhz | mean | -0.42 | -0.90 | 1.05e-26 | 3.4e-25 | 4.25e+03 | 4.49e+03 |
| threads.proc_cpu_pct | step | +0.41 | 3.63 | 2.71e-25 | 8.3e-24 | 57.3 | -0.551 |
| cpufreq.cpu10_mhz | mean | -0.40 | -0.95 | 7.61e-24 | 2e-22 | 4.27e+03 | 4.5e+03 |

## What the threads were blocked on during hitches

- window per hitch: [hitch_start - max(pre_ms, magnitude_ms), hitch_end] (pre_ms=50); threads seen: 75
- hitches analysed: 223/223 (a bucket counts when it covers >= 5% of the window)
- main thread off-CPU buckets: S/futex __futex_wait (72%); S/epoll_wait do_epoll_wait (21%); S/clock_nanosleep hrtimer_nanosleep (6%); S/- 0 (0%)

| thread | state | syscall | wchan | hitches | % hitches | coverage | threads |
|---|---|---|---|---|---|---|---|
| dota2 | S | futex | __futex_wait | 223 | 100.0% | 100% | 5.0 |
| [vkcf] Analysis | S | futex | __futex_wait | 223 | 100.0% | 100% | 1.0 |
| [vkrt] Analysis | S | futex | __futex_wait | 223 | 100.0% | 100% | 1.0 |
| Async Pipeline | S | futex | __futex_wait | 223 | 100.0% | 100% | 31.0 |
| VmaDefragThread | S | futex | __futex_wait | 223 | 100.0% | 100% | 1.0 |
| CSteamAudioReve | S | futex | __futex_wait | 223 | 100.0% | 100% | 1.0 |
| CSteamAudioPart | S | futex | __futex_wait | 223 | 100.0% | 100% | 1.0 |
| SaveJob/0 | S | futex | __futex_wait | 223 | 100.0% | 100% | 1.0 |
| cuda0000a40002a | S | poll | do_sys_poll | 223 | 100.0% | 100% | 1.0 |
| dota2 | S | clock_nanosleep | hrtimer_nanosleep | 223 | 100.0% | 100% | 1.0 |
| V8 DefaultWorke | S | futex | __futex_wait | 223 | 100.0% | 100% | 1.0 |
| Panorama Image | S | futex | __futex_wait | 223 | 100.0% | 100% | 1.0 |
| mangohud-hwinfo | S | futex | __futex_wait | 223 | 100.0% | 100% | 1.0 |
| AsyncIOService/ | S | futex | __futex_wait | 223 | 100.0% | 100% | 3.0 |
| VKRenderThread | S | futex | __futex_wait | 223 | 100.0% | 100% | 8.0 |
| AsyncTextureHoo | S | futex | __futex_wait | 223 | 100.0% | 100% | 1.0 |
| [vkps] Update | S | futex | __futex_wait | 223 | 100.0% | 99% | 1.0 |
| PulseHotplug | S | futex | __futex_wait | 223 | 100.0% | 99% | 1.0 |
| dota2 | S | epoll_wait | do_epoll_wait | 223 | 100.0% | 99% | 1.0 |
| SDLAudioP15 | S | futex | __futex_wait | 223 | 100.0% | 99% | 1.0 |
| dota2 | S | poll | do_sys_poll | 223 | 100.0% | 99% | 1.0 |
| PulseMainloop | S | poll | do_sys_poll | 223 | 100.0% | 98% | 1.0 |
| AudioMixer | S | futex | __futex_wait | 223 | 100.0% | 98% | 1.0 |
| mangohud-nvidia | S | clock_nanosleep | hrtimer_nanosleep | 223 | 100.0% | 92% | 1.0 |
| GlobPool/3 | S | futex | __futex_wait | 223 | 100.0% | 81% | 1.0 |
| GlobPool/4 | S | futex | __futex_wait | 223 | 100.0% | 80% | 1.0 |
| GlobPool/2 | S | futex | __futex_wait | 223 | 100.0% | 78% | 1.0 |
| GlobPool/0 | S | futex | __futex_wait | 222 | 99.6% | 79% | 1.0 |
| GlobPool/6 | S | futex | __futex_wait | 222 | 99.6% | 77% | 1.0 |
| GlobPool/5 | S | futex | __futex_wait | 221 | 99.1% | 78% | 1.0 |

### Per-thread-name CPU (threads_cpu.csv)

| thread | cpu% (mean) | samples | threads |
|---|---|---|---|
| mangohud-nvidia | 1692771.08 | 502 | 1 |
| AsyncIOService/ | 1116834.85 | 111 | 3 |
| dota2 | 1029930.20 | 1023 | 6 |
| AsyncTextureHoo | 628244.40 | 16 | 1 |
| VKRenderThread | 433997.16 | 962 | 8 |
| GlobPool/6 | 356535.02 | 349 | 1 |
| GlobPool/0 | 336261.06 | 362 | 1 |
| GlobPool/4 | 335219.94 | 353 | 1 |
| GlobPool/1 | 312295.86 | 345 | 1 |
| GlobPool/5 | 310591.33 | 353 | 1 |
| GlobPool/2 | 303630.51 | 348 | 1 |
| GlobPool/3 | 303194.87 | 347 | 1 |
| [vkps] Update | 239641.83 | 58 | 1 |
| AudioMixer | 229116.02 | 89 | 1 |
| PulseMainloop | 185217.01 | 134 | 1 |


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

