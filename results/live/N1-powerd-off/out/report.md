# Stutter report — live-N1-powerd-off

- run-dir: `/path/to/repo/runs/live-N1-powerd-off`
- window: 6.0 min after warm-up (warm-up source: mark), 47785 frames
- hitch rule: frametime_ms > K * rolling_median(+-W, excl. centre) AND frametime_ms > FLOOR (K=2.5, W=1.0s, FLOOR=13.9 ms, merge<=100 ms)

## Hitches
- **60 hitches** (9.99/min); worst 3569.8 ms; median 91.1 ms
- isolated/sparse hitches (>15 s from any other): 1 (0.17/min)
- low-severity tier: 7 (1.17/min)

## Frametimes
- p50 7.06 ms | p95 9.66 ms | p99 10.67 ms
- 1% low **16.2 fps**, 0.1% low **2.0 fps**, mean 132.6 fps
- frames below 50% of cap: 0.18%

## Data quality
- frametime rows: 58105 kept / 58105 read; **0 rejected** (> 10000 ms / non-positive / non-finite)

## Periodicity
- verdict: **aperiodic** (window 6.0 min, sparse assessable: True)
- steady: period 3.26 s (spectral peak 0.77 s, source interval) +- 0.80 s, p=0.3342, significant=False, fraction explained 0.28
- sparse: period 72.08 s (spectral peak 72.08 s, source spectral) +- 16.74 s, p=0.2693, significant=False, fraction explained 0.33

## Sparse hitches (explicit assessment)
- assessment: **none** (52 severe candidate(s) of 60 primary; severity gate 20.8 ms)
- rate: 8.66/min (95% CI 6.33-10.99, poisson-bootstrap)
- intervals (s): p50 4.1, p90 15.7, CV 0.96

## What moved around hitches
| signal.column | feature | cliff's d | z | p | q | hitch | control |
|---|---|---|---|---|---|---|---|
| sys.intr_per_s | min | -0.79 | -3.26 | 2.55e-25 | 1.3e-23 | 2.19e+04 | 3.73e+04 |
| gpu.power_w | min | -0.79 | -2.27 | 8.81e-25 | 4.1e-23 | 37.1 | 43.8 |
| threads.main_cpu_pct | min | -0.77 | -2.87 | 2.06e-26 | 1.5e-24 | 12 | 31.6 |
| threads.main_cpu_pct | step | +0.77 | 4.10 | 5.54e-24 | 2.4e-22 | 14.9 | -0.28 |
| threads.main_cpu_pct | mean | -0.76 | -1.30 | 2.18e-23 | 7.9e-22 | 33.6 | 41.1 |
| sys.ctxt_per_s | min | -0.76 | -3.26 | 2.87e-23 | 9.8e-22 | 3.24e+04 | 6.02e+04 |
| gpu.power_w | mean | -0.70 | -3.15 | 7.99e-20 | 2.3e-18 | 38.9 | 44.4 |
| sys.intr_per_s | mean | -0.65 | -1.00 | 2.84e-17 | 7.1e-16 | 3.58e+04 | 4.11e+04 |
| threads.proc_cpu_pct | mean | -0.65 | -1.28 | 2.89e-17 | 7.1e-16 | 194 | 215 |
| sys.ctxt_per_s | mean | -0.65 | -0.80 | 2.93e-17 | 7.1e-16 | 5.77e+04 | 6.59e+04 |
| threads.proc_cpu_pct | min | -0.64 | -2.27 | 7.23e-17 | 1.7e-15 | 135 | 176 |
| gpu.temp_c | mean | -0.59 | -1.98 | 1.26e-27 | 1.1e-25 | 76.2 | 76.9 |
| sys.ctxt_per_s | step | +0.59 | 1.83 | 1.74e-14 | 3.9e-13 | 1.73e+04 | -267 |
| gpu.temp_c | min | -0.58 | -2.10 | 1.09e-34 | 1.4e-32 | 75.8 | 76.8 |
| cpu.cpu0_util | step | -0.58 | -1.84 | 2.61e-14 | 5.6e-13 | -25.2 | 1.08 |

## What the threads were blocked on during hitches

- window per hitch: [hitch_start - max(pre_ms, magnitude_ms), hitch_end] (pre_ms=50); threads seen: 92
- hitches analysed: 60/60 (a bucket counts when it covers >= 5% of the window)
- main thread off-CPU buckets: S/futex __futex_wait (64%); S/epoll_wait do_epoll_wait (30%); S/clock_nanosleep hrtimer_nanosleep (5%); S/poll do_sys_poll (1%)

| thread | state | syscall | wchan | hitches | % hitches | coverage | threads |
|---|---|---|---|---|---|---|---|
| dota2 | S | futex | __futex_wait | 60 | 100.0% | 100% | 5.0 |
| [vkcf] Analysis | S | futex | __futex_wait | 60 | 100.0% | 100% | 1.0 |
| [vkrt] Analysis | S | futex | __futex_wait | 60 | 100.0% | 100% | 1.0 |
| Async Pipeline | S | futex | __futex_wait | 60 | 100.0% | 100% | 31.0 |
| VmaDefragThread | S | futex | __futex_wait | 60 | 100.0% | 100% | 1.0 |
| AsyncTextureHoo | S | futex | __futex_wait | 60 | 100.0% | 100% | 1.0 |
| CSteamAudioReve | S | futex | __futex_wait | 60 | 100.0% | 100% | 1.0 |
| CSteamAudioPart | S | futex | __futex_wait | 60 | 100.0% | 100% | 1.0 |
| V8 DefaultWorke | S | futex | __futex_wait | 60 | 100.0% | 100% | 1.0 |
| Panorama Image | S | futex | __futex_wait | 60 | 100.0% | 100% | 1.0 |
| SaveJob/0 | S | futex | __futex_wait | 60 | 100.0% | 100% | 1.0 |
| Video Decode Th | S | futex | __futex_wait | 60 | 100.0% | 100% | 5.0 |
| CFileWriterThre | S | futex | __futex_wait | 60 | 100.0% | 100% | 1.0 |
| SteamEngineWatc | S | futex | __futex_wait | 60 | 100.0% | 100% | 1.0 |
| CJobMgr::m_Work | S | futex | __futex_wait | 60 | 100.0% | 100% | 2.0 |
| CHTTPClientThre | S | futex | __futex_wait | 60 | 100.0% | 100% | 1.0 |
| IPC:CSteamEngin | S | futex | __futex_wait | 60 | 100.0% | 100% | 1.0 |
| CNet Encrypt:0 | S | futex | __futex_wait | 60 | 100.0% | 100% | 1.0 |
| cuda0000a40002a | S | poll | do_sys_poll | 60 | 100.0% | 100% | 1.0 |
| IOCP Thread 0 | S | epoll_wait | do_epoll_wait | 60 | 100.0% | 100% | 1.0 |
| VKRenderThread | S | futex | __futex_wait | 60 | 100.0% | 100% | 8.0 |
| AsyncIOService/ | S | futex | __futex_wait | 60 | 100.0% | 100% | 3.0 |
| dota2 | S | clock_nanosleep | hrtimer_nanosleep | 60 | 100.0% | 100% | 1.1 |
| dota2 | S | epoll_wait | do_epoll_wait | 60 | 100.0% | 100% | 1.0 |
| CHTTPCacheFileT | S | futex | __futex_wait | 60 | 100.0% | 100% | 1.0 |
| IPC:CSteamEngin | S | epoll_wait | do_epoll_wait | 60 | 100.0% | 100% | 1.0 |
| mangohud-hwinfo | S | futex | __futex_wait | 60 | 100.0% | 100% | 1.0 |
| [vkps] Update | S | futex | __futex_wait | 60 | 100.0% | 100% | 1.0 |
| PulseHotplug | S | futex | __futex_wait | 60 | 100.0% | 99% | 1.0 |
| SDLAudioP15 | S | futex | __futex_wait | 60 | 100.0% | 99% | 1.0 |

### Per-thread-name CPU (threads_cpu.csv)

| thread | cpu% (mean) | samples | threads |
|---|---|---|---|
| AsyncTextureHoo | 2673072.18 | 11 | 1 |
| mangohud-nvidia | 2249202.18 | 460 | 1 |
| CHTTPClientThre | 2097152.00 | 1 | 1 |
| dota2 | 1032258.27 | 918 | 6 |
| AsyncIOService/ | 875112.14 | 58 | 3 |
| VKRenderThread | 591961.06 | 1045 | 8 |
| SDLAudioP15 | 482409.36 | 46 | 1 |
| PulseHotplug | 387239.31 | 39 | 1 |
| GlobPool/1 | 339951.55 | 299 | 1 |
| GlobPool/2 | 333227.29 | 300 | 1 |
| GlobPool/3 | 318970.84 | 284 | 1 |
| GlobPool/5 | 316158.12 | 289 | 1 |
| GlobPool/4 | 301564.97 | 291 | 1 |
| mangohud-hwinfo | 294807.26 | 41 | 1 |
| GlobPool/6 | 285665.74 | 279 | 1 |


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

