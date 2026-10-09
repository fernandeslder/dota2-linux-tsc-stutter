# Stutter report — live-AF1-phases

- run-dir: `/path/to/repo/runs/live-AF1-phases`
- window: 8.3 min after warm-up (warm-up source: mark), 68440 frames
- hitch rule: frametime_ms > K * rolling_median(+-W, excl. centre) AND frametime_ms > FLOOR (K=2.5, W=1.0s, FLOOR=13.9 ms, merge<=100 ms)

## Hitches
- **42 hitches** (5.05/min); worst 1677.1 ms; median 95.4 ms
- isolated/sparse hitches (>15 s from any other): 0 (0.00/min)
- low-severity tier: 10 (1.20/min)

## Frametimes
- p50 7.05 ms | p95 9.60 ms | p99 10.57 ms
- 1% low **27.3 fps**, 0.1% low **3.8 fps**, mean 137.3 fps
- frames below 50% of cap: 0.08%

## Data quality
- frametime rows: 79198 kept / 79198 read; **0 rejected** (> 10000 ms / non-positive / non-finite)

## Periodicity
- verdict: **aperiodic** (window 8.3 min, sparse assessable: True)
- steady: period 4.59 s (spectral peak 1.13 s, source interval) +- 0.77 s, p=0.2943, significant=False, fraction explained 0.24
- sparse: period 55.40 s (spectral peak 55.40 s, source spectral) +- 14.96 s, p=0.6534, significant=False, fraction explained 0.33

## Sparse hitches (explicit assessment)
- assessment: **irregular** (39 severe candidate(s) of 42 primary; severity gate 20.8 ms)
- rate: 4.69/min (95% CI 3.25-6.14, poisson-bootstrap)
- intervals (s): p50 5.6, p90 13.6, CV 2.15
- interval mode 40.5 s; modal cluster n=1 cv=0.000 frac=1.00
- CAVEAT: only 1 interval(s) in the [20, 100] s band (<5): regularity cannot be established

## What moved around hitches
| signal.column | feature | cliff's d | z | p | q | hitch | control |
|---|---|---|---|---|---|---|---|
| sys.ctxt_per_s | min | -0.85 | -4.29 | 1.08e-20 | 7.1e-19 | 3.03e+04 | 6.18e+04 |
| gpu.power_w | min | -0.85 | -4.90 | 1.16e-20 | 7.1e-19 | 35.9 | 44.3 |
| sys.intr_per_s | min | -0.82 | -4.91 | 3.86e-19 | 1.9e-17 | 2.06e+04 | 3.76e+04 |
| cpu.cpu0_util | mean | +0.80 | 1.93 | 1.82e-18 | 8.1e-17 | 45.2 | 19.9 |
| sys.ctxt_per_s | step | +0.79 | 1.73 | 3.95e-18 | 1.6e-16 | 1.75e+04 | -102 |
| gpu.power_w | mean | -0.79 | -8.49 | 5.6e-18 | 2.1e-16 | 37.9 | 44.6 |
| sys.intr_per_s | step | +0.79 | 2.12 | 7e-18 | 2.5e-16 | 9.4e+03 | -146 |
| sys.intr_per_s | mean | -0.75 | -1.34 | 1.63e-16 | 5.3e-15 | 3.48e+04 | 4.13e+04 |
| sys.ctxt_per_s | mean | -0.74 | -1.05 | 3.53e-16 | 8.9e-15 | 5.57e+04 | 6.84e+04 |
| gpu.power_w | step | -0.74 | -1.63 | 4.2e-16 | 9.8e-15 | -1.77 | -0.0258 |
| threads.main_cpu_pct | mean | -0.73 | -3.48 | 1.33e-15 | 3e-14 | 33.5 | 40 |
| cpu.cpu0_util | max | +0.72 | 1.55 | 1.89e-15 | 4e-14 | 80.8 | 45.1 |
| threads.main_cpu_pct | min | -0.72 | -4.46 | 1.53e-19 | 8.3e-18 | 13.1 | 30.5 |
| cpu.cpu1_util | mean | -0.70 | -1.32 | 2.03e-14 | 4.1e-13 | 20.2 | 33.5 |
| cpu.cpu0_util | step | -0.69 | -2.14 | 5.13e-14 | 9.7e-13 | -25.6 | 0.795 |

## What the threads were blocked on during hitches

- window per hitch: [hitch_start - max(pre_ms, magnitude_ms), hitch_end] (pre_ms=50); threads seen: 93
- hitches analysed: 42/42 (a bucket counts when it covers >= 5% of the window)
- main thread off-CPU buckets: S/futex __futex_wait (64%); S/epoll_wait do_epoll_wait (24%); S/clock_nanosleep hrtimer_nanosleep (11%); S/- 0 (0%)

| thread | state | syscall | wchan | hitches | % hitches | coverage | threads |
|---|---|---|---|---|---|---|---|
| AsyncIOService/ | S | futex | __futex_wait | 42 | 100.0% | 100% | 3.0 |
| dota2 | S | futex | __futex_wait | 42 | 100.0% | 100% | 5.0 |
| [vkcf] Analysis | S | futex | __futex_wait | 42 | 100.0% | 100% | 1.0 |
| [vkrt] Analysis | S | futex | __futex_wait | 42 | 100.0% | 100% | 1.0 |
| Async Pipeline | S | futex | __futex_wait | 42 | 100.0% | 100% | 31.0 |
| VmaDefragThread | S | futex | __futex_wait | 42 | 100.0% | 100% | 1.0 |
| AsyncTextureHoo | S | futex | __futex_wait | 42 | 100.0% | 100% | 1.0 |
| mangohud-hwinfo | S | futex | __futex_wait | 42 | 100.0% | 100% | 1.0 |
| CSteamAudioReve | S | futex | __futex_wait | 42 | 100.0% | 100% | 1.0 |
| CSteamAudioPart | S | futex | __futex_wait | 42 | 100.0% | 100% | 1.0 |
| V8 DefaultWorke | S | futex | __futex_wait | 42 | 100.0% | 100% | 1.0 |
| Panorama Image | S | futex | __futex_wait | 42 | 100.0% | 100% | 1.0 |
| SaveJob/0 | S | futex | __futex_wait | 42 | 100.0% | 100% | 1.0 |
| Video Decode Th | S | futex | __futex_wait | 42 | 100.0% | 100% | 5.0 |
| CFileWriterThre | S | futex | __futex_wait | 42 | 100.0% | 100% | 1.0 |
| SteamEngineWatc | S | futex | __futex_wait | 42 | 100.0% | 100% | 1.0 |
| CJobMgr::m_Work | S | futex | __futex_wait | 42 | 100.0% | 100% | 2.0 |
| CHTTPClientThre | S | futex | __futex_wait | 42 | 100.0% | 100% | 1.0 |
| CHTTPCacheFileT | S | futex | __futex_wait | 42 | 100.0% | 100% | 1.0 |
| IOCP Thread 0 | S | epoll_wait | do_epoll_wait | 42 | 100.0% | 100% | 1.0 |
| dota2 | S | clock_nanosleep | hrtimer_nanosleep | 42 | 100.0% | 100% | 1.0 |
| cuda0000a40002a | S | poll | do_sys_poll | 42 | 100.0% | 100% | 1.0 |
| COfflineMessage | D | access | read_extent_buffer_pages | 42 | 100.0% | 100% | 1.0 |
| CNet Encrypt:0 | S | futex | __futex_wait | 42 | 100.0% | 100% | 1.0 |
| IPC:CSteamEngin | S | futex | __futex_wait | 42 | 100.0% | 100% | 1.0 |
| PulseHotplug | S | futex | __futex_wait | 42 | 100.0% | 100% | 1.0 |
| IPC:CSteamEngin | S | epoll_wait | do_epoll_wait | 42 | 100.0% | 100% | 1.0 |
| [vkps] Update | S | futex | __futex_wait | 42 | 100.0% | 100% | 1.0 |
| VKRenderThread | S | futex | __futex_wait | 42 | 100.0% | 100% | 8.0 |
| dota2 | S | epoll_wait | do_epoll_wait | 42 | 100.0% | 100% | 1.0 |

### Per-thread-name CPU (threads_cpu.csv)

| thread | cpu% (mean) | samples | threads |
|---|---|---|---|
| mangohud-nvidia | 1969374.06 | 601 | 1 |
| dota2 | 899719.59 | 1214 | 6 |
| CHTTPClientThre | 599186.29 | 1 | 1 |
| VKRenderThread | 519995.21 | 1422 | 8 |
| IPC:CSteamEngin | 383305.91 | 73 | 2 |
| PulseHotplug | 379016.80 | 50 | 1 |
| PulseMainloop | 340470.86 | 149 | 1 |
| GlobPool/0 | 290884.68 | 387 | 1 |
| GlobPool/4 | 289750.32 | 387 | 1 |
| mangohud-hwinfo | 277161.00 | 54 | 1 |
| GlobPool/3 | 275984.29 | 392 | 1 |
| GlobPool/2 | 272387.44 | 400 | 1 |
| AudioMixer | 263229.05 | 98 | 1 |
| GlobPool/5 | 261727.93 | 401 | 1 |
| GlobPool/6 | 260203.66 | 404 | 1 |


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

