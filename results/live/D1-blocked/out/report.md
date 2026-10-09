# Stutter report — live-D1-blocked

- run-dir: `/path/to/repo/runs/live-D1-blocked`
- window: 6.0 min after warm-up (warm-up source: mark), 37758 frames
- hitch rule: frametime_ms > K * rolling_median(+-W, excl. centre) AND frametime_ms > FLOOR (K=2.5, W=1.0s, FLOOR=13.9 ms, merge<=100 ms)

## Hitches
- **195 hitches** (32.46/min); worst 2957.9 ms; median 70.9 ms
- isolated/sparse hitches (>15 s from any other): 0 (0.00/min)
- low-severity tier: 200 (33.30/min)

## Frametimes
- p50 7.47 ms | p95 13.18 ms | p99 15.72 ms
- 1% low **8.4 fps**, 0.1% low **1.3 fps**, mean 104.8 fps
- frames below 50% of cap: 2.86%

## Data quality
- frametime rows: 48644 kept / 48644 read; **0 rejected** (> 10000 ms / non-positive / non-finite)

## Periodicity
- verdict: **aperiodic** (window 6.0 min, sparse assessable: True)
- steady: period 1.73 s (spectral peak 0.55 s, source interval) +- 0.23 s, p=0.8279, significant=False, fraction explained 0.25
- sparse: period 40.04 s (spectral peak 40.04 s, source spectral) +- 14.66 s, p=0.7606, significant=False, fraction explained 0.23

## Sparse hitches (explicit assessment)
- assessment: **none** (183 severe candidate(s) of 195 primary; severity gate 20.8 ms)
- rate: 30.47/min (95% CI 26.14-34.80, poisson-bootstrap)
- intervals (s): p50 1.6, p90 4.3, CV 0.88

## What moved around hitches
| signal.column | feature | cliff's d | z | p | q | hitch | control |
|---|---|---|---|---|---|---|---|
| sys.ctxt_per_s | min | -0.81 | -2.67 | 5.45e-82 | 7.1e-80 | 2.38e+04 | 5.9e+04 |
| sys.intr_per_s | min | -0.80 | -2.63 | 9.74e-80 | 1e-77 | 1.69e+04 | 3.64e+04 |
| threads.proc_cpu_pct | min | -0.79 | -2.22 | 1.61e-78 | 1.4e-76 | 156 | 312 |
| threads.main_cpu_pct | min | -0.79 | -2.72 | 4.51e-78 | 3.3e-76 | 16.7 | 56.3 |
| cpu.cpu_util_avg | min | -0.74 | -2.04 | 1.38e-67 | 8.9e-66 | 8.5 | 14 |
| threads.busiest_cpu_pct | min | -0.71 | -2.55 | 8.34e-63 | 4.8e-61 | 36.8 | 59.5 |
| threads.main_cpu_pct | mean | -0.71 | -0.69 | 3e-62 | 1.6e-60 | 67.1 | 77.9 |
| threads.proc_cpu_pct | step | +0.63 | 2.28 | 4.12e-50 | 1.9e-48 | 73.2 | -6.73 |
| threads.main_cpu_pct | step | +0.62 | 2.16 | 7.09e-49 | 2.8e-47 | 18.3 | -1.54 |
| net.netif0_tx_mbps | min | -0.62 | -1.99 | 3.74e-48 | 1.4e-46 | 0.0249 | 0.0439 |
| sys.ctxt_per_s | step | +0.61 | 1.42 | 2.69e-46 | 8.2e-45 | 1.36e+04 | -823 |
| cpu.cpu0_util | max | +0.60 | 1.17 | 4.33e-47 | 1.5e-45 | 91.7 | 72.1 |
| cpufreq.cpu0_mhz | max | +0.60 | 1.22 | 1.13e-45 | 3.3e-44 | 4.8e+03 | 4.68e+03 |
| cpu.cpu_util_avg | step | +0.58 | 1.89 | 2.77e-43 | 6.8e-42 | 2.76 | -0.225 |
| sys.intr_per_s | step | +0.57 | 1.59 | 1.39e-41 | 3.2e-40 | 7.48e+03 | -517 |

| log | near hitch | near control | template |
|---|---|---|---|
| journal | 0 | 1 | `HOSTNAME systemd[#]: Starting Stop the on-demand background stac` |
| journal | 0 | 4 | `HOSTNAME systemd[#]: idle-reaper.service: Deactivated ` |
| journal | 0 | 4 | `HOSTNAME systemd[#]: Finished Stop the on-demand background stac` |

## What the threads were blocked on during hitches

- window per hitch: [hitch_start - max(pre_ms, magnitude_ms), hitch_end] (pre_ms=50); threads seen: 75
- hitches analysed: 195/195 (a bucket counts when it covers >= 5% of the window)
- main thread off-CPU buckets: S/futex __futex_wait (72%); S/epoll_wait do_epoll_wait (26%); S/poll do_sys_poll (1%); S/- 0 (0%)

| thread | state | syscall | wchan | hitches | % hitches | coverage | threads |
|---|---|---|---|---|---|---|---|
| dota2 | S | futex | __futex_wait | 195 | 100.0% | 100% | 5.0 |
| [vkrt] Analysis | S | futex | __futex_wait | 195 | 100.0% | 100% | 1.0 |
| Async Pipeline | S | futex | __futex_wait | 195 | 100.0% | 100% | 31.0 |
| VmaDefragThread | S | futex | __futex_wait | 195 | 100.0% | 100% | 1.0 |
| CSteamAudioReve | S | futex | __futex_wait | 195 | 100.0% | 100% | 1.0 |
| CSteamAudioPart | S | futex | __futex_wait | 195 | 100.0% | 100% | 1.0 |
| V8 DefaultWorke | S | futex | __futex_wait | 195 | 100.0% | 100% | 1.0 |
| Panorama Image | S | futex | __futex_wait | 195 | 100.0% | 100% | 1.0 |
| SaveJob/0 | S | futex | __futex_wait | 195 | 100.0% | 100% | 1.0 |
| cuda0000a40002a | S | poll | do_sys_poll | 195 | 100.0% | 100% | 1.0 |
| AsyncTextureHoo | S | futex | __futex_wait | 195 | 100.0% | 100% | 1.0 |
| mangohud-hwinfo | S | futex | __futex_wait | 195 | 100.0% | 100% | 1.0 |
| dota2 | S | clock_nanosleep | hrtimer_nanosleep | 195 | 100.0% | 100% | 1.0 |
| AsyncIOService/ | S | futex | __futex_wait | 195 | 100.0% | 100% | 3.0 |
| VKRenderThread | S | futex | __futex_wait | 195 | 100.0% | 100% | 8.0 |
| [vkcf] Analysis | S | futex | __futex_wait | 195 | 100.0% | 100% | 1.0 |
| SDLAudioP15 | S | futex | __futex_wait | 195 | 100.0% | 99% | 1.0 |
| PulseHotplug | S | futex | __futex_wait | 195 | 100.0% | 99% | 1.0 |
| [vkps] Update | S | futex | __futex_wait | 195 | 100.0% | 99% | 1.0 |
| dota2 | S | epoll_wait | do_epoll_wait | 195 | 100.0% | 99% | 1.0 |
| dota2 | S | poll | do_sys_poll | 195 | 100.0% | 99% | 1.0 |
| PulseMainloop | S | poll | do_sys_poll | 195 | 100.0% | 99% | 1.0 |
| AudioMixer | S | futex | __futex_wait | 195 | 100.0% | 98% | 1.0 |
| mangohud-nvidia | S | clock_nanosleep | hrtimer_nanosleep | 195 | 100.0% | 93% | 1.0 |
| GlobPool/1 | S | futex | __futex_wait | 195 | 100.0% | 79% | 1.0 |
| GlobPool/5 | S | futex | __futex_wait | 195 | 100.0% | 76% | 1.0 |
| GlobPool/2 | S | futex | __futex_wait | 194 | 99.5% | 76% | 1.0 |
| GlobPool/3 | S | futex | __futex_wait | 194 | 99.5% | 76% | 1.0 |
| GlobPool/4 | S | futex | __futex_wait | 194 | 99.5% | 75% | 1.0 |
| GlobPool/0 | S | futex | __futex_wait | 193 | 99.0% | 78% | 1.0 |

### Per-thread-name CPU (threads_cpu.csv)

| thread | cpu% (mean) | samples | threads |
|---|---|---|---|
| AsyncIOService/ | 1329886.14 | 93 | 3 |
| mangohud-nvidia | 918703.74 | 501 | 1 |
| dota2 | 617966.87 | 1129 | 6 |
| AsyncTextureHoo | 376601.94 | 10 | 1 |
| mangohud-hwinfo | 304355.77 | 46 | 1 |
| VKRenderThread | 271203.95 | 1048 | 8 |
| GlobPool/3 | 211418.33 | 431 | 1 |
| GlobPool/2 | 210865.78 | 434 | 1 |
| GlobPool/6 | 207546.11 | 431 | 1 |
| GlobPool/4 | 207077.04 | 431 | 1 |
| GlobPool/5 | 197044.43 | 431 | 1 |
| GlobPool/1 | 196492.29 | 432 | 1 |
| GlobPool/0 | 192700.20 | 428 | 1 |
| Async Pipeline | 151109.92 | 89 | 31 |
| PulseMainloop | 117345.46 | 137 | 1 |


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

