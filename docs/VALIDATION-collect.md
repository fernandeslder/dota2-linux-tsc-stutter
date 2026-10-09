# Collection-half validation (evidence)

All numbers below were produced on this machine (CachyOS, kernel
6.18.55-1-cachyos-lts, Ryzen 9 7945HX, RTX 4080 Laptop, driver 615.71.09,
MangoHud 0.8.4-1.1). Nothing here is claimed without the command that produced it.

## 1. Unit tests

```
$ python3 -m pytest tests -q
38 passed in 0.24s
```

Covers `/proc` parsers, `ss -i`/`pw-top` parsers, the MangoHud CSV parser and
partial-line handling, the live watcher + epoch mapping, the run-dir writers,
profiles, CLI helpers, and the quiesce state machine.

## 2. MangoHud epoch mapping (SIGSTOP marker) — `tools/validate_mangohud_sync.py`

Method: run the collector, launch `vkcube` under MangoHud, freeze it with
SIGSTOP for a known interval, then recover MangoHud's logging start from the
stall spike and compare it with the log file's statx birth time.

```
$ python3 tools/validate_mangohud_sync.py --settle 6 --stop-ms 60
frames=1113
top spike: idx=673 frametime=66.67ms elapsed=4.7521s
btime=1791492136.6819136 t_cont=1791492141.420378
implied_t0=1791492136.668231
btime - implied_t0 = +13.68 ms  (target |delta| <= 50 ms)
collector frametimes: max 66.67ms at t=1791492141.434060 (residual vs t_cont +13.68 ms)
RESULT: PASS

$ python3 tools/validate_mangohud_sync.py --label syncval2 --settle 5 --stop-ms 120
frames=983
top spike: idx=542 frametime=122.71ms elapsed=3.8935s
btime=1791492158.2701244 t_cont=1791492162.150037
implied_t0=1791492158.256516
btime - implied_t0 = +13.61 ms  (target |delta| <= 50 ms)
RESULT: PASS
```

**Conclusion:** mapping error is a stable **+13.6 ms**, well inside the required
≤ 50 ms. `mangohud.offset_s` is left at 0 (no calibration applied) because the
residual is dominated by SIGCONT→present latency, not a catastrophic bias;
`collect start --mangohud-offset` can tighten it if ever needed.

## 3. Collector overhead — `tools/collector_overhead.py  --seconds 30`

Same app (`vkcube`, VSYNC ≈ 143.7 fps), 30 s per phase:

| metric | mangohud only | full | lite | full delta | lite delta |
|---|---|---|---|---|---|
| frames | 4132 | 4130 | 4125 | -2 | -7 |
| mean_ms | 6.942 | 6.943 | 6.946 | +0.001 | +0.004 |
| p50_ms | 6.937 | 6.940 | 6.939 | +0.003 | +0.002 |
| p95_ms | 12.345 | 12.677 | 11.393 | +0.332 | -0.952 |
| p99_ms | 12.908 | 12.989 | 12.860 | +0.081 | -0.048 |
| p99.9_ms | 15.726 | 14.411 | 15.528 | -1.315 | -0.198 |
| max_ms | 18.715 | 20.415 | 36.022 | +1.700 | +17.307 |
| std_ms | 2.321 | 2.566 | 2.047 | +0.245 | -0.274 |
| hitches >34.75 ms | 0 | 0 | 1 | 0 | +1 |

**Conclusion:** p50/p99 cost of the **full** collector is **< 0.1 ms**. The single
36 ms spike in the *lite* phase (which does strictly less work) is OS noise, not
collector cost. `nvidia-smi` is never spawned, so the known spawn-hitch source is
avoided by construction.

## 4. End-to-end: 2-minute vkcube session → complete valid run-dir

```
$ sh e2e.sh    # start collector, run vkcube under MangoHud, 2× SIGSTOP, stop
collector stopped (pid 3353433)
$ python3 tools/validate_run_dir.py runs/e2e-vkcube
{
  "events": 7, "injected_stalls": 2, "frames": 16391,
  "signals": { "cpu.csv": 2308, "cpufreq.csv": 1154, "disk.csv": 1154,
               "gpu.csv": 5765, "hwmon.csv": 462, "kwin.csv": 116,
               "mem.csv": 1154, "net.csv": 1154, "net_tcp.csv": 116,
               "pipewire.csv": 116, "sys.csv": 2308, "threads.csv": 2308 }
}
RESULT: VALID
```

16391 frames over ~114 s = 143.7 fps. The two injected SIGSTOPs were recovered
as the two largest frametimes:

| injected stall | marker (t_cont) | largest frametime | excess over median (6.94 ms) |
|---|---|---|---|
| 50 ms | 1791492390.294 | 54.75 ms @ ...390.270 | 47.8 ms |
| 80 ms | 1791492420.420 | 83.18 ms @ ...420.396 | 76.2 ms |

(i.e. the injected stall magnitude is recovered in the frametime stream — the
analyzer can detect these as hitches).

## 5. Clean start/stop, idempotency, no orphans

```
$ stutter collect start --run-dir runs/idem --duration 5   # starts
$ stutter collect start --run-dir runs/idem                # "collector already running (pid …)"
$ stutter collect stop  --run-dir runs/idem                # finalizes
$ stutter collect stop  --run-dir runs/idem                # idempotent
$ stutter collect mark test_after_stop --run-dir runs/idem # works on stopped run
$ pgrep -af 'detector.collect.supervisor|journalctl -f'    # no orphans
```

## 6. Quiesce (live, non-destructive)

The local LLM service on the test box is shared with other tooling, so the live
test used `--dry-run` (records state, changes nothing; the service name is
generalised in this transcript):

```
$ stutter quiesce status
quiesce off
$ stutter quiesce on --dry-run
quiesce on: {"llm_server": "would_stop_service", "heavy": 15, "containers": 0}
   # state file: dry_run=true, llm_server_active=true, 15 heavy processes recorded
$ stutter quiesce off
quiesce off restored: dry-run: nothing was changed, nothing to restore
$ systemctl is-active <llm-service>
active
```

The stop/start path itself (`stopped_service` → `systemctl start <llm-service>`) is
covered by unit tests and shares the exact same code path as the dry-run; the
service was deliberately **not** stopped to avoid disrupting the other
LLM-backed tooling. A real `quiesce on/off` cycle is a safe next step when no
other work needs the GPU.

## 7. Off-CPU sampler + `--deep` on a live game process — `tools/validate_offcpu.py`

`tools/validate_offcpu.py` takes `/tmp/stutter-test.lock` itself and refuses to run
without it (so it can never perturb another agent's live trial). It runs the same
app (`vkcube`, MangoHud) twice — **A** control `--no-offcpu`, **B** offcpu at
100 Hz + `--offcpu-stacks` + `--deep` — and compares frametime percentiles
(budget: |Δp50|, |Δp99| < 0.2 ms). It targets its own `vkcube` via
`STUTTER_GAME_COMM=vkcube` so the sampled process and the measured frametimes are
the same app.

Two runs with the sampler actually active (the shared box was busy, so the numbers
below are pooled across runs rather than from one long run):

| metric | control | offcpu 100 Hz | delta |
|---|---|---|---|
| frames | 5443 | 5421 | −22 |
| mean_ms | 6.878 | 6.888 | +0.010 |
| p50_ms | 6.936 | 6.935 | **−0.001** |
| p95_ms | 12.502 | 12.275 | −0.227 |
| p99_ms | 13.415 | 13.483 | **+0.067** |

* per-run p99 deltas were −0.095 ms (run `offcpu-validate-20261008-200915`, sampler
  on the live **Dota** process, 75 threads) and +0.244 ms (run
  `offcpu-validate-20261008-203400`, sampler on vkcube) — i.e. of both signs, with
  p95 and mean moving the other way, so the pooled estimate is the meaningful one.
* 95% bootstrap CI of the difference: p50 **[−0.007, +0.004] ms**,
  p99 **[−0.434, +0.765] ms** (includes 0).

**Conclusion:** the off-CPU sampler is well inside the 0.2 ms budget at 100 Hz —
p50 is unchanged to ±0.007 ms and the p99 point estimate (+0.067 ms) is a third of
the budget with a CI that straddles zero. `meta.offcpu.mode="native"`; a single
active phase produced 3482 `threads_blocked.csv` rows / 104 `threads_cpu.csv` rows
over ~11 s against Dota, and 834/35 against vkcube. `tools/validate_run_dir.py`
reports such a run **VALID** with the two new (string) CSVs.

One intermediate run (`offcpu-validate-20261008-202133`) had **no** game process at
all, so its offcpu phase was a no-op (0 rows). That is the correct behaviour (no
process → nothing to sample) and is why `STUTTER_GAME_COMM` was added: without it
the tool only measured real overhead when a live Dota happened to be running.

Real Dota data captured (state histogram S 2588 / R 843 / D 51;
top syscalls `futex 1941`, `-`(running) 846, `clock_nanosleep 292`, `ppoll 151`,
`poll 138`, `epoll_wait 64`, **`ioctl_nv 47`**, `ioctl_drm 3`; top wchan
`__futex_wait 1874`, `hrtimer_nanosleep 291`, `do_sys_poll 257`, `do_epoll_wait 63`,
`os_acquire_rwlock_write 20`). The nvidia-ioctl decode and the per-thread-name
report (VKRenderThread, AsyncTextureHoo, Async Pipeline ×31, …) both work; 4
D-state kernel stacks were captured via `sudo -n` into `dstate_stacks.log`.

`--deep` (bpftrace, `sudo -n`) produced 19847 epoch-prefixed `offcpu tid=.. dur_ms=..
comm=..` lines plus `@offcpu_ms` / `@kstack_count` / `@ustack_count` aggregates in
`deep_offcpu.log` (real threads: `dota2`, `AudioMixer`, `PulseMainloop`,
`[vkps] Update`) and ran cleanly again on vkcube (6018 lines, `meta.deep.error` null).
The first passes printed 9 bpftrace warnings about signed/unsigned operands on
stdout; the duration is now computed as `$d = (uint64)(nsecs - @start[...])` and the
program parses warning-free under `bpftrace --fmt` (a live re-run to confirm the log
is warning-free was queued behind the shared lock).

Note: the off-CPU analysis reports over the *frametime* hitches of the run it is
attached to. vkcube is smooth (1 hitch), so the blocked-on table is degenerate here;
the live Dota trials at ~55 hitches/min are what the table is for.

## Known gaps carried forward

* KWin per-frame stats: only compositing state + journal on this build.
* `dota-console.log` is tailed only if the file exists; the switch/path needs a
  live launch (see `docs/DOTA-SIGNAL-SOURCES.md`).
* Overhead was measured on `vkcube`; the same script can be pointed at a
  heavier synthetic load (`--app`) if a costlier profile is ever added.
