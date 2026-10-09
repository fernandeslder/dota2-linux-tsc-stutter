# Stutter report — live-P1-proton-demo

- run-dir: `/path/to/repo/runs/live-P1-proton-demo`
- window: 1.0 min after warm-up (warm-up source: mark), 7808 frames
- hitch rule: frametime_ms > K * rolling_median(+-W, excl. centre) AND frametime_ms > FLOOR (K=2.5, W=1.0s, FLOOR=13.9 ms, merge<=100 ms)

## Hitches
- **10 hitches** (10.51/min); worst 1211.0 ms; median 54.0 ms
- isolated/sparse hitches (>15 s from any other): 0 (0.00/min)
- low-severity tier: 7 (7.35/min)

## Frametimes
- p50 7.07 ms | p95 10.32 ms | p99 11.95 ms
- 1% low **24.7 fps**, 0.1% low **3.5 fps**, mean 136.8 fps
- frames below 50% of cap: 0.22%

## Data quality
- frametime rows: 36508 kept / 36508 read; **0 rejected** (> 10000 ms / non-positive / non-finite)

## Periodicity
- verdict: **aperiodic** (window 0.8 min, sparse assessable: False)
- steady: period 3.47 s (spectral peak 3.47 s, source interval) +- 1.99 s, p=0.5586, significant=False, fraction explained 0.50
- sparse: period 48.60 s (spectral peak 48.60 s, source spectral) +- 3.68 s, p=0.8005, significant=False, fraction explained 0.30
- WARNING: post-warm-up window 0.8 min < 5 min: sparse (30-90 s) periodicity cannot be assessed

## Sparse hitches (explicit assessment)
- assessment: **none** (9 severe candidate(s) of 10 primary; severity gate 20.8 ms)
- rate: 11.12/min (95% CI 4.94-18.53, poisson-bootstrap)
- intervals (s): p50 4.7, p90 8.9, CV 0.51
- CAVEAT: post-warm-up window 0.8 min < 5 min: sparse assessment unreliable

## What moved around hitches
| signal.column | feature | cliff's d | z | p | q | hitch | control |
|---|---|---|---|---|---|---|---|
| hwmon.k10temp_temp4_c | max | -0.61 | -0.91 | 0.00115 | 0.038 | 98.7 | 101 |
| cpufreq.cpu16_mhz | mean | +0.52 | 0.93 | 0.00588 | 0.17 | 4.25e+03 | 3.94e+03 |
| cpu.cpu12_util | min | +0.50 | 0.00 | 6.34e-24 | 3.1e-21 | 9.67 | 0 |
| cpu.cpu12_util | mean | +0.50 | 1.32 | 0.00804 | 0.22 | 28.3 | 23.5 |
| cpufreq.cpu11_mhz | step | -0.49 | -0.72 | 0.00836 | 0.22 | -505 | -3.08 |
| cpufreq.cpu11_mhz | max | -0.48 | -1.04 | 0.01 | 0.25 | 4.74e+03 | 4.77e+03 |
| cpufreq.cpu20_mhz | max | -0.45 | -1.37 | 0.0155 | 0.35 | 4.72e+03 | 4.77e+03 |
| cpufreq.cpu6_mhz | min | +0.43 | 0.62 | 0.0216 | 0.44 | 4.31e+03 | 3.83e+03 |
| cpufreq.cpu22_mhz | max | -0.43 | -0.95 | 0.0221 | 0.44 | 4.73e+03 | 4.77e+03 |
| cpufreq.cpu5_mhz | max | -0.42 | -0.97 | 0.0238 | 0.45 | 4.75e+03 | 4.79e+03 |
| cpufreq.cpu16_mhz | min | +0.42 | 0.98 | 0.00279 | 0.087 | 2.7e+03 | 1.9e+03 |
| cpufreq.cpu9_mhz | step | +0.39 | 0.68 | 0.0373 | 0.64 | 393 | -211 |
| cpu.cpu22_util | max | +0.38 | 0.94 | 0.0395 | 0.65 | 43 | 34.1 |
| cpufreq.cpu8_mhz | max | -0.36 | -0.89 | 0.0518 | 0.78 | 4.75e+03 | 4.78e+03 |
| cpu.cpu8_util | max | -0.36 | -0.72 | 0.034 | 0.6 | 35.7 | 39.2 |

## What the threads were blocked on during hitches

- window per hitch: [hitch_start - max(pre_ms, magnitude_ms), hitch_end] (pre_ms=50); threads seen: 107
- hitches analysed: 10/10 (a bucket counts when it covers >= 5% of the window)
- main thread off-CPU buckets: S/pselect6 do_select (62%); S/ioctl ntsync_schedule.isra.0 (21%); S/- 0 (6%); S/- ntsync_schedule.isra.0 (3%)

| thread | state | syscall | wchan | hitches | % hitches | coverage | threads |
|---|---|---|---|---|---|---|---|
| DeviceHotplugTh | S | ioctl | ntsync_schedule.isra.0 | 10 | 100.0% | 100% | 1.0 |
| wine_sechost_de | S | ioctl | ntsync_schedule.isra.0 | 10 | 100.0% | 100% | 1.0 |
| AsyncIOService/ | S | ioctl | ntsync_schedule.isra.0 | 10 | 100.0% | 100% | 3.0 |
| MainThrd | S | ioctl | ntsync_schedule.isra.0 | 10 | 100.0% | 100% | 6.0 |
| wine_rpcrt4_ser | S | ioctl | ntsync_schedule.isra.0 | 10 | 100.0% | 100% | 1.0 |
| CSteamAudioReve | S | ioctl | ntsync_schedule.isra.0 | 10 | 100.0% | 100% | 1.0 |
| CSteamAudioPart | S | ioctl | ntsync_schedule.isra.0 | 10 | 100.0% | 100% | 1.0 |
| wine_mmdevapi_n | S | ioctl | ntsync_schedule.isra.0 | 10 | 100.0% | 100% | 1.0 |
| Panorama Image | S | ioctl | ntsync_schedule.isra.0 | 10 | 100.0% | 100% | 1.0 |
| MainThrd | S | futex | __futex_wait | 10 | 100.0% | 100% | 9.0 |
| [vkcf] Analysis | S | futex | __futex_wait | 10 | 100.0% | 100% | 2.0 |
| [vkrt] Analysis | S | futex | __futex_wait | 10 | 100.0% | 100% | 2.0 |
| [vkps] Update | S | futex | __futex_wait | 10 | 100.0% | 100% | 2.0 |
| dxvk-submit | S | futex | __futex_wait | 10 | 100.0% | 100% | 2.0 |
| dxvk-queue | S | futex | __futex_wait | 10 | 100.0% | 100% | 2.0 |
| AsyncTextureHoo | S | futex | __futex_wait | 10 | 100.0% | 100% | 1.0 |
| dxvk-shader-l | S | futex | __futex_wait | 10 | 100.0% | 100% | 8.0 |
| dxvk-shader-n | S | futex | __futex_wait | 10 | 100.0% | 100% | 14.0 |
| dxvk-shader-h | S | futex | __futex_wait | 10 | 100.0% | 100% | 10.0 |
| dxvk-frame | S | futex | __futex_wait | 10 | 100.0% | 100% | 1.0 |
| SDLWASAPIMgmt | S | futex | __futex_wait | 10 | 100.0% | 100% | 1.0 |
| SaveJob/0 | S | futex | __futex_wait | 10 | 100.0% | 100% | 1.0 |
| dxvk-cache | S | futex | __futex_wait | 10 | 100.0% | 100% | 1.0 |
| CFileWriterThre | S | futex | __futex_wait | 10 | 100.0% | 100% | 1.0 |
| SteamEngineWatc | S | futex | __futex_wait | 10 | 100.0% | 100% | 1.0 |
| CJobMgr::m_Work | S | futex | __futex_wait | 10 | 100.0% | 100% | 2.0 |
| CHTTPClientThre | S | futex | __futex_wait | 10 | 100.0% | 100% | 1.0 |
| IPC:CSteamEngin | S | futex | __futex_wait | 10 | 100.0% | 100% | 1.0 |
| CHTTPCacheFileT | S | futex | __futex_wait | 10 | 100.0% | 100% | 1.0 |
| CNet Encrypt:0 | S | futex | __futex_wait | 10 | 100.0% | 100% | 1.0 |

### Per-thread-name CPU (threads_cpu.csv)

| thread | cpu% (mean) | samples | threads |
|---|---|---|---|
| CHTTPCacheIniti | 3495253.33 | 1 | 1 |
| mangohud-nvidia | 1811045.86 | 485 | 1 |
| MainThrd | 1342448.50 | 965 | 7 |
| AsyncIOService/ | 1285231.77 | 57 | 3 |
| cuda-EvtHandlr | 1048626.01 | 2 | 1 |
| IPC:CSteamEngin | 593618.36 | 18 | 1 |
| dxvk-submit | 526356.52 | 464 | 1 |
| dxvk-cache | 508246.13 | 5 | 1 |
| dxvk-frame | 318132.57 | 26 | 1 |
| dxvk-queue | 293918.06 | 353 | 1 |
| GlobPool/4 | 277375.34 | 234 | 1 |
| GlobPool/1 | 277000.97 | 246 | 1 |
| dxvk-cs | 271261.94 | 210 | 1 |
| GlobPool/2 | 268837.82 | 233 | 1 |
| AudioMixer | 260974.86 | 81 | 1 |


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

