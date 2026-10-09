# Stutter report — live-FP2

- run-dir: `/path/to/repo/runs/live-FP2`
- window: 8.4 min after warm-up (warm-up source: mark), 56445 frames
- hitch rule: frametime_ms > K * rolling_median(+-W, excl. centre) AND frametime_ms > FLOOR (K=2.5, W=1.0s, FLOOR=13.9 ms, merge<=100 ms)

## Hitches
- **23 hitches** (2.75/min); worst 31.3 ms; median 19.5 ms
- isolated/sparse hitches (>15 s from any other): 5 (0.60/min)
- low-severity tier: 785 (93.78/min)

## Frametimes
- p50 7.63 ms | p95 14.35 ms | p99 15.83 ms
- 1% low **59.4 fps**, 0.1% low **50.1 fps**, mean 112.4 fps
- frames below 50% of cap: 7.48%

## Data quality
- frametime rows: 69545 kept / 69545 read; **0 rejected** (> 10000 ms / non-positive / non-finite)

## Periodicity
- verdict: **aperiodic** (window 8.4 min, sparse assessable: True)
- steady: period 7.12 s (spectral peak 0.86 s, source interval) +- 2.65 s, p=0.2943, significant=False, fraction explained 0.26
- sparse: period 58.80 s (spectral peak 33.48 s, source interval) +- 12.83 s, p=0.2294, significant=False, fraction explained 0.35

## Sparse hitches (explicit assessment)
- assessment: **irregular** (8 severe candidate(s) of 23 primary; severity gate 20.8 ms)
- rate: 0.96/min (95% CI 0.36-1.67, poisson-bootstrap)
- intervals (s): p50 24.5, p90 74.1, CV 0.68
- interval mode 67.5 s; modal cluster n=3 cv=0.084 frac=1.00
- CAVEAT: only 3 interval(s) in the [20, 100] s band (<5): regularity cannot be established

## What moved around hitches
| signal.column | feature | cliff's d | z | p | q | hitch | control |
|---|---|---|---|---|---|---|---|
| gpu.vram_used_mib | step | +0.41 | 0.66 | 2.96e-05 | 0.0089 | 3.37 | -0.459 |
| gpu.vram_util_pct | step | +0.41 | 0.66 | 3.66e-05 | 0.0089 | 0.0275 | -0.00374 |
| cpu.cpu_util_avg | max | +0.36 | 0.86 | 0.00363 | 0.2 | 23.3 | 21 |
| disk.nvme0n1_read_iops | mean | +0.34 | 2.80 | 0.000105 | 0.014 | 80.4 | 8.29 |
| gpu.gpu_util | min | -0.34 | -0.86 | 0.00519 | 0.25 | 34.7 | 36.8 |
| disk.nvme0n1_read_iops | max | +0.34 | 2.40 | 0.000117 | 0.014 | 267 | 31.3 |
| disk.nvme0n1_read_mbs | mean | +0.34 | 1.77 | 0.000141 | 0.014 | 4.91 | 0.744 |
| disk.nvme0n1_read_mbs | max | +0.33 | 1.63 | 0.000173 | 0.014 | 17 | 2.81 |
| mem.mem_cached_mib | step | +0.33 | 0.25 | 0.00697 | 0.28 | 4 | -3.99 |
| threads.proc_rss_mib | step | +0.32 | -0.01 | 0.00854 | 0.28 | 0.158 | 0.171 |
| cpu.cpu30_util | min | -0.32 | -0.62 | 0.00294 | 0.2 | 0.87 | 4.32 |
| sys.ctxt_per_s | min | -0.29 | -0.39 | 0.0181 | 0.34 | 6.3e+04 | 6.52e+04 |
| cpufreq.cpu26_mhz | max | +0.29 | 0.37 | 0.0202 | 0.34 | 4.44e+03 | 4.41e+03 |
| cpufreq.cpu29_mhz | step | +0.28 | 0.43 | 0.021 | 0.34 | 564 | 74.9 |
| gpu.gpu_util | mean | -0.28 | -0.73 | 0.0213 | 0.34 | 36.8 | 38.4 |

## What the threads were blocked on during hitches

- window per hitch: [hitch_start - max(pre_ms, magnitude_ms), hitch_end] (pre_ms=50); threads seen: 75
- hitches analysed: 23/23 (a bucket counts when it covers >= 5% of the window)
- main thread off-CPU buckets: S/epoll_wait do_epoll_wait (37%); S/futex __futex_wait (34%); S/clock_nanosleep hrtimer_nanosleep (11%); S/- __futex_wait (11%)

| thread | state | syscall | wchan | hitches | % hitches | coverage | threads |
|---|---|---|---|---|---|---|---|
| dota2 | S | futex | __futex_wait | 23 | 100.0% | 100% | 5.0 |
| [vkcf] Analysis | S | futex | __futex_wait | 23 | 100.0% | 100% | 1.0 |
| [vkrt] Analysis | S | futex | __futex_wait | 23 | 100.0% | 100% | 1.0 |
| Async Pipeline | S | futex | __futex_wait | 23 | 100.0% | 100% | 31.0 |
| VmaDefragThread | S | futex | __futex_wait | 23 | 100.0% | 100% | 1.0 |
| AsyncTextureHoo | S | futex | __futex_wait | 23 | 100.0% | 100% | 1.0 |
| mangohud-hwinfo | S | futex | __futex_wait | 23 | 100.0% | 100% | 1.0 |
| CSteamAudioReve | S | futex | __futex_wait | 23 | 100.0% | 100% | 1.0 |
| CSteamAudioPart | S | futex | __futex_wait | 23 | 100.0% | 100% | 1.0 |
| V8 DefaultWorke | S | futex | __futex_wait | 23 | 100.0% | 100% | 1.0 |
| Panorama Image | S | futex | __futex_wait | 23 | 100.0% | 100% | 1.0 |
| SaveJob/0 | S | futex | __futex_wait | 23 | 100.0% | 100% | 1.0 |
| cuda0000a40002a | S | poll | do_sys_poll | 23 | 100.0% | 100% | 1.0 |
| PulseHotplug | S | futex | __futex_wait | 23 | 100.0% | 100% | 1.0 |
| PulseMainloop | S | poll | do_sys_poll | 23 | 100.0% | 100% | 1.0 |
| AsyncIOService/ | S | futex | __futex_wait | 23 | 100.0% | 100% | 3.0 |
| SDLAudioP15 | S | futex | __futex_wait | 23 | 100.0% | 100% | 1.0 |
| dota2 | S | clock_nanosleep | hrtimer_nanosleep | 23 | 100.0% | 99% | 1.0 |
| [vkps] Update | S | futex | __futex_wait | 23 | 100.0% | 99% | 1.0 |
| dota2 | S | epoll_wait | do_epoll_wait | 23 | 100.0% | 99% | 1.0 |
| AudioMixer | S | futex | __futex_wait | 23 | 100.0% | 98% | 1.0 |
| VKRenderThread | S | futex | __futex_wait | 23 | 100.0% | 97% | 8.0 |
| dota2 | S | poll | do_sys_poll | 23 | 100.0% | 96% | 1.0 |
| mangohud-nvidia | S | clock_nanosleep | hrtimer_nanosleep | 23 | 100.0% | 95% | 1.0 |
| GlobPool/6 | S | futex | __futex_wait | 23 | 100.0% | 65% | 1.0 |
| GlobPool/1 | S | futex | __futex_wait | 23 | 100.0% | 64% | 1.0 |
| GlobPool/5 | S | futex | __futex_wait | 23 | 100.0% | 61% | 1.0 |
| GlobPool/3 | S | futex | __futex_wait | 23 | 100.0% | 61% | 1.0 |
| GlobPool/2 | S | futex | __futex_wait | 23 | 100.0% | 60% | 1.0 |
| GlobPool/0 | S | futex | __futex_wait | 23 | 100.0% | 59% | 1.0 |

### Per-thread-name CPU (threads_cpu.csv)

| thread | cpu% (mean) | samples | threads |
|---|---|---|---|
| mangohud-nvidia | 1039031.52 | 651 | 1 |
| dota2 | 739716.77 | 1523 | 6 |
| AsyncTextureHoo | 738610.63 | 11 | 1 |
| AsyncIOService/ | 566306.30 | 98 | 3 |
| VKRenderThread | 339653.57 | 1418 | 8 |
| GlobPool/3 | 289268.50 | 600 | 1 |
| GlobPool/6 | 280362.20 | 600 | 1 |
| GlobPool/0 | 272777.83 | 600 | 1 |
| GlobPool/4 | 269103.28 | 603 | 1 |
| GlobPool/1 | 264083.75 | 599 | 1 |
| GlobPool/2 | 262791.99 | 601 | 1 |
| GlobPool/5 | 258568.65 | 600 | 1 |
| Async Pipeline | 205310.81 | 92 | 31 |
| AudioMixer | 136957.78 | 116 | 1 |
| [vkps] Update | 111615.28 | 83 | 1 |


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

