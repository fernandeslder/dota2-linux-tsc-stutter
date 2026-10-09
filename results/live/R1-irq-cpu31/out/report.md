# Stutter report — live-R1-irq-cpu31

- run-dir: `/path/to/repo/runs/live-R1-irq-cpu31`
- window: 6.0 min after warm-up (warm-up source: mark), 34766 frames
- hitch rule: frametime_ms > K * rolling_median(+-W, excl. centre) AND frametime_ms > FLOOR (K=2.5, W=1.0s, FLOOR=13.9 ms, merge<=100 ms)

## Hitches
- **101 hitches** (16.83/min); worst 2958.7 ms; median 66.7 ms
- isolated/sparse hitches (>15 s from any other): 0 (0.00/min)
- low-severity tier: 256 (42.65/min)

## Frametimes
- p50 8.33 ms | p95 15.29 ms | p99 18.07 ms
- 1% low **9.9 fps**, 0.1% low **1.3 fps**, mean 96.5 fps
- frames below 50% of cap: 10.92%

## Data quality
- frametime rows: 46348 kept / 46348 read; **0 rejected** (> 10000 ms / non-positive / non-finite)

## Periodicity
- verdict: **aperiodic** (window 6.0 min, sparse assessable: True)
- steady: period 2.47 s (spectral peak 1.53 s, source interval) +- 0.36 s, p=0.6758, significant=False, fraction explained 0.22
- sparse: period 30.03 s (spectral peak 30.03 s, source spectral) +- 16.14 s, p=0.399, significant=False, fraction explained 0.23

## Sparse hitches (explicit assessment)
- assessment: **none** (96 severe candidate(s) of 101 primary; severity gate 20.8 ms)
- rate: 15.99/min (95% CI 12.82-19.15, poisson-bootstrap)
- intervals (s): p50 2.4, p90 9.4, CV 1.12

## What moved around hitches
| signal.column | feature | cliff's d | z | p | q | hitch | control |
|---|---|---|---|---|---|---|---|
| threads.proc_cpu_pct | min | -0.85 | -3.14 | 9.81e-48 | 1.3e-45 | 216 | 396 |
| cpu.cpu_util_avg | min | -0.82 | -2.77 | 9.15e-44 | 9.5e-42 | 11.9 | 17.3 |
| sys.intr_per_s | min | -0.75 | -2.77 | 1.29e-37 | 1.1e-35 | 2.27e+04 | 3.62e+04 |
| threads.main_cpu_pct | min | -0.71 | -3.35 | 1.13e-33 | 8.4e-32 | 32.7 | 72.4 |
| threads.proc_cpu_pct | mean | -0.71 | -1.58 | 1.84e-33 | 1.2e-31 | 371 | 441 |
| threads.main_cpu_pct | mean | -0.68 | -1.49 | 1.06e-30 | 5e-29 | 69.3 | 81.6 |
| sys.ctxt_per_s | min | -0.68 | -2.54 | 1.35e-30 | 5.8e-29 | 3.37e+04 | 5.64e+04 |
| threads.busiest_cpu_pct | min | -0.66 | -3.91 | 4.81e-29 | 1.9e-27 | 47.6 | 73.6 |
| gpu.gpu_util | min | -0.62 | -2.48 | 2.33e-26 | 8e-25 | 23.1 | 35.7 |
| cpu.cpu0_util | max | +0.61 | 1.36 | 3.6e-25 | 1.2e-23 | 82.7 | 60.7 |
| cpu.cpu_util_avg | mean | -0.61 | -1.33 | 8.29e-25 | 2.5e-23 | 17.4 | 19.5 |
| gpu.mem_util | min | -0.58 | -2.27 | 1.09e-26 | 4e-25 | 5.48 | 8.13 |
| gpu.gpu_util | mean | -0.57 | -2.29 | 5.01e-22 | 1.4e-20 | 30.5 | 37.7 |
| threads.proc_cpu_pct | step | +0.54 | 2.25 | 5.04e-20 | 1.3e-18 | 80.3 | -4.11 |
| gpu.temp_c | min | -0.53 | -1.05 | 6.48e-21 | 1.8e-19 | 78.9 | 80.2 |

## What the threads were blocked on during hitches

- window per hitch: [hitch_start - max(pre_ms, magnitude_ms), hitch_end] (pre_ms=50); threads seen: 75
- hitches analysed: 101/101 (a bucket counts when it covers >= 5% of the window)
- main thread off-CPU buckets: S/futex __futex_wait (69%); S/epoll_wait do_epoll_wait (30%); S/- 0 (0%); S/poll do_sys_poll (0%)

| thread | state | syscall | wchan | hitches | % hitches | coverage | threads |
|---|---|---|---|---|---|---|---|
| dota2 | S | futex | __futex_wait | 101 | 100.0% | 100% | 5.0 |
| [vkrt] Analysis | S | futex | __futex_wait | 101 | 100.0% | 100% | 1.0 |
| Async Pipeline | S | futex | __futex_wait | 101 | 100.0% | 100% | 31.0 |
| VmaDefragThread | S | futex | __futex_wait | 101 | 100.0% | 100% | 1.0 |
| CSteamAudioReve | S | futex | __futex_wait | 101 | 100.0% | 100% | 1.0 |
| CSteamAudioPart | S | futex | __futex_wait | 101 | 100.0% | 100% | 1.0 |
| V8 DefaultWorke | S | futex | __futex_wait | 101 | 100.0% | 100% | 1.0 |
| Panorama Image | S | futex | __futex_wait | 101 | 100.0% | 100% | 1.0 |
| SaveJob/0 | S | futex | __futex_wait | 101 | 100.0% | 100% | 1.0 |
| cuda0000a40002a | S | poll | do_sys_poll | 101 | 100.0% | 100% | 1.0 |
| dota2 | S | clock_nanosleep | hrtimer_nanosleep | 101 | 100.0% | 100% | 1.0 |
| AsyncTextureHoo | S | futex | __futex_wait | 101 | 100.0% | 100% | 1.0 |
| AsyncIOService/ | S | futex | __futex_wait | 101 | 100.0% | 100% | 3.0 |
| [vkcf] Analysis | S | futex | __futex_wait | 101 | 100.0% | 100% | 1.0 |
| mangohud-hwinfo | S | futex | __futex_wait | 101 | 100.0% | 100% | 1.0 |
| PulseHotplug | S | futex | __futex_wait | 101 | 100.0% | 100% | 1.0 |
| VKRenderThread | S | futex | __futex_wait | 101 | 100.0% | 100% | 8.0 |
| SDLAudioP15 | S | futex | __futex_wait | 101 | 100.0% | 99% | 1.0 |
| PulseMainloop | S | poll | do_sys_poll | 101 | 100.0% | 99% | 1.0 |
| [vkps] Update | S | futex | __futex_wait | 101 | 100.0% | 99% | 1.0 |
| dota2 | S | epoll_wait | do_epoll_wait | 101 | 100.0% | 99% | 1.0 |
| AudioMixer | S | futex | __futex_wait | 101 | 100.0% | 98% | 1.0 |
| dota2 | S | poll | do_sys_poll | 101 | 100.0% | 98% | 1.0 |
| mangohud-nvidia | S | clock_nanosleep | hrtimer_nanosleep | 101 | 100.0% | 93% | 1.0 |
| GlobPool/0 | S | futex | __futex_wait | 101 | 100.0% | 76% | 1.0 |
| GlobPool/1 | S | futex | __futex_wait | 101 | 100.0% | 76% | 1.0 |
| GlobPool/6 | S | futex | __futex_wait | 101 | 100.0% | 74% | 1.0 |
| GlobPool/4 | S | futex | __futex_wait | 100 | 99.0% | 78% | 1.0 |
| GlobPool/5 | S | futex | __futex_wait | 100 | 99.0% | 78% | 1.0 |
| GlobPool/3 | S | futex | __futex_wait | 100 | 99.0% | 74% | 1.0 |

### Per-thread-name CPU (threads_cpu.csv)

| thread | cpu% (mean) | samples | threads |
|---|---|---|---|
| AsyncIOService/ | 1535460.56 | 103 | 3 |
| mangohud-nvidia | 1410293.74 | 504 | 1 |
| dota2 | 998760.05 | 1133 | 6 |
| AsyncTextureHoo | 688267.74 | 11 | 1 |
| VKRenderThread | 404757.28 | 1058 | 8 |
| GlobPool/1 | 343805.79 | 433 | 1 |
| GlobPool/3 | 340942.55 | 435 | 1 |
| GlobPool/0 | 327531.84 | 433 | 1 |
| GlobPool/5 | 324950.49 | 436 | 1 |
| GlobPool/4 | 311467.29 | 437 | 1 |
| GlobPool/2 | 310135.36 | 442 | 1 |
| GlobPool/6 | 307164.34 | 445 | 1 |
| SDLAudioP15 | 209984.81 | 58 | 1 |
| mangohud-hwinfo | 206230.58 | 48 | 1 |
| Async Pipeline | 173141.51 | 91 | 31 |


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

