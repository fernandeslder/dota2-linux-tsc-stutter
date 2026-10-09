# Stutter report — live-G1-gamescope

- run-dir: `/path/to/repo/runs/live-G1-gamescope`
- window: 6.0 min after warm-up (warm-up source: mark), 49742 frames
- hitch rule: frametime_ms > K * rolling_median(+-W, excl. centre) AND frametime_ms > FLOOR (K=2.5, W=1.0s, FLOOR=13.9 ms, merge<=100 ms)

## Hitches
- **57 hitches** (9.49/min); worst 1665.4 ms; median 64.4 ms
- isolated/sparse hitches (>15 s from any other): 2 (0.33/min)
- low-severity tier: 6 (1.00/min)

## Frametimes
- p50 7.05 ms | p95 9.68 ms | p99 10.67 ms
- 1% low **30.2 fps**, 0.1% low **4.4 fps**, mean 138.0 fps
- frames below 50% of cap: 0.13%

## Data quality
- frametime rows: 61414 kept / 61414 read; **0 rejected** (> 10000 ms / non-positive / non-finite)

## Periodicity
- verdict: **aperiodic** (window 6.0 min, sparse assessable: True)
- steady: period 3.48 s (spectral peak 1.12 s, source interval) +- 0.74 s, p=0.2045, significant=False, fraction explained 0.30
- sparse: period 30.04 s (spectral peak 30.04 s, source spectral) +- 22.89 s, p=0.9451, significant=False, fraction explained 0.30

## Sparse hitches (explicit assessment)
- assessment: **none** (53 severe candidate(s) of 57 primary; severity gate 20.8 ms)
- rate: 8.82/min (95% CI 6.49-11.15, poisson-bootstrap)
- intervals (s): p50 4.8, p90 15.7, CV 0.95

## What moved around hitches
| signal.column | feature | cliff's d | z | p | q | hitch | control |
|---|---|---|---|---|---|---|---|
| sys.ctxt_per_s | min | -0.92 | -6.42 | 5.11e-32 | 6.4e-30 | 3.88e+04 | 6.85e+04 |
| sys.intr_per_s | min | -0.88 | -6.63 | 2.93e-29 | 3e-27 | 2.57e+04 | 4.19e+04 |
| gpu.power_w | min | -0.71 | -6.52 | 1.52e-19 | 1.1e-17 | 40 | 44.5 |
| gpu.power_w | step | -0.68 | -4.59 | 3.86e-18 | 2.4e-16 | -1.93 | 0.0436 |
| threads.main_cpu_pct | mean | -0.68 | -4.01 | 5.54e-18 | 3.1e-16 | 36.2 | 41.9 |
| threads.main_cpu_pct | min | -0.68 | -3.55 | 5.29e-20 | 4.4e-18 | 14.9 | 32.1 |
| sys.ctxt_per_s | mean | -0.67 | -0.96 | 1.65e-17 | 8.3e-16 | 6.61e+04 | 7.37e+04 |
| threads.proc_cpu_pct | min | -0.66 | -2.64 | 3.45e-17 | 1.6e-15 | 142 | 180 |
| sys.intr_per_s | mean | -0.62 | -1.29 | 3.15e-15 | 1.2e-13 | 4.08e+04 | 4.55e+04 |
| sys.ctxt_per_s | step | +0.56 | 1.81 | 6.99e-13 | 1.9e-11 | 1.38e+04 | 51.3 |
| threads.main_cpu_pct | step | +0.56 | 3.75 | 1.39e-12 | 3.5e-11 | 10.1 | 0.0371 |
| sys.intr_per_s | step | +0.53 | 1.93 | 1.14e-11 | 2.6e-10 | 7.87e+03 | 56.8 |
| threads.proc_cpu_pct | mean | -0.52 | -1.65 | 2.33e-11 | 5.1e-10 | 204 | 219 |
| threads.busiest_cpu_pct | min | -0.51 | -2.01 | 3.95e-12 | 9.5e-11 | 22.8 | 32.2 |
| threads.proc_cpu_pct | step | +0.50 | 1.74 | 2.48e-10 | 4.6e-09 | 26.9 | -0.101 |

## What the threads were blocked on during hitches

- window per hitch: [hitch_start - max(pre_ms, magnitude_ms), hitch_end] (pre_ms=50); threads seen: 91
- hitches analysed: 57/57 (a bucket counts when it covers >= 5% of the window)
- main thread off-CPU buckets: S/futex __futex_wait (63%); S/epoll_wait do_epoll_wait (28%); S/clock_nanosleep hrtimer_nanosleep (8%); S/futex 0 (1%)

| thread | state | syscall | wchan | hitches | % hitches | coverage | threads |
|---|---|---|---|---|---|---|---|
| AsyncIOService/ | S | futex | __futex_wait | 57 | 100.0% | 100% | 3.0 |
| dota2 | S | futex | __futex_wait | 57 | 100.0% | 100% | 5.0 |
| [vkcf] Analysis | S | futex | __futex_wait | 57 | 100.0% | 100% | 1.0 |
| [vkrt] Analysis | S | futex | __futex_wait | 57 | 100.0% | 100% | 1.0 |
| Async Pipeline | S | futex | __futex_wait | 57 | 100.0% | 100% | 31.0 |
| VmaDefragThread | S | futex | __futex_wait | 57 | 100.0% | 100% | 1.0 |
| VKRenderThread | S | futex | __futex_wait | 57 | 100.0% | 100% | 8.0 |
| AsyncTextureHoo | S | futex | __futex_wait | 57 | 100.0% | 100% | 1.0 |
| CSteamAudioReve | S | futex | __futex_wait | 57 | 100.0% | 100% | 1.0 |
| CSteamAudioPart | S | futex | __futex_wait | 57 | 100.0% | 100% | 1.0 |
| V8 DefaultWorke | S | futex | __futex_wait | 57 | 100.0% | 100% | 1.0 |
| Panorama Image | S | futex | __futex_wait | 57 | 100.0% | 100% | 1.0 |
| SaveJob/0 | S | futex | __futex_wait | 57 | 100.0% | 100% | 1.0 |
| Video Decode Th | S | futex | __futex_wait | 57 | 100.0% | 100% | 5.0 |
| CFileWriterThre | S | futex | __futex_wait | 57 | 100.0% | 100% | 1.0 |
| SteamEngineWatc | S | futex | __futex_wait | 57 | 100.0% | 100% | 1.0 |
| CJobMgr::m_Work | S | futex | __futex_wait | 57 | 100.0% | 100% | 2.0 |
| CHTTPClientThre | S | futex | __futex_wait | 57 | 100.0% | 100% | 1.0 |
| CHTTPCacheFileT | S | futex | __futex_wait | 57 | 100.0% | 100% | 1.0 |
| CNet Encrypt:0 | S | futex | __futex_wait | 57 | 100.0% | 100% | 1.0 |
| cuda0000a80002b | S | poll | do_sys_poll | 57 | 100.0% | 100% | 1.0 |
| IOCP Thread 0 | S | epoll_wait | do_epoll_wait | 57 | 100.0% | 100% | 1.0 |
| IPC:CSteamEngin | S | futex | __futex_wait | 57 | 100.0% | 100% | 1.0 |
| dota2 | S | clock_nanosleep | hrtimer_nanosleep | 57 | 100.0% | 100% | 1.0 |
| dota2 | S | epoll_wait | do_epoll_wait | 57 | 100.0% | 100% | 1.0 |
| mangohud-hwinfo | S | futex | __futex_wait | 57 | 100.0% | 100% | 1.0 |
| IPC:CSteamEngin | S | epoll_wait | do_epoll_wait | 57 | 100.0% | 100% | 1.0 |
| SDLAudioP15 | S | futex | __futex_wait | 57 | 100.0% | 99% | 1.0 |
| PulseHotplug | S | futex | __futex_wait | 57 | 100.0% | 99% | 1.0 |
| PulseMainloop | S | poll | do_sys_poll | 57 | 100.0% | 99% | 1.0 |

### Per-thread-name CPU (threads_cpu.csv)

| thread | cpu% (mean) | samples | threads |
|---|---|---|---|
| mangohud-nvidia | 1898627.34 | 487 | 1 |
| dota2 | 818317.84 | 968 | 6 |
| AsyncIOService/ | 757319.78 | 54 | 3 |
| CNet Encrypt:0 | 599186.29 | 1 | 1 |
| VKRenderThread | 535211.98 | 1131 | 8 |
| PulseHotplug | 302464.83 | 43 | 1 |
| AudioMixer | 271945.47 | 87 | 1 |
| IPC:CSteamEngin | 263797.19 | 59 | 2 |
| GlobPool/5 | 255885.99 | 313 | 1 |
| GlobPool/1 | 246677.96 | 334 | 1 |
| GlobPool/3 | 246262.66 | 309 | 1 |
| GlobPool/0 | 244497.11 | 315 | 1 |
| GlobPool/2 | 240646.85 | 314 | 1 |
| GlobPool/4 | 234356.39 | 327 | 1 |
| SDLAudioP15 | 218009.94 | 54 | 1 |


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

