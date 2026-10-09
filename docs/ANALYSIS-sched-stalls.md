# ANALYSIS — scheduler-trace attribution of Dota 2 hitches (run S1)

**Inputs (read-only, main checkout):**
`/tmp/stutter-live/perf-S1.data` (100 s system-wide `sched:sched_switch` +
`sched:sched_waking` trace) and
`runs/live-S1-sched/raw/mangohud/dota2_2026-10-08_22-26-04.csv` (MangoHud
frametimes).

**Tool:** `tools/sched_stall_analysis.py` (reusable; args = perf.data, MangoHud
csv, offset). Full generated report is stored next to this file as
[`ANALYSIS-sched-stalls.report.txt`](./ANALYSIS-sched-stalls.report.txt).

**Reproduce:**

```sh
tools/sched_stall_analysis.py /tmp/stutter-live/perf-S1.data \
  runs/live-S1-sched/raw/mangohud/dota2_2026-10-08_22-26-04.csv 0.0 \
  --game-pid 3838464 --mono-offset 1791395966.6282375 --control 300 --json /tmp/s1.json
```

---

## TL;DR / headline

The hitches are a **stall of the whole Dota process that Dota itself ends**.
During a hitch the **main thread (tid 3838464) is blocked for ~99% of the
frametime** and is woken by **another Dota thread — usually a `GlobPool/N`
worker (Dota's global job pool) or a `VKRenderThread`** — with a wake lag of
**≈0.02 ms**, i.e. a genuine hand-off, not a stray wake.

The only CPU that is actually busy during the stall is **cpu0, running Dota's
own worker threads**: cpu0 is **~85 % busy during hitches vs ~30 % in control**
(`GlobPool/*` and `VKRenderThread` are **5–10× enriched** on cpu0), while
**~92 % of the 32 cores are idle** and *no external* task (nvidia kernel
thread/IRQ, `kwin_wayland`, `pipewire`, a local LLM server, `steamwebhelper`, …) is
enriched. So the OS is handing Dota a nearly idle machine and Dota still
stalls: the bottleneck is **inside Dota (a long single-threaded job / a
synchronization on its job pool), not OS scheduling or external contention.**

**Most likely culprit:** Dota's main thread blocking on its global job
pool / render thread while a single worker performs a long task (up to ~3 s)
on one core. The Linux scheduler is not the cause.

---

## Data provenance, clocks and mapping

* perf window (perf's CLOCK_MONOTONIC): **113480.6368 … 113580.6428 s**,
  = **epoch 1791509447.265 … 1791509547.271** with
  `mono_offset = 1791395966.6282375` (the run's own `mono_offset.txt`).
* MangoHud log: `btime = 1791509164.768330` (statx), `frametime`/`elapsed`
  mapped as `t = btime + elapsed/1e9 + offset`.
* **Mapping validated:** with `offset = 0.0` the mapped epochs reproduce the
  collector's `frametimes.csv` row-for-row to the microsecond over the first
  2 min (e.g. row 1 → 1791509164.823582 in both). The measured residual of
  this mapping is `~+0.0136 s` (from `validate_mangohud_sync`); it is far below
  the smallest hitch and does not change any conclusion.
* **Offset cross-check.** The given `mono_offset` is the right one: shifting
  the MangoHud spikes by it makes **11 frames > 60 ms land inside 9.91 s of
  dota-thread near-silence (2135 dota switch-ins/s inside the stall windows vs
  a 21264/s baseline = 10× depletion)**; using the `perf_start_epoch.txt`
  offset (205 s away) leaves the rate at baseline (22099/s = no signal).
* The perf record started **~200 s after the run's nominal 2-min window**
  (the first `perf record` attempt failed — see `perf-S1.log` — and was retried
  late), so the trace covers *continued idle demo-hero play*, not the
  collector's exact window. The MangoHud log kept growing, so the overlap is
  valid: **11 hitches > 60 ms in the 100 s window (6.6/min**, matching the
  earlier ~10/min idle-demo-hero rate).

Threads of the Dota process (tgid 3838464): main = `dota2`/tid 3838464;
render = 8× `VKRenderThread`; job pool = 7× `GlobPool/0..6`; plus audio
(`SDLAudioP15`, `AudioMixer`, `PulseMainloop`), Steam-engine threads
(`CJobMgr::m_Work`, `CHTTP*`, `IPC:CSteamEngin`), `mangohud-*`, etc.

---

## (a) Per-CPU timeline during hitches

`idle%` = mean fraction of cpu time sleeping (swapper) across all 32 CPUs;
`cpu0idle%` = idle fraction of cpu0; `top_task` = busiest non-idle comm over
all CPUs in the window.

```
     hitch_t   ft_ms  idle% cpu0idle%       cpu0_top busy_cpu           top_task main_block
1791509470.950   317.8   91.1       9.6 VKRenderThread        0         Compositor          -
1791509472.399   201.3   91.9      16.3     GlobPool/0        0         Compositor      195ms
1791509472.655    86.2   89.5      51.5 VKRenderThread        0         Compositor          -
1791509473.235    88.6   90.8      35.6 VKRenderThread        0         Compositor       79ms
1791509483.672  2021.9   92.7       2.3     GlobPool/0        0         GlobPool/0     2017ms
1791509487.305  2957.8   92.9       1.0     GlobPool/6        0         GlobPool/6     2951ms
1791509492.657  1579.7   92.8       2.5 VKRenderThread        0     VKRenderThread     1573ms
1791509501.458   233.5   91.9      17.9     GlobPool/0        0         Compositor      225ms
1791509507.334  1001.6   92.8       4.6 VKRenderThread        0     VKRenderThread      250ms
1791509523.690   519.6   91.7       6.0     GlobPool/2        0         GlobPool/2      512ms
1791509526.137   905.5   92.8       5.0 VKRenderThread        0     VKRenderThread      250ms
```

* **~92 % of all CPUs are idle during every hitch** — more than in control
  (91.9 % vs 89.0 %), i.e. hitches are *not* CPU contention; if anything the
  machine is quieter than normal.
* **cpu0 is the exception**: it is ~99 % busy during the big hitches, and the
  task on it is a **Dota worker** (`GlobPool/*`) or a `VKRenderThread`.
* `top_task` is Dota's own worker in the big hitches. (It is `Compositor`
  = *desktop-app-1*, a background desktop app, in the small hitches; it is *less* busy in
  hitches than control — see below — so it is not a driver.)

**cpu0 breakdown (mean seconds on cpu0 per window, hitch vs the 300 controls):**

```
comm                           hitch_s    ctrl_s   ratio
VKRenderThread                  0.3364    0.0635    5.30
GlobPool/6                      0.2649    0.0358    7.39
GlobPool/0                      0.2090    0.0206   10.17
GlobPool/2                      0.0430    0.0219    1.96
Compositor (desktop-app-1)     0.0056    0.0940    0.06   <- less busy in hitches
dota2                           0.0013    0.0320    0.04
desktop-app-1                   0.0009    0.0139    0.06
...
(cpu0 idle)                     0.1384    0.6300
```

Concatenated `perf script` around the 2.96 s hitch shows cpu0 holding
`GlobPool/6` essentially continuously (runnable, `prev_state=R`), interrupted
only every ~64–128 ms by `kworker/0:1-eve` for a few µs:

```
GlobPool/6 [000] ... prev_comm=GlobPool/6 prev_state=R ==> next_comm=kworker/0:1
kworker/0:1 [000] ... prev_comm=kworker/0:1 prev_state=I ==> next_comm=GlobPool/6
GlobPool/6 [000] ... prev_comm=GlobPool/6 prev_state=R ==> next_comm=kworker/0:1
...
```

---

## (b) Main thread: switch-out that starts the stall, and the waker that ends it

`blk_ms` = length of the main thread's blocked interval; `ovl_ms` = overlap of
that interval with the hitch; `in` = did the block start inside the hitch
window; `lag` = resume-time − waker-time; `chain` = who woke the waker, etc.

```
     hitch_t   ft_ms   blk_ms   ovl_ms  in cpu0idle% out_st            waker wk_cpu    lag                          chain
1791509470.950   317.8 (main not blocked)
1791509472.399   201.3    194.5    150.4   Y      16.3      S       GlobPool/3      4   0.02 GlobPool/4(0) -> GlobPool/0(7)
1791509472.655    86.2     35.2    -61.6   n      51.5      S       GlobPool/0     10   0.02 GlobPool/6(28) -> GlobPool/5(1)
1791509473.235    88.6     78.7     38.3   Y      35.6      S   VKRenderThread     15   0.02
1791509483.672  2021.9   2017.1   1970.1   Y       2.3      S       GlobPool/0      0   0.02
1791509487.305  2957.8   2950.6   2907.6   Y       1.0      S       GlobPool/5     30   0.02                  GlobPool/6(0)
1791509492.657  1579.7   1572.6   1530.3   Y       2.5      S   VKRenderThread     20   0.40
1791509501.458   233.5    224.7    184.0   Y      17.9      S       GlobPool/0     22   0.01 VKRenderThread(1) -> GlobPool/0(22)
1791509507.334  1001.6    250.1    250.1   Y       4.6      S          swapper     26   0.01
1791509523.690   519.6    511.8    467.9   Y       6.0      S       GlobPool/2     31   0.01
1791509526.137   905.5    250.1    250.1   Y       5.0      S          swapper      5   0.01
```

* The main thread always switches out **with `prev_state=S`** (futex/poll —
  matching the D1 "blocked on futex/epoll" report), and its block **≈ the whole
  frametime** (2950.6 ms of a 2957.8 ms hitch).
* **Wake lag ≈ 0.02 ms** → the `sched_waking` is the true end-of-stall wake.
* **Wakers are Dota's own threads:** `GlobPool/*` (7/10) or `VKRenderThread`
  (2/10); only 2/10 are timer/idle-context (`swapper`). The wake chains run
  *within* Dota, e.g. for the 2.96 s hitch: `GlobPool/6` (busy on cpu0) woke
  `GlobPool/5`, which woke the main thread.

**Whole-process, not just main:** during each hitch essentially the whole Dota
thread population is blocked at once — all 8 `VKRenderThread`, all 7
`GlobPool`, the Steam threads and audio — and they resume together (see the
"other threads blocked ≥ 50 % of the hitch" table in the appended report).
For example at the 2.02 s hitch, the 8 render threads (≈2020 ms), the 7
GlobPool workers (≈2017 ms) and audio all sleep simultaneously.

*Caveat:* the "other threads" table also contains fixed-period background
pollers (`dota2`/tid 3838506 sleeps exactly 2000.1 ms; `CJobMgr`/`CHTTP*`
250.1 ms; `SteamEngineWatc` 5000 ms) which are not specific to the hitch.

---

## (c) Control comparison (300 random same-length windows)

```
* cpu idle fraction (all CPUs):  hitch 91.89%   control 88.99%
* dota switch-in rate         :  hitch 5258/s   control 21181/s   (10x depletion)
* cpu0 idle fraction          :  hitch 14.0%    control 63.0%    (cpu0 85% vs 30% busy)
```

Enriched tasks during hitches (wall-normalised share, hitch − control):

```
comm                             hitch%    ctrl%   delta%   ratio
GlobPool/0                        0.797    0.502   +0.295    1.59
VKRenderThread                    1.621    1.508   +0.113    1.07
swapper/*                         ~3       ~2.5    +0.1..0.5 1.05..1.19   (idle, i.e. MORE idle)
```

* The **only non-idle enrichment is Dota's own `GlobPool/0` (+0.30 pp) and
  `VKRenderThread`**; on a per-cpu basis the effect is much larger on **cpu0**
  (5–10×, table in (a)).
* Every other process is flat or *less* busy during hitches — including the
  background apps (`desktop-app-1`, `Compositor`, `user-app-1`, a JS runtime). **No external process or
  kernel thread is enriched.** This is the key negative result: an idle machine
  + a stalling Dota ⇒ not preemption/contention from anything else.

---

## (d) Periodic structure

```
hitch occurrence:  n=11, inter-hitch median 4.49 s, mean 5.52 s, range 0.26–16.4 s;
                   autocorrelation peak 0.25 at 16.35 s (weak).
stall-end times :  n=10, median 5.35 s, range 0.16–16.7 s; AC peak 0.15 at 19.7 s (weak).
```

Boundary events (switch-ins within ±10 ms of hitch **start**): the only
non-trivial lifts are `HeapHelper` (3.7×, 87 vs 23 expected, 10652 events),
`nvidia-powerd` (1.3×, 191 vs 143), `user-daemon-1`/`user-app-1` (1.3×). At stall
**end**: `swapper/31` (2.3×, i.e. a specific CPU going idle), `nvidia-powerd`
(1.5×), `mangohud-hwinfo` (6 hits vs 0.4 expected). None of these is a
plausible *cause* (they are low-volume daemons likely reacting: `nvidia-powerd`
is the GPU power daemon; `mangohud-hwinfo` is our own overlay reading the GPU).

**No ~Hz external driver** (no timer/IRQ/daemon that appears at every stall
boundary); the hitches are **aperiodic**, consistent with on-demand jobs rather
than a periodic external agent.

---

## Ranked conclusion

1. **(strong) The stall is inside Dota and ends inside Dota.** The main thread
   blocks (futex) for ~the whole frametime and is woken by a Dota worker/render
   thread with 0.02 ms lag. Dota ends its own stall.
2. **(strong) It is not OS scheduling or CPU contention.** Hitches have *more*
   idle CPUs than control (91.9 % vs 89.0 %); ~92 % of cores are idle; no
   external task is enriched; the busy core (cpu0) is running **Dota's own**
   `GlobPool`/`VKRenderThread`.
3. **(medium) A single Dota worker executes on one core (cpu0) for the whole
   stall.** cpu0 is 85 % busy (vs 30 % control) with `GlobPool/*`; that worker
   runs ~3 s essentially uninterrupted (only µs preemptions by
   `kworker/0:1-eve`). This is the signature of a **long single-threaded job /
   spin** that fails to use the 31 other idle cores.
4. **(weak) Aperiodic; no external trigger.** No task/IRQ/timer recurs at stall
   boundaries; boundary lifts are small and attributable to bystanders.

**Most likely culprit:** Dota's main thread waiting on its global job
pool/render thread while a worker runs a long task on a single core (up to
~3 s) — an **in-process / driver-internal** stall. **Not** the Linux scheduler,
not CPU contention, not an external daemon.

## Uncertainty / caveats

* The trace has **scheduler events only — no stacks**, so "long job" vs
  "futex spin" vs "Vulkan driver ioctl wait" cannot be separated; the wording
  above reflects that.
* The perf window is **~200 s later than the collector's analysed window**
  (late retry), so this is continued idle demo-hero play, not the exact 2-min
  window.
* The **"cpu0 is the busy core" pattern rests on the two big hitches**
  (2.0 s, 3.0 s) which both landed on cpu0; the small hitches show other cores.
  It may be a coincidence of where the worker was scheduled.
* Background desktop apps and daemons (`desktop-app-1`, `user-app-1`, a JS runtime, container daemons) were running in
  the background; it appears in boundary tables but is **not** enriched during
  hitches (it is less busy), so it is not the driver — but it is noise.
* The 300-control comparison uses random windows of the same *length*
  distribution; with only 11 hitches the enrichment of low-volume comms
  (`HeapHelper`) is not significant.

## Concrete next experiment (to confirm the culprit)

Capture **call stacks**, not just scheduler events, during an idle demo-hero
session:

```sh
# on-CPU stacks of the Dota process during hitches — shows what the busy
# GlobPool/VKRenderThread worker is actually doing for those ~3 s
sudo perf record -F 499 -g -p "$(pgrep -x dota2)" --call-graph dwarf -- sleep 180
sudo perf report --sort comm,dso,sym       # look at GlobPool*/VKRenderThread frames
```

Then, in parallel, run the existing off-CPU sampler
(`bin/stutter collect --deep`, bpftrace `sched_switch` with kstack/ustack) to
capture **what the main thread is blocked on** (futex owner, ioctl, fence) at
the stall. Decision rule:

* stacks show Dota/engine frames (job/lock) → it is a Dota job/lock convoy;
  next, check for a lock-holder: which thread/com of the pool is on cpu0 and
  whether the workers are serialized (e.g. `taskset` the game off cpu0 to see
  if the stall moves with the worker).
* stacks show `libnvidia*` / driver ioctls / `vkWaitForFences` → it is a
  driver/GPU-sync stall, and the fix is on the driver/Proton side.

A cheaper instantaneous cross-check: run
`perf top -C 0 -p <dota2-pid>` (or `-g`) while reproducing, to see which symbol
dominates cpu0 during a hitch.
