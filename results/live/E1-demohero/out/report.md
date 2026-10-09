# Stutter report — live-E1-demohero

- run-dir: `/path/to/repo/runs/live-E1-demohero`
- window: 6.0 min after warm-up (warm-up source: mark), 48155 frames
- hitch rule: frametime_ms > K * rolling_median(+-W, excl. centre) AND frametime_ms > FLOOR (K=2.5, W=1.0s, FLOOR=13.9 ms, merge<=100 ms)

## Hitches
- **82 hitches** (13.65/min); worst 1773.7 ms; median 90.1 ms
- isolated/sparse hitches (>15 s from any other): 0 (0.00/min)
- low-severity tier: 9 (1.50/min)

## Frametimes
- p50 7.06 ms | p95 9.56 ms | p99 10.63 ms
- 1% low **17.8 fps**, 0.1% low **2.3 fps**, mean 133.6 fps
- frames below 50% of cap: 0.19%

## Data quality
- frametime rows: 60506 kept / 60506 read; **0 rejected** (> 10000 ms / non-positive / non-finite)

## Periodicity
- verdict: **aperiodic** (window 6.0 min, sparse assessable: True)
- steady: period 3.35 s (spectral peak 0.52 s, source interval) +- 0.46 s, p=0.3092, significant=False, fraction explained 0.26
- sparse: period 30.03 s (spectral peak 30.03 s, source spectral) +- 18.89 s, p=0.8005, significant=False, fraction explained 0.32

## Sparse hitches (explicit assessment)
- assessment: **none** (79 severe candidate(s) of 82 primary; severity gate 20.8 ms)
- rate: 13.15/min (95% CI 10.32-16.15, poisson-bootstrap)
- intervals (s): p50 3.4, p90 9.4, CV 0.87

## What moved around hitches
| signal.column | feature | cliff's d | z | p | q | hitch | control |
|---|---|---|---|---|---|---|---|
| sys.intr_per_s | min | -0.98 | -6.30 | 2.16e-50 | 2.2e-48 | 1.6e+04 | 3.6e+04 |
| sys.ctxt_per_s | min | -0.97 | -6.53 | 2.83e-50 | 2.4e-48 | 2.21e+04 | 5.96e+04 |
| gpu.power_w | min | -0.79 | -4.93 | 2.35e-33 | 1.3e-31 | 38 | 43.9 |
| sys.intr_per_s | mean | -0.78 | -1.69 | 3.17e-33 | 1.6e-31 | 3.58e+04 | 4.16e+04 |
| cpu.cpu0_util | mean | +0.78 | 2.55 | 6.31e-33 | 2.9e-31 | 44.2 | 27.1 |
| sys.ctxt_per_s | mean | -0.78 | -1.33 | 1.21e-32 | 5.1e-31 | 5.8e+04 | 6.84e+04 |
| cpu.cpu0_util | max | +0.72 | 1.51 | 1.56e-29 | 6.1e-28 | 92.1 | 64.7 |
| gpu.power_w | mean | -0.72 | -4.76 | 5.27e-28 | 1.9e-26 | 39.7 | 44.2 |
| sys.ctxt_per_s | step | +0.70 | 2.16 | 4.03e-27 | 1.2e-25 | 1.86e+04 | -1.01e+03 |
| threads.main_cpu_pct | mean | -0.69 | -3.20 | 2.17e-26 | 6.1e-25 | 33.7 | 40.5 |
| threads.main_cpu_pct | step | +0.69 | 3.48 | 3.07e-26 | 8.2e-25 | 12.5 | -0.218 |
| threads.main_cpu_pct | min | -0.68 | -4.58 | 6.21e-28 | 2.1e-26 | 6.82 | 20 |
| sys.intr_per_s | step | +0.66 | 2.35 | 2.59e-24 | 6.6e-23 | 9.76e+03 | -383 |
| gpu.mem_util | min | -0.65 | -4.98 | 3.2e-94 | 4.1e-92 | 5.27 | 8.9 |
| threads.busiest_tid | max | +0.65 | 3.02 | 2.14e-181 | 1.1e-178 | 3.78e+06 | 3.78e+06 |

| log | near hitch | near control | template |
|---|---|---|---|
| journal | 0 | 17 | `HOSTNAME systemd[#]: Starting Stop the on-demand background stac` |
| journal | 0 | 18 | `HOSTNAME systemd[#]: Finished Stop the on-demand background stac` |
| journal | 0 | 18 | `HOSTNAME systemd[#]: idle-reaper.service: Deactivated ` |

## What the threads were blocked on during hitches

- window per hitch: [hitch_start - max(pre_ms, magnitude_ms), hitch_end] (pre_ms=50); threads seen: 92
- hitches analysed: 82/82 (a bucket counts when it covers >= 5% of the window)
- main thread off-CPU buckets: S/futex __futex_wait (65%); S/epoll_wait do_epoll_wait (26%); S/clock_nanosleep hrtimer_nanosleep (8%); S/- 0 (0%)

| thread | state | syscall | wchan | hitches | % hitches | coverage | threads |
|---|---|---|---|---|---|---|---|
| AsyncIOService/ | S | futex | __futex_wait | 82 | 100.0% | 100% | 3.0 |
| dota2 | S | futex | __futex_wait | 82 | 100.0% | 100% | 5.0 |
| [vkcf] Analysis | S | futex | __futex_wait | 82 | 100.0% | 100% | 1.0 |
| [vkrt] Analysis | S | futex | __futex_wait | 82 | 100.0% | 100% | 1.0 |
| Async Pipeline | S | futex | __futex_wait | 82 | 100.0% | 100% | 31.0 |
| VmaDefragThread | S | futex | __futex_wait | 82 | 100.0% | 100% | 1.0 |
| AsyncTextureHoo | S | futex | __futex_wait | 82 | 100.0% | 100% | 1.0 |
| CSteamAudioReve | S | futex | __futex_wait | 82 | 100.0% | 100% | 1.0 |
| CSteamAudioPart | S | futex | __futex_wait | 82 | 100.0% | 100% | 1.0 |
| V8 DefaultWorke | S | futex | __futex_wait | 82 | 100.0% | 100% | 1.0 |
| Panorama Image | S | futex | __futex_wait | 82 | 100.0% | 100% | 1.0 |
| SaveJob/0 | S | futex | __futex_wait | 82 | 100.0% | 100% | 1.0 |
| Video Decode Th | S | futex | __futex_wait | 82 | 100.0% | 100% | 5.0 |
| CFileWriterThre | S | futex | __futex_wait | 82 | 100.0% | 100% | 1.0 |
| SteamEngineWatc | S | futex | __futex_wait | 82 | 100.0% | 100% | 1.0 |
| CJobMgr::m_Work | S | futex | __futex_wait | 82 | 100.0% | 100% | 2.0 |
| CHTTPClientThre | S | futex | __futex_wait | 82 | 100.0% | 100% | 1.0 |
| IPC:CSteamEngin | S | futex | __futex_wait | 82 | 100.0% | 100% | 1.0 |
| CNet Encrypt:0 | S | futex | __futex_wait | 82 | 100.0% | 100% | 1.0 |
| dota2 | S | clock_nanosleep | hrtimer_nanosleep | 82 | 100.0% | 100% | 1.0 |
| cuda0000a40002a | S | poll | do_sys_poll | 82 | 100.0% | 100% | 1.0 |
| IOCP Thread 0 | S | epoll_wait | do_epoll_wait | 82 | 100.0% | 100% | 1.0 |
| mangohud-hwinfo | S | futex | __futex_wait | 82 | 100.0% | 100% | 1.0 |
| VKRenderThread | S | futex | __futex_wait | 82 | 100.0% | 100% | 8.0 |
| CHTTPCacheFileT | S | futex | __futex_wait | 82 | 100.0% | 100% | 1.0 |
| dota2 | S | epoll_wait | do_epoll_wait | 82 | 100.0% | 100% | 1.0 |
| [vkps] Update | S | futex | __futex_wait | 82 | 100.0% | 100% | 1.0 |
| IPC:CSteamEngin | S | epoll_wait | do_epoll_wait | 82 | 100.0% | 100% | 1.0 |
| SDLAudioP15 | S | futex | __futex_wait | 82 | 100.0% | 99% | 1.0 |
| PulseMainloop | S | poll | do_sys_poll | 82 | 100.0% | 99% | 1.0 |

### Per-thread-name CPU (threads_cpu.csv)

| thread | cpu% (mean) | samples | threads |
|---|---|---|---|
| AsyncIOService/ | 4153364.26 | 55 | 3 |
| AsyncTextureHoo | 2048855.93 | 10 | 1 |
| Async Pipeline | 1442778.42 | 49 | 31 |
| mangohud-nvidia | 1391520.48 | 492 | 1 |
| CNet Encrypt:0 | 838860.80 | 1 | 1 |
| dota2 | 661007.92 | 982 | 6 |
| VKRenderThread | 349844.83 | 1042 | 8 |
| GlobPool/6 | 232955.20 | 304 | 1 |
| IPC:CSteamEngin | 219827.32 | 59 | 2 |
| GlobPool/3 | 205041.95 | 302 | 1 |
| GlobPool/2 | 204295.01 | 308 | 1 |
| GlobPool/5 | 203759.19 | 317 | 1 |
| mangohud-hwinfo | 202944.26 | 43 | 1 |
| GlobPool/1 | 198641.10 | 307 | 1 |
| GlobPool/4 | 189742.01 | 300 | 1 |


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

