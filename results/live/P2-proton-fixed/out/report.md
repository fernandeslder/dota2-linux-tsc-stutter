# Stutter report — live-P2-proton-fixed

- run-dir: `/path/to/repo/runs/live-P2-proton-fixed`
- window: 6.1 min after warm-up (warm-up source: mark), 52365 frames
- hitch rule: frametime_ms > K * rolling_median(+-W, excl. centre) AND frametime_ms > FLOOR (K=2.5, W=1.0s, FLOOR=13.9 ms, merge<=100 ms)

## Hitches
- **12 hitches** (1.96/min); worst 40.8 ms; median 27.8 ms
- isolated/sparse hitches (>15 s from any other): 2 (0.33/min)
- low-severity tier: 31 (5.05/min)

## Frametimes
- p50 7.03 ms | p95 10.31 ms | p99 11.65 ms
- 1% low **77.5 fps**, 0.1% low **55.4 fps**, mean 142.3 fps
- frames below 50% of cap: 0.10%

## Data quality
- frametime rows: 62406 kept / 62406 read; **0 rejected** (> 10000 ms / non-positive / non-finite)

## Periodicity
- verdict: **mixed** (window 6.0 min, sparse assessable: True)
- steady: period 8.18 s (spectral peak 8.18 s, source spectral) +- 1.12 s, p=0.002494, significant=True, fraction explained 0.92
- sparse: period 60.02 s (spectral peak 60.02 s, source spectral) +- 8.67 s, p=0.002494, significant=True, fraction explained 0.92

## Sparse hitches (explicit assessment)
- assessment: **none** (0 severe candidate(s) of 12 primary; severity gate 20.8 ms, steady phase 8.18 s removed)
- CAVEAT: no severe isolated hitches in the window

## What moved around hitches
| signal.column | feature | cliff's d | z | p | q | hitch | control |
|---|---|---|---|---|---|---|---|
| cpu.cpu8_util | mean | +0.71 | 1.38 | 3.16e-05 | 0.0013 | 21.2 | 17.3 |
| gpu.video_clock_mhz | min | +0.70 | 1.38 | 2.04e-05 | 0.001 | 1.66e+03 | 1.6e+03 |
| cpu.cpu8_util | max | +0.69 | 0.71 | 2.65e-05 | 0.0012 | 33.7 | 28.7 |
| gpu.sm_clock_mhz | min | +0.69 | 1.04 | 3.89e-05 | 0.0014 | 1.67e+03 | 1.63e+03 |
| gpu.graphics_clock_mhz | min | +0.69 | 1.04 | 3.89e-05 | 0.0014 | 1.67e+03 | 1.63e+03 |
| sys.ctxt_per_s | mean | +0.69 | 1.49 | 6.14e-05 | 0.0017 | 9.52e+04 | 7.38e+04 |
| gpu.video_clock_mhz | mean | +0.68 | 1.27 | 6e-05 | 0.0017 | 1.67e+03 | 1.61e+03 |
| cpufreq.cpu15_mhz | max | -0.68 | -1.03 | 6.68e-05 | 0.0018 | 4.57e+03 | 4.63e+03 |
| cpu.cpu14_util | max | +0.68 | 1.25 | 6.01e-05 | 0.0017 | 60.3 | 47.2 |
| gpu.temp_c | mean | +0.68 | 1.22 | 4.06e-05 | 0.0014 | 79.9 | 79.3 |
| cpu.cpu7_util | mean | +0.67 | 1.16 | 8.27e-05 | 0.0019 | 13.7 | 9.5 |
| gpu.sm_clock_mhz | mean | +0.67 | 0.92 | 0.000101 | 0.002 | 1.68e+03 | 1.64e+03 |
| gpu.graphics_clock_mhz | mean | +0.67 | 0.92 | 0.000101 | 0.002 | 1.68e+03 | 1.64e+03 |
| cpu.cpu29_util | mean | -0.66 | -0.82 | 8.11e-05 | 0.0019 | 0.152 | 2.18 |
| threads.main_cpu_pct | mean | +0.66 | 1.12 | 0.000105 | 0.002 | 58.2 | 55.9 |

## What the threads were blocked on during hitches

- window per hitch: [hitch_start - max(pre_ms, magnitude_ms), hitch_end] (pre_ms=50); threads seen: 107
- hitches analysed: 12/12 (a bucket counts when it covers >= 5% of the window)
- main thread off-CPU buckets: S/pselect6 do_select (71%); S/ioctl ntsync_schedule.isra.0 (20%); D/ioctl_nv os_acquire_rwlock_read (4%); S/- 0 (4%)

| thread | state | syscall | wchan | hitches | % hitches | coverage | threads |
|---|---|---|---|---|---|---|---|
| MainThrd | S | futex | __futex_wait | 12 | 100.0% | 100% | 9.0 |
| [vkcf] Analysis | S | futex | __futex_wait | 12 | 100.0% | 100% | 2.0 |
| [vkrt] Analysis | S | futex | __futex_wait | 12 | 100.0% | 100% | 2.0 |
| [vkps] Update | S | futex | __futex_wait | 12 | 100.0% | 100% | 2.0 |
| AsyncTextureHoo | S | futex | __futex_wait | 12 | 100.0% | 100% | 1.0 |
| dxvk-shader-l | S | futex | __futex_wait | 12 | 100.0% | 100% | 8.0 |
| dxvk-shader-n | S | futex | __futex_wait | 12 | 100.0% | 100% | 14.0 |
| dxvk-shader-h | S | futex | __futex_wait | 12 | 100.0% | 100% | 10.0 |
| SDLWASAPIMgmt | S | futex | __futex_wait | 12 | 100.0% | 100% | 1.0 |
| SaveJob/0 | S | futex | __futex_wait | 12 | 100.0% | 100% | 1.0 |
| CFileWriterThre | S | futex | __futex_wait | 12 | 100.0% | 100% | 1.0 |
| SteamEngineWatc | S | futex | __futex_wait | 12 | 100.0% | 100% | 1.0 |
| CJobMgr::m_Work | S | futex | __futex_wait | 12 | 100.0% | 100% | 2.0 |
| CHTTPCacheFileT | S | futex | __futex_wait | 12 | 100.0% | 100% | 1.0 |
| CHTTPClientThre | S | futex | __futex_wait | 12 | 100.0% | 100% | 1.0 |
| IPC:CSteamEngin | S | futex | __futex_wait | 12 | 100.0% | 100% | 1.0 |
| CNet Encrypt:0 | S | futex | __futex_wait | 12 | 100.0% | 100% | 1.0 |
| dxvk-cache | S | futex | __futex_wait | 12 | 100.0% | 100% | 1.0 |
| cuda00016c0005c | S | poll | do_sys_poll | 12 | 100.0% | 100% | 1.0 |
| MainThrd | S | poll | do_sys_poll | 12 | 100.0% | 100% | 2.0 |
| cuda-EvtHandlr | S | poll | do_sys_poll | 12 | 100.0% | 100% | 1.0 |
| MainThrd | S | clock_nanosleep | hrtimer_nanosleep | 12 | 100.0% | 100% | 3.0 |
| DeviceHotplugTh | S | ioctl | ntsync_schedule.isra.0 | 12 | 100.0% | 100% | 1.0 |
| wine_sechost_de | S | ioctl | ntsync_schedule.isra.0 | 12 | 100.0% | 100% | 1.0 |
| AsyncIOService/ | S | ioctl | ntsync_schedule.isra.0 | 12 | 100.0% | 100% | 3.0 |
| MainThrd | S | ioctl | ntsync_schedule.isra.0 | 12 | 100.0% | 100% | 6.0 |
| wine_rpcrt4_ser | S | ioctl | ntsync_schedule.isra.0 | 12 | 100.0% | 100% | 1.0 |
| CSteamAudioReve | S | ioctl | ntsync_schedule.isra.0 | 12 | 100.0% | 100% | 1.0 |
| CSteamAudioPart | S | ioctl | ntsync_schedule.isra.0 | 12 | 100.0% | 100% | 1.0 |
| wine_mmdevapi_n | S | ioctl | ntsync_schedule.isra.0 | 12 | 100.0% | 100% | 1.0 |

### Per-thread-name CPU (threads_cpu.csv)

| thread | cpu% (mean) | samples | threads |
|---|---|---|---|
| MainThrd | 3871708.85 | 993 | 8 |
| AsyncIOService/ | 3809663.01 | 57 | 3 |
| mangohud-nvidia | 2858916.48 | 469 | 1 |
| dxvk-submit | 1494751.51 | 456 | 1 |
| CHTTPCacheIniti | 1198372.57 | 1 | 1 |
| dxvk-shader-l | 863259.85 | 15 | 8 |
| dxvk-shader-n | 786515.51 | 83 | 14 |
| dxvk-queue | 703238.81 | 445 | 1 |
| AsyncTextureHoo | 701994.68 | 6 | 1 |
| GlobPool/4 | 543664.86 | 336 | 1 |
| AudioMixer | 523164.04 | 90 | 1 |
| dxvk-frame | 520492.85 | 41 | 1 |
| GlobPool/0 | 505441.67 | 349 | 1 |
| dxvk-descriptor | 473021.54 | 179 | 1 |
| GlobPool/2 | 452254.95 | 343 | 1 |


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

