# Stutter report — live-C2-nosound

- run-dir: `/path/to/repo/runs/live-C2-nosound`
- window: 6.0 min after warm-up (warm-up source: mark), 49578 frames
- hitch rule: frametime_ms > K * rolling_median(+-W, excl. centre) AND frametime_ms > FLOOR (K=2.5, W=1.0s, FLOOR=13.9 ms, merge<=100 ms)

## Hitches
- **58 hitches** (9.66/min); worst 1439.8 ms; median 94.9 ms
- isolated/sparse hitches (>15 s from any other): 1 (0.17/min)
- low-severity tier: 7 (1.17/min)

## Frametimes
- p50 7.06 ms | p95 9.61 ms | p99 10.63 ms
- 1% low **29.6 fps**, 0.1% low **4.3 fps**, mean 137.7 fps
- frames below 50% of cap: 0.13%

## Data quality
- frametime rows: 60077 kept / 60077 read; **0 rejected** (> 10000 ms / non-positive / non-finite)

## Periodicity
- verdict: **aperiodic** (window 6.0 min, sparse assessable: True)
- steady: period 2.84 s (spectral peak 0.60 s, source interval) +- 0.66 s, p=0.793, significant=False, fraction explained 0.24
- sparse: period 40.01 s (spectral peak 40.01 s, source spectral) +- 11.94 s, p=0.1222, significant=False, fraction explained 0.31

## Sparse hitches (explicit assessment)
- assessment: **irregular** (57 severe candidate(s) of 58 primary; severity gate 20.8 ms)
- rate: 9.50/min (95% CI 7.00-12.00, poisson-bootstrap)
- intervals (s): p50 3.6, p90 13.9, CV 1.08
- interval mode 37.5 s; modal cluster n=1 cv=0.000 frac=1.00
- CAVEAT: only 1 interval(s) in the [20, 100] s band (<5): regularity cannot be established

## What moved around hitches
| signal.column | feature | cliff's d | z | p | q | hitch | control |
|---|---|---|---|---|---|---|---|
| sys.ctxt_per_s | min | -0.87 | -6.89 | 4.65e-29 | 4.9e-27 | 2.43e+04 | 5.87e+04 |
| threads.main_cpu_pct | min | -0.79 | -4.24 | 1.96e-27 | 1.7e-25 | 6.19 | 20.4 |
| sys.intr_per_s | min | -0.78 | -6.87 | 8.11e-24 | 6.1e-22 | 1.79e+04 | 3.63e+04 |
| threads.busiest_tid | mean | +0.70 | 20.00 | 8.73e-173 | 2.7e-170 | 3.82e+06 | 3.82e+06 |
| threads.busiest_tid | max | +0.70 | 20.00 | 1.03e-172 | 2.7e-170 | 3.82e+06 | 3.82e+06 |
| threads.busiest_cpu_pct | max | +0.69 | 5.19 | 2.47e-19 | 1.6e-17 | 88.4 | 61.5 |
| threads.busiest_tid | step | -0.64 | -17.25 | 1.36e-142 | 2.4e-140 | -3.74 | 0.00966 |
| threads.main_cpu_pct | step | +0.63 | 3.89 | 5.15e-16 | 2.7e-14 | 10.4 | 0.163 |
| gpu.power_w | min | -0.62 | -1.81 | 1.95e-15 | 8.9e-14 | 42.1 | 46.1 |
| threads.proc_cpu_pct | min | -0.62 | -1.26 | 2.04e-15 | 8.9e-14 | 110 | 135 |
| threads.main_cpu_pct | mean | -0.62 | -3.34 | 2.4e-15 | 9.7e-14 | 36.2 | 41.4 |
| sys.ctxt_per_s | step | +0.59 | 1.61 | 2.07e-14 | 7.2e-13 | 1.27e+04 | -10.2 |
| cpu.cpu0_util | max | +0.58 | 1.09 | 1.88e-14 | 7e-13 | 92.9 | 72 |
| cpu.cpu0_util | step | -0.57 | -1.51 | 1.41e-13 | 4.6e-12 | -19.1 | -0.157 |
| threads.nthreads_gt50pct | mean | +0.56 | 1.11 | 1.68e-13 | 5.2e-12 | 0.376 | 0.26 |

| log | near hitch | near control | template |
|---|---|---|---|
| journal | 5 | 61 | `HOSTNAME llm-server[#]: <log line>` |
| journal | 5 | 61 | `HOSTNAME llm-server[#]: <log line>` |
| journal | 5 | 61 | `HOSTNAME llm-server[#]: <log line>` |
| journal | 5 | 61 | `HOSTNAME llm-server[#]: <log line>` |
| journal | 5 | 61 | `HOSTNAME llm-server[#]: <log line>` |
| journal | 5 | 61 | `HOSTNAME llm-server[#]: <log line>` |
| journal | 5 | 61 | `HOSTNAME llm-server[#]: <log line>` |
| journal | 4 | 41 | `HOSTNAME llm-server[#]: <log line>` |

## What the threads were blocked on during hitches

- window per hitch: [hitch_start - max(pre_ms, magnitude_ms), hitch_end] (pre_ms=50); threads seen: 90
- hitches analysed: 58/58 (a bucket counts when it covers >= 5% of the window)
- main thread off-CPU buckets: S/futex __futex_wait (40%); S/epoll_wait do_epoll_wait (33%); S/clock_nanosleep hrtimer_nanosleep (25%); S/- 0 (1%)

| thread | state | syscall | wchan | hitches | % hitches | coverage | threads |
|---|---|---|---|---|---|---|---|
| AsyncIOService/ | S | futex | __futex_wait | 58 | 100.0% | 100% | 3.0 |
| dota2 | S | futex | __futex_wait | 58 | 100.0% | 100% | 5.0 |
| [vkcf] Analysis | S | futex | __futex_wait | 58 | 100.0% | 100% | 1.0 |
| [vkrt] Analysis | S | futex | __futex_wait | 58 | 100.0% | 100% | 1.0 |
| Async Pipeline | S | futex | __futex_wait | 58 | 100.0% | 100% | 31.0 |
| VmaDefragThread | S | futex | __futex_wait | 58 | 100.0% | 100% | 1.0 |
| AsyncTextureHoo | S | futex | __futex_wait | 58 | 100.0% | 100% | 1.0 |
| mangohud-hwinfo | S | futex | __futex_wait | 58 | 100.0% | 100% | 1.0 |
| CSteamAudioReve | S | futex | __futex_wait | 58 | 100.0% | 100% | 1.0 |
| CSteamAudioPart | S | futex | __futex_wait | 58 | 100.0% | 100% | 1.0 |
| V8 DefaultWorke | S | futex | __futex_wait | 58 | 100.0% | 100% | 1.0 |
| Panorama Image | S | futex | __futex_wait | 58 | 100.0% | 100% | 1.0 |
| SaveJob/0 | S | futex | __futex_wait | 58 | 100.0% | 100% | 1.0 |
| Video Decode Th | S | futex | __futex_wait | 58 | 100.0% | 100% | 5.0 |
| CFileWriterThre | S | futex | __futex_wait | 58 | 100.0% | 100% | 1.0 |
| SteamEngineWatc | S | futex | __futex_wait | 58 | 100.0% | 100% | 1.0 |
| CJobMgr::m_Work | S | futex | __futex_wait | 58 | 100.0% | 100% | 2.0 |
| IPC:CSteamEngin | S | futex | __futex_wait | 58 | 100.0% | 100% | 1.0 |
| cuda0000a40002a | S | poll | do_sys_poll | 58 | 100.0% | 100% | 1.0 |
| dota2 | S | epoll_wait | do_epoll_wait | 58 | 100.0% | 100% | 2.0 |
| IOCP Thread 0 | S | epoll_wait | do_epoll_wait | 58 | 100.0% | 100% | 1.0 |
| dota2 | S | clock_nanosleep | hrtimer_nanosleep | 58 | 100.0% | 100% | 1.0 |
| CHTTPClientThre | S | futex | __futex_wait | 58 | 100.0% | 100% | 1.0 |
| CHTTPCacheFileT | S | futex | __futex_wait | 58 | 100.0% | 100% | 1.0 |
| IPC:CSteamEngin | S | epoll_wait | do_epoll_wait | 58 | 100.0% | 100% | 1.0 |
| CNet Encrypt:0 | S | futex | __futex_wait | 58 | 100.0% | 100% | 1.0 |
| VKRenderThread | S | futex | __futex_wait | 58 | 100.0% | 99% | 8.0 |
| [vkps] Update | S | futex | __futex_wait | 58 | 100.0% | 99% | 1.0 |
| dota2 | S | poll | do_sys_poll | 58 | 100.0% | 98% | 1.0 |
| mangohud-nvidia | S | clock_nanosleep | hrtimer_nanosleep | 58 | 100.0% | 92% | 1.0 |

### Per-thread-name CPU (threads_cpu.csv)

| thread | cpu% (mean) | samples | threads |
|---|---|---|---|
| mangohud-nvidia | 1224515.67 | 466 | 1 |
| AsyncIOService/ | 1224210.94 | 53 | 3 |
| dota2 | 593087.98 | 939 | 7 |
| AsyncTextureHoo | 525674.10 | 6 | 1 |
| CHTTPClientThre | 524288.00 | 1 | 1 |
| VKRenderThread | 352162.91 | 1128 | 8 |
| Async Pipeline | 330386.98 | 56 | 30 |
| CJobMgr::m_Work | 288205.10 | 2 | 2 |
| mangohud-hwinfo | 268343.40 | 43 | 1 |
| [vkps] Update | 214353.17 | 53 | 1 |
| IPC:CSteamEngin | 206701.17 | 58 | 2 |
| GlobPool/5 | 197143.92 | 309 | 1 |
| GlobPool/1 | 192260.92 | 303 | 1 |
| GlobPool/6 | 184828.47 | 315 | 1 |
| GlobPool/4 | 171727.26 | 303 | 1 |


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

