# Stutter report — live-AG1-autogroup

- run-dir: `/path/to/repo/runs/live-AG1-autogroup`
- window: 8.0 min after warm-up (warm-up source: mark), 65874 frames
- hitch rule: frametime_ms > K * rolling_median(+-W, excl. centre) AND frametime_ms > FLOOR (K=2.5, W=1.0s, FLOOR=13.9 ms, merge<=100 ms)

## Hitches
- **56 hitches** (6.99/min); worst 2959.2 ms; median 89.4 ms
- isolated/sparse hitches (>15 s from any other): 1 (0.12/min)
- low-severity tier: 7 (0.87/min)

## Frametimes
- p50 7.04 ms | p95 9.59 ms | p99 10.53 ms
- 1% low **26.9 fps**, 0.1% low **3.7 fps**, mean 137.2 fps
- frames below 50% of cap: 0.10%

## Data quality
- frametime rows: 77125 kept / 77125 read; **0 rejected** (> 10000 ms / non-positive / non-finite)

## Periodicity
- verdict: **aperiodic** (window 8.0 min, sparse assessable: True)
- steady: period 3.13 s (spectral peak 1.18 s, source interval) +- 0.84 s, p=0.2269, significant=False, fraction explained 0.20
- sparse: period 53.38 s (spectral peak 53.38 s, source spectral) +- 9.83 s, p=0.7207, significant=False, fraction explained 0.21

## Sparse hitches (explicit assessment)
- assessment: **irregular** (50 severe candidate(s) of 56 primary; severity gate 20.8 ms)
- rate: 6.25/min (95% CI 4.50-7.99, poisson-bootstrap)
- intervals (s): p50 8.4, p90 20.3, CV 0.85
- interval mode 31.5 s; modal cluster n=2 cv=0.040 frac=1.00
- CAVEAT: only 2 interval(s) in the [20, 100] s band (<5): regularity cannot be established

## What moved around hitches
| signal.column | feature | cliff's d | z | p | q | hitch | control |
|---|---|---|---|---|---|---|---|
| sys.intr_per_s | min | -0.80 | -3.44 | 6.54e-24 | 6.6e-22 | 2.3e+04 | 3.73e+04 |
| gpu.power_w | min | -0.77 | -2.96 | 1.7e-22 | 1.4e-20 | 38.3 | 44.1 |
| sys.ctxt_per_s | min | -0.76 | -3.25 | 7.03e-22 | 5.1e-20 | 3.42e+04 | 6.09e+04 |
| gpu.power_w | mean | -0.70 | -3.40 | 1.32e-18 | 5.2e-17 | 40.5 | 44.4 |
| threads.main_cpu_pct | mean | -0.65 | -1.51 | 1.37e-16 | 4.4e-15 | 33.2 | 39.5 |
| threads.main_cpu_pct | min | -0.62 | -3.29 | 7.34e-20 | 3.1e-18 | 14.3 | 30 |
| sys.ctxt_per_s | mean | -0.61 | -0.66 | 8.11e-15 | 2.3e-13 | 5.95e+04 | 6.7e+04 |
| gpu.power_w | step | -0.60 | -2.53 | 2.97e-14 | 7.9e-13 | -2.14 | -0.0747 |
| threads.proc_cpu_pct | min | -0.57 | -2.15 | 4.08e-13 | 1e-11 | 138 | 170 |
| sys.intr_per_s | mean | -0.57 | -0.85 | 7.52e-13 | 1.8e-11 | 3.65e+04 | 4.07e+04 |
| sys.intr_per_s | step | +0.55 | 2.11 | 2.88e-12 | 6.7e-11 | 9.1e+03 | -177 |
| threads.busiest_cpu_pct | min | -0.55 | -1.67 | 8.48e-16 | 2.5e-14 | 21.6 | 30.7 |
| sys.ctxt_per_s | step | +0.54 | 1.58 | 9.77e-12 | 2.2e-10 | 1.62e+04 | -255 |
| threads.main_cpu_pct | step | +0.54 | 3.66 | 1.06e-11 | 2.2e-10 | 11.6 | -0.112 |
| threads.proc_cpu_pct | mean | -0.51 | -1.31 | 9.68e-11 | 2e-09 | 191 | 207 |

## What the threads were blocked on during hitches

- window per hitch: [hitch_start - max(pre_ms, magnitude_ms), hitch_end] (pre_ms=50); threads seen: 92
- hitches analysed: 56/56 (a bucket counts when it covers >= 5% of the window)
- main thread off-CPU buckets: S/futex __futex_wait (83%); S/epoll_wait do_epoll_wait (13%); S/clock_nanosleep hrtimer_nanosleep (4%); S/- 0 (0%)

| thread | state | syscall | wchan | hitches | % hitches | coverage | threads |
|---|---|---|---|---|---|---|---|
| AsyncIOService/ | S | futex | __futex_wait | 56 | 100.0% | 100% | 3.0 |
| dota2 | S | futex | __futex_wait | 56 | 100.0% | 100% | 5.0 |
| [vkcf] Analysis | S | futex | __futex_wait | 56 | 100.0% | 100% | 1.0 |
| [vkrt] Analysis | S | futex | __futex_wait | 56 | 100.0% | 100% | 1.0 |
| Async Pipeline | S | futex | __futex_wait | 56 | 100.0% | 100% | 31.0 |
| VmaDefragThread | S | futex | __futex_wait | 56 | 100.0% | 100% | 1.0 |
| AsyncTextureHoo | S | futex | __futex_wait | 56 | 100.0% | 100% | 1.0 |
| CSteamAudioReve | S | futex | __futex_wait | 56 | 100.0% | 100% | 1.0 |
| CSteamAudioPart | S | futex | __futex_wait | 56 | 100.0% | 100% | 1.0 |
| V8 DefaultWorke | S | futex | __futex_wait | 56 | 100.0% | 100% | 1.0 |
| Panorama Image | S | futex | __futex_wait | 56 | 100.0% | 100% | 1.0 |
| SaveJob/0 | S | futex | __futex_wait | 56 | 100.0% | 100% | 1.0 |
| Video Decode Th | S | futex | __futex_wait | 56 | 100.0% | 100% | 5.0 |
| CFileWriterThre | S | futex | __futex_wait | 56 | 100.0% | 100% | 1.0 |
| SteamEngineWatc | S | futex | __futex_wait | 56 | 100.0% | 100% | 1.0 |
| CJobMgr::m_Work | S | futex | __futex_wait | 56 | 100.0% | 100% | 2.0 |
| CHTTPCacheFileT | S | futex | __futex_wait | 56 | 100.0% | 100% | 1.0 |
| CNet Encrypt:0 | S | futex | __futex_wait | 56 | 100.0% | 100% | 1.0 |
| IOCP Thread 0 | S | epoll_wait | do_epoll_wait | 56 | 100.0% | 100% | 1.0 |
| cuda0000a40002a | S | poll | do_sys_poll | 56 | 100.0% | 100% | 1.0 |
| IPC:CSteamEngin | S | futex | __futex_wait | 56 | 100.0% | 100% | 1.0 |
| CHTTPClientThre | S | futex | __futex_wait | 56 | 100.0% | 100% | 1.0 |
| mangohud-hwinfo | S | futex | __futex_wait | 56 | 100.0% | 100% | 1.0 |
| dota2 | S | clock_nanosleep | hrtimer_nanosleep | 56 | 100.0% | 100% | 1.0 |
| IPC:CSteamEngin | S | epoll_wait | do_epoll_wait | 56 | 100.0% | 100% | 1.0 |
| dota2 | S | epoll_wait | do_epoll_wait | 56 | 100.0% | 100% | 1.0 |
| SDLAudioP15 | S | futex | __futex_wait | 56 | 100.0% | 100% | 1.0 |
| VKRenderThread | S | futex | __futex_wait | 56 | 100.0% | 100% | 8.0 |
| PulseMainloop | S | poll | do_sys_poll | 56 | 100.0% | 99% | 1.0 |
| AudioMixer | S | futex | __futex_wait | 56 | 100.0% | 99% | 1.0 |

### Per-thread-name CPU (threads_cpu.csv)

| thread | cpu% (mean) | samples | threads |
|---|---|---|---|
| mangohud-nvidia | 1011372.28 | 585 | 1 |
| dota2 | 430569.38 | 1188 | 6 |
| AsyncIOService/ | 303803.63 | 54 | 3 |
| VKRenderThread | 246675.54 | 1360 | 8 |
| CHTTPCacheIniti | 174762.67 | 1 | 1 |
| [vkps] Update | 173410.60 | 72 | 1 |
| CJobMgr::m_Work | 171746.69 | 4 | 2 |
| SDLAudioP15 | 171209.59 | 56 | 1 |
| GlobPool/6 | 160560.67 | 382 | 1 |
| IPC:CSteamEngin | 149644.09 | 76 | 2 |
| AudioMixer | 142356.28 | 101 | 1 |
| GlobPool/1 | 141802.06 | 386 | 1 |
| PulseMainloop | 141267.99 | 143 | 1 |
| GlobPool/4 | 139271.11 | 374 | 1 |
| GlobPool/5 | 139010.87 | 388 | 1 |


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

