# Stutter report — live-FP2

- run-dir: `/path/to/repo/runs/live-FP2`
- window: 20.0 min after warm-up (warm-up source: mark), 134648 frames
- hitch rule: frametime_ms > K * rolling_median(+-W, excl. centre) AND frametime_ms > FLOOR (K=2.5, W=1.0s, FLOOR=13.9 ms, merge<=100 ms)

## Hitches
- **57 hitches** (2.85/min); worst 54.2 ms; median 21.3 ms
- isolated/sparse hitches (>15 s from any other): 9 (0.45/min)
- low-severity tier: 1971 (98.46/min)

## Frametimes
- p50 7.63 ms | p95 14.42 ms | p99 15.85 ms
- 1% low **58.6 fps**, 0.1% low **45.2 fps**, mean 112.1 fps
- frames below 50% of cap: 7.85%

## Data quality
- frametime rows: 147649 kept / 147649 read; **0 rejected** (> 10000 ms / non-positive / non-finite)

## Periodicity
- verdict: **aperiodic** (window 20.0 min, sparse assessable: True)
- steady: period 6.25 s (spectral peak 5.33 s, source interval) +- 1.61 s, p=0.1122, significant=False, fraction explained 0.28
- sparse: period 52.18 s (spectral peak 50.01 s, source interval) +- 5.71 s, p=0.01247, significant=False, fraction explained 0.30

## Sparse hitches (explicit assessment)
- assessment: **irregular** (29 severe candidate(s) of 57 primary; severity gate 20.8 ms)
- rate: 1.45/min (95% CI 0.95-2.00, poisson-bootstrap)
- intervals (s): p50 7.5, p90 121.0, CV 1.46
- interval mode 58.5 s; modal cluster n=4 cv=0.108 frac=1.00
- CAVEAT: only 4 interval(s) in the [20, 100] s band (<5): regularity cannot be established

## What moved around hitches
| signal.column | feature | cliff's d | z | p | q | hitch | control |
|---|---|---|---|---|---|---|---|
| sys.ctxt_per_s | min | -0.57 | -1.31 | 2.9e-13 | 5e-11 | 5.71e+04 | 6.46e+04 |
| disk.nvme0n1_util_pct | mean | +0.47 | 1.43 | 1.76e-11 | 2.3e-09 | 1.68 | 0.488 |
| sys.intr_per_s | min | -0.46 | -1.14 | 4.55e-09 | 1.6e-07 | 3.62e+04 | 3.91e+04 |
| disk.nvme0n1_util_pct | max | +0.44 | 1.27 | 3.27e-10 | 1.2e-08 | 4.86 | 1.63 |
| threads.proc_cpu_pct | min | -0.42 | -1.64 | 6.7e-08 | 2e-06 | 328 | 377 |
| gpu.gpu_util | min | -0.42 | -1.91 | 7.68e-08 | 2.2e-06 | 31.9 | 36.8 |
| sys.forks_per_s | mean | +0.40 | 1.55 | 3.14e-07 | 8.5e-06 | 28.9 | 9.58 |
| threads.main_cpu_pct | min | -0.39 | -1.45 | 3.75e-07 | 9.2e-06 | 66.9 | 74.4 |
| threads.busiest_cpu_pct | min | -0.39 | -1.45 | 3.75e-07 | 9.2e-06 | 66.9 | 74.4 |
| gpu.mem_util | min | -0.39 | -1.51 | 2.26e-08 | 7.3e-07 | 7.84 | 8.88 |
| mem.mem_free_mib | step | -0.39 | -1.35 | 8.23e-07 | 1.9e-05 | -20.4 | 1.3 |
| mem.mem_available_mib | step | -0.38 | -1.48 | 1.18e-06 | 2.6e-05 | -17.5 | 0.451 |
| disk.nvme0n1_read_iops | mean | +0.38 | 5.28 | 7.64e-11 | 7.9e-09 | 171 | 5.8 |
| disk.nvme0n1_read_iops | max | +0.37 | 7.06 | 1.22e-10 | 1e-08 | 652 | 20.3 |
| disk.nvme0n1_read_mbs | max | +0.37 | 11.62 | 1.52e-10 | 1e-08 | 72.9 | 1.35 |

## What the threads were blocked on during hitches

- window per hitch: [hitch_start - max(pre_ms, magnitude_ms), hitch_end] (pre_ms=50); threads seen: 76
- hitches analysed: 57/57 (a bucket counts when it covers >= 5% of the window)
- main thread off-CPU buckets: S/epoll_wait do_epoll_wait (41%); S/futex __futex_wait (21%); D/ioctl_nv os_acquire_rwlock_read (13%); S/- 0 (9%)

| thread | state | syscall | wchan | hitches | % hitches | coverage | threads |
|---|---|---|---|---|---|---|---|
| dota2 | S | epoll_wait | do_epoll_wait | 57 | 100.0% | 100% | 1.9 |
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
| cuda0000a40002a | S | poll | do_sys_poll | 57 | 100.0% | 100% | 1.0 |
| dota2 | S | clock_nanosleep | hrtimer_nanosleep | 57 | 100.0% | 100% | 1.0 |
| mangohud-hwinfo | S | futex | __futex_wait | 57 | 100.0% | 100% | 1.0 |
| [vkps] Update | S | futex | __futex_wait | 57 | 100.0% | 99% | 1.0 |
| PulseHotplug | S | futex | __futex_wait | 57 | 100.0% | 99% | 1.0 |
| SDLAudioP15 | S | futex | __futex_wait | 57 | 100.0% | 99% | 1.0 |
| PulseMainloop | S | poll | do_sys_poll | 57 | 100.0% | 98% | 1.0 |
| AudioMixer | S | futex | __futex_wait | 57 | 100.0% | 98% | 1.0 |
| dota2 | S | poll | do_sys_poll | 57 | 100.0% | 98% | 1.0 |
| mangohud-nvidia | S | clock_nanosleep | hrtimer_nanosleep | 57 | 100.0% | 89% | 1.0 |
| GlobPool/0 | S | futex | __futex_wait | 57 | 100.0% | 68% | 1.0 |
| GlobPool/3 | S | futex | __futex_wait | 57 | 100.0% | 67% | 1.0 |
| GlobPool/1 | S | futex | __futex_wait | 57 | 100.0% | 66% | 1.0 |
| GlobPool/4 | S | futex | __futex_wait | 57 | 100.0% | 66% | 1.0 |
| GlobPool/2 | S | futex | __futex_wait | 57 | 100.0% | 65% | 1.0 |
| GlobPool/6 | S | futex | __futex_wait | 57 | 100.0% | 64% | 1.0 |

### Per-thread-name CPU (threads_cpu.csv)

| thread | cpu% (mean) | samples | threads |
|---|---|---|---|
| mangohud-nvidia | 1545977.72 | 1340 | 1 |
| dota2 | 1079311.92 | 3176 | 7 |
| AsyncTextureHoo | 608286.68 | 11 | 1 |
| VKRenderThread | 421717.35 | 3204 | 8 |
| AsyncIOService/ | 362469.38 | 96 | 3 |
| GlobPool/2 | 350257.40 | 1287 | 1 |
| GlobPool/4 | 350220.31 | 1285 | 1 |
| GlobPool/5 | 343848.46 | 1290 | 1 |
| GlobPool/3 | 336263.90 | 1282 | 1 |
| GlobPool/6 | 335926.82 | 1292 | 1 |
| GlobPool/0 | 333200.63 | 1289 | 1 |
| GlobPool/1 | 330615.31 | 1291 | 1 |
| AudioMixer | 254641.76 | 248 | 1 |
| PulseHotplug | 197294.99 | 116 | 1 |
| PulseMainloop | 184201.61 | 340 | 1 |


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

