# Stutter report — live-H1b-threads-unset

- run-dir: `/path/to/repo/runs/live-H1b-threads-unset`
- window: 6.1 min after warm-up (warm-up source: mark), 52333 frames
- hitch rule: frametime_ms > K * rolling_median(+-W, excl. centre) AND frametime_ms > FLOOR (K=2.5, W=1.0s, FLOOR=13.9 ms, merge<=100 ms)

## Hitches
- **16 hitches** (2.60/min); worst 53.2 ms; median 45.8 ms
- isolated/sparse hitches (>15 s from any other): 1 (0.16/min)
- low-severity tier: 3 (0.49/min)

## Frametimes
- p50 7.04 ms | p95 9.67 ms | p99 10.68 ms
- 1% low **80.9 fps**, 0.1% low **43.5 fps**, mean 141.9 fps
- frames below 50% of cap: 0.05%

## Data quality
- frametime rows: 61330 kept / 61330 read; **0 rejected** (> 10000 ms / non-positive / non-finite)

## Periodicity
- verdict: **sparse** (window 6.0 min, sparse assessable: True)
- steady: period 4.56 s (spectral peak 4.56 s, source spectral) +- 2.21 s, p=0.02743, significant=False, fraction explained 0.38
- sparse: period 45.01 s (spectral peak 45.01 s, source spectral) +- 0.09 s, p=0.002494, significant=True, fraction explained 0.88

## Sparse hitches (explicit assessment)
- assessment: **irregular** (16 severe candidate(s) of 16 primary; severity gate 20.8 ms)
- rate: 2.67/min (95% CI 1.50-4.00, poisson-bootstrap)
- intervals (s): p50 0.3, p90 1.9, CV 3.50
- interval mode 88.5 s; modal cluster n=1 cv=0.000 frac=1.00
- CAVEAT: only 1 interval(s) in the [20, 100] s band (<5): regularity cannot be established

## What moved around hitches
| signal.column | feature | cliff's d | z | p | q | hitch | control |
|---|---|---|---|---|---|---|---|
| gpu.video_clock_mhz | min | +0.90 | 3.91 | 1.57e-11 | 1.2e-09 | 1.63e+03 | 1.39e+03 |
| gpu.sm_clock_mhz | min | +0.89 | 3.68 | 3.96e-10 | 2e-08 | 1.65e+03 | 1.45e+03 |
| gpu.graphics_clock_mhz | min | +0.89 | 3.68 | 3.96e-10 | 2e-08 | 1.65e+03 | 1.45e+03 |
| sys.psi_mem_full_avg10 | min | +0.89 | 1.18 | 1.44e-16 | 7.4e-14 | 0.129 | 0.0251 |
| sys.psi_mem_full_avg10 | mean | +0.89 | 1.20 | 8.63e-16 | 1.9e-13 | 0.137 | 0.0267 |
| gpu.power_w | min | +0.88 | 5.05 | 2.38e-09 | 8.2e-08 | 48.7 | 44.6 |
| gpu.power_w | mean | +0.88 | 3.97 | 3.03e-09 | 9.8e-08 | 48.9 | 44.8 |
| sys.psi_mem_full_avg10 | max | +0.88 | 1.15 | 1.62e-15 | 2.1e-13 | 0.144 | 0.0293 |
| gpu.gpu_util | max | -0.88 | -2.76 | 8.38e-10 | 3.3e-08 | 35.6 | 39.6 |
| gpu.gpu_util | mean | -0.87 | -2.11 | 4.25e-09 | 1.2e-07 | 35.2 | 38.7 |
| gpu.gpu_util | min | -0.87 | -1.35 | 5.02e-10 | 2.4e-08 | 34.6 | 37.9 |
| sys.forks_per_s | mean | -0.87 | -0.60 | 4.63e-09 | 1.2e-07 | 1.12 | 20.7 |
| gpu.video_clock_mhz | mean | +0.87 | 3.37 | 1.01e-09 | 3.7e-08 | 1.63e+03 | 1.4e+03 |
| sys.psi_mem_some_avg10 | min | +0.87 | 0.86 | 1.09e-15 | 1.9e-13 | 0.134 | 0.0333 |
| sys.psi_mem_some_avg10 | mean | +0.86 | 0.87 | 1.64e-14 | 1.7e-12 | 0.142 | 0.0353 |

## What the threads were blocked on during hitches

- window per hitch: [hitch_start - max(pre_ms, magnitude_ms), hitch_end] (pre_ms=50); threads seen: 100
- hitches analysed: 16/16 (a bucket counts when it covers >= 5% of the window)
- main thread off-CPU buckets: S/clock_nanosleep hrtimer_nanosleep (71%); S/epoll_wait do_epoll_wait (23%); S/- 0 (4%); S/- hrtimer_nanosleep (2%)

| thread | state | syscall | wchan | hitches | % hitches | coverage | threads |
|---|---|---|---|---|---|---|---|
| dota2 | S | clock_nanosleep | hrtimer_nanosleep | 16 | 100.0% | 100% | 1.0 |
| dota2 | S | epoll_wait | do_epoll_wait | 16 | 100.0% | 100% | 1.0 |
| IOCP Thread 0 | S | epoll_wait | do_epoll_wait | 16 | 100.0% | 100% | 1.0 |
| AsyncIOService/ | S | futex | __futex_wait | 16 | 100.0% | 100% | 3.0 |
| dota2 | S | futex | __futex_wait | 16 | 100.0% | 100% | 5.0 |
| [vkcf] Analysis | S | futex | __futex_wait | 16 | 100.0% | 100% | 1.0 |
| [vkrt] Analysis | S | futex | __futex_wait | 16 | 100.0% | 100% | 1.0 |
| [vkps] Update | S | futex | __futex_wait | 16 | 100.0% | 100% | 1.0 |
| Async Pipeline | S | futex | __futex_wait | 16 | 100.0% | 100% | 31.0 |
| VmaDefragThread | S | futex | __futex_wait | 16 | 100.0% | 100% | 1.0 |
| VKRenderThread | S | futex | __futex_wait | 16 | 100.0% | 100% | 8.0 |
| AsyncTextureHoo | S | futex | __futex_wait | 16 | 100.0% | 100% | 1.0 |
| mangohud-hwinfo | S | futex | __futex_wait | 16 | 100.0% | 100% | 1.0 |
| CSteamAudioReve | S | futex | __futex_wait | 16 | 100.0% | 100% | 1.0 |
| CSteamAudioPart | S | futex | __futex_wait | 16 | 100.0% | 100% | 1.0 |
| V8 DefaultWorke | S | futex | __futex_wait | 16 | 100.0% | 100% | 1.0 |
| Panorama Image | S | futex | __futex_wait | 16 | 100.0% | 100% | 1.0 |
| SaveJob/0 | S | futex | __futex_wait | 16 | 100.0% | 100% | 1.0 |
| Video Decode Th | S | futex | __futex_wait | 16 | 100.0% | 100% | 5.0 |
| CFileWriterThre | S | futex | __futex_wait | 16 | 100.0% | 100% | 1.0 |
| SteamEngineWatc | S | futex | __futex_wait | 16 | 100.0% | 100% | 1.0 |
| CJobMgr::m_Work | S | futex | __futex_wait | 16 | 100.0% | 100% | 2.0 |
| CHTTPCacheFileT | S | futex | __futex_wait | 16 | 100.0% | 100% | 1.0 |
| CHTTPClientThre | S | futex | __futex_wait | 16 | 100.0% | 100% | 1.0 |
| IPC:CSteamEngin | S | futex | __futex_wait | 16 | 100.0% | 100% | 1.0 |
| CNet Encrypt:0 | S | futex | __futex_wait | 16 | 100.0% | 100% | 1.0 |
| cuda0000a40002a | S | poll | do_sys_poll | 16 | 100.0% | 100% | 1.0 |
| IPC:CSteamEngin | S | epoll_wait | do_epoll_wait | 16 | 100.0% | 99% | 1.0 |
| PulseHotplug | S | futex | __futex_wait | 16 | 100.0% | 98% | 1.0 |
| SDLAudioP15 | S | futex | __futex_wait | 16 | 100.0% | 98% | 1.0 |

### Per-thread-name CPU (threads_cpu.csv)

| thread | cpu% (mean) | samples | threads |
|---|---|---|---|
| AsyncIOService/ | 2400115.06 | 53 | 3 |
| mangohud-nvidia | 2252511.30 | 458 | 1 |
| dota2 | 1046790.73 | 925 | 6 |
| AsyncTextureHoo | 780850.36 | 9 | 1 |
| CHTTPCacheIniti | 571950.55 | 1 | 1 |
| VKRenderThread | 549858.29 | 1136 | 8 |
| PulseHotplug | 409870.59 | 35 | 1 |
| CJobMgr::m_Work | 405482.74 | 3 | 2 |
| GlobPool/5 | 328302.57 | 282 | 1 |
| GlobPool/12 | 321427.88 | 279 | 1 |
| GlobPool/0 | 300590.86 | 275 | 1 |
| GlobPool/10 | 299680.52 | 281 | 1 |
| mangohud-hwinfo | 297977.94 | 44 | 1 |
| GlobPool/8 | 297505.01 | 271 | 1 |
| GlobPool/2 | 292091.84 | 286 | 1 |


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

