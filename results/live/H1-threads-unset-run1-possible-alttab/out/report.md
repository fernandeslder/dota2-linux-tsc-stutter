# Stutter report — live-H1-threads-unset

- run-dir: `/path/to/repo/runs/live-H1-threads-unset`
- window: 6.0 min after warm-up (warm-up source: mark), 49254 frames
- hitch rule: frametime_ms > K * rolling_median(+-W, excl. centre) AND frametime_ms > FLOOR (K=2.5, W=1.0s, FLOOR=13.9 ms, merge<=100 ms)

## Hitches
- **21 hitches** (3.50/min); worst 110.0 ms; median 107.9 ms
- isolated/sparse hitches (>15 s from any other): 0 (0.00/min)
- low-severity tier: 8 (1.33/min)

## Frametimes
- p50 7.03 ms | p95 9.75 ms | p99 11.00 ms
- 1% low **26.4 fps**, 0.1% low **9.1 fps**, mean 136.8 fps
- frames below 50% of cap: 0.31%

## Data quality
- frametime rows: 59672 kept / 59672 read; **0 rejected** (> 10000 ms / non-positive / non-finite)

## Periodicity
- verdict: **mixed** (window 6.0 min, sparse assessable: True)
- steady: period 6.93 s (spectral peak 6.93 s, source spectral) +- 2.37 s, p=0.002494, significant=True, fraction explained 0.76
- sparse: period 72.04 s (spectral peak 72.04 s, source spectral) +- nan s, p=0.002494, significant=True, fraction explained 0.38
- sparse_residual: period 72.04 s (spectral peak 72.04 s, source spectral) +- nan s, p=0.002494, significant=True, fraction explained 1.00

## Sparse hitches (explicit assessment)
- assessment: **none** (5 severe candidate(s) of 21 primary; severity gate 20.8 ms, steady phase 6.93 s removed)
- rate: 0.83/min (95% CI 0.17-1.67, poisson-bootstrap)
- intervals (s): p50 0.2, p90 1.8, CV 1.32
- CAVEAT: only 5 sparse candidate(s) (<8): rate/period estimate is uncertain

## What moved around hitches
| signal.column | feature | cliff's d | z | p | q | hitch | control |
|---|---|---|---|---|---|---|---|
| gpu.gpu_util | min | -0.97 | -4.94 | 1.19e-14 | 4.5e-13 | 19.6 | 36.9 |
| sys.ctxt_per_s | min | -0.96 | -3.97 | 8.82e-14 | 2.9e-12 | 4.22e+04 | 9.73e+04 |
| gpu.temp_c | min | -0.91 | -2.95 | 2.2e-17 | 1.2e-15 | 75.5 | 77.6 |
| cpu.cpu0_util | max | +0.89 | 2.24 | 4.81e-12 | 8.8e-11 | 71.4 | 46.2 |
| mem.swap_used_mib | min | -0.89 | -1.29 | 6.82e-12 | 1.2e-10 | 1.25e+04 | 1.3e+04 |
| cpu.cpu0_util | mean | +0.88 | 2.16 | 8.69e-12 | 1.5e-10 | 38.4 | 26.3 |
| disk.nvme0n1_util_pct | mean | +0.88 | 2.59 | 4.91e-13 | 1.3e-11 | 4.5 | 0.93 |
| sys.load5 | max | -0.88 | -1.70 | 1.2e-11 | 2e-10 | 4.33 | 4.61 |
| sys.load5 | mean | -0.87 | -1.70 | 1.34e-11 | 2.1e-10 | 4.33 | 4.6 |
| sys.load5 | min | -0.87 | -1.68 | 1.64e-11 | 2.5e-10 | 4.33 | 4.6 |
| mem.swap_used_mib | mean | -0.85 | -1.28 | 4.62e-11 | 6.4e-10 | 1.25e+04 | 1.3e+04 |
| disk.nvme0n1_util_pct | max | +0.85 | 3.04 | 2.53e-12 | 4.8e-11 | 12.9 | 2.52 |
| cpufreq.cpu2_mhz | mean | -0.85 | -2.59 | 6.02e-11 | 7.9e-10 | 3.97e+03 | 4.53e+03 |
| gpu.temp_c | mean | -0.84 | -2.68 | 1.09e-14 | 4.4e-13 | 76 | 77.7 |
| mem.mem_free_mib | max | +0.83 | 1.77 | 1.27e-10 | 1.6e-09 | 8.15e+03 | 7.43e+03 |

| log | near hitch | near control | template |
|---|---|---|---|
| dmesg | 0 | 1 | `HOSTNAME kernel: __report_access: # callbacks suppressed` |
| dmesg | 0 | 10 | `HOSTNAME kernel: ptrace attach notice (process names omitted)` |

## What the threads were blocked on during hitches

- window per hitch: [hitch_start - max(pre_ms, magnitude_ms), hitch_end] (pre_ms=50); threads seen: 99
- hitches analysed: 21/21 (a bucket counts when it covers >= 5% of the window)
- main thread off-CPU buckets: S/ppoll do_sys_poll (68%); S/clock_nanosleep hrtimer_nanosleep (9%); S/futex __futex_wait (9%); S/poll do_sys_poll (6%)

| thread | state | syscall | wchan | hitches | % hitches | coverage | threads |
|---|---|---|---|---|---|---|---|
| dota2 | S | futex | __futex_wait | 21 | 100.0% | 100% | 5.0 |
| [vkcf] Analysis | S | futex | __futex_wait | 21 | 100.0% | 100% | 1.0 |
| [vkrt] Analysis | S | futex | __futex_wait | 21 | 100.0% | 100% | 1.0 |
| Async Pipeline | S | futex | __futex_wait | 21 | 100.0% | 100% | 31.0 |
| VmaDefragThread | S | futex | __futex_wait | 21 | 100.0% | 100% | 1.0 |
| VKRenderThread | S | futex | __futex_wait | 21 | 100.0% | 100% | 8.0 |
| AsyncTextureHoo | S | futex | __futex_wait | 21 | 100.0% | 100% | 1.0 |
| mangohud-hwinfo | S | futex | __futex_wait | 21 | 100.0% | 100% | 1.0 |
| CSteamAudioReve | S | futex | __futex_wait | 21 | 100.0% | 100% | 1.0 |
| CSteamAudioPart | S | futex | __futex_wait | 21 | 100.0% | 100% | 1.0 |
| V8 DefaultWorke | S | futex | __futex_wait | 21 | 100.0% | 100% | 1.0 |
| Panorama Image | S | futex | __futex_wait | 21 | 100.0% | 100% | 1.0 |
| SaveJob/0 | S | futex | __futex_wait | 21 | 100.0% | 100% | 1.0 |
| Video Decode Th | S | futex | __futex_wait | 21 | 100.0% | 100% | 5.0 |
| CFileWriterThre | S | futex | __futex_wait | 21 | 100.0% | 100% | 1.0 |
| SteamEngineWatc | S | futex | __futex_wait | 21 | 100.0% | 100% | 1.0 |
| CJobMgr::m_Work | S | futex | __futex_wait | 21 | 100.0% | 100% | 2.0 |
| CHTTPClientThre | S | futex | __futex_wait | 21 | 100.0% | 100% | 1.0 |
| IPC:CSteamEngin | S | futex | __futex_wait | 21 | 100.0% | 100% | 1.0 |
| CHTTPCacheFileT | S | futex | __futex_wait | 21 | 100.0% | 100% | 1.0 |
| CNet Encrypt:0 | S | futex | __futex_wait | 21 | 100.0% | 100% | 1.0 |
| cuda0000a40002a | S | poll | do_sys_poll | 21 | 100.0% | 100% | 1.0 |
| dota2 | S | clock_nanosleep | hrtimer_nanosleep | 21 | 100.0% | 100% | 1.0 |
| dota2 | S | epoll_wait | do_epoll_wait | 21 | 100.0% | 100% | 1.0 |
| IOCP Thread 0 | S | epoll_wait | do_epoll_wait | 21 | 100.0% | 100% | 1.0 |
| IPC:CSteamEngin | S | epoll_wait | do_epoll_wait | 21 | 100.0% | 100% | 1.0 |
| SDLAudioP15 | S | futex | __futex_wait | 21 | 100.0% | 100% | 1.0 |
| PulseMainloop | S | poll | do_sys_poll | 21 | 100.0% | 99% | 1.0 |
| AsyncIOService/ | S | futex | __futex_wait | 21 | 100.0% | 99% | 3.0 |
| PulseHotplug | S | futex | __futex_wait | 21 | 100.0% | 99% | 1.0 |

### Per-thread-name CPU (threads_cpu.csv)

| thread | cpu% (mean) | samples | threads |
|---|---|---|---|
| mangohud-nvidia | 1662168.21 | 459 | 1 |
| AsyncIOService/ | 835684.94 | 55 | 3 |
| dota2 | 761352.53 | 929 | 6 |
| VKRenderThread | 426307.01 | 1155 | 8 |
| PulseHotplug | 302098.82 | 40 | 1 |
| mangohud-hwinfo | 265854.52 | 45 | 1 |
| CJobMgr::m_Work | 262197.03 | 2 | 2 |
| PulseMainloop | 248301.73 | 109 | 1 |
| GlobPool/4 | 236694.89 | 267 | 1 |
| SDLAudioP15 | 230795.88 | 45 | 1 |
| GlobPool/14 | 223858.59 | 266 | 1 |
| GlobPool/12 | 221936.01 | 274 | 1 |
| GlobPool/1 | 217925.04 | 269 | 1 |
| IPC:CSteamEngin | 214899.14 | 56 | 2 |
| GlobPool/2 | 212808.34 | 276 | 1 |


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

