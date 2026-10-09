# Data collection — `stutter collect` / `stutter quiesce`

Implementation of the collection half of `docs/SPEC-detector.md`. Python 3
stdlib + `pynvml`; POSIX `sh` glue in `bin/stutter`.

```
detector/collect/
  cli.py          `stutter collect start|stop|mark|status`
  supervisor.py   one process, one clock; owns every sampler thread + child
  mangohud.py     MangoHud config, launch options, live CSV tail, epoch sync
  rundir.py       run-dir contract writers (meta/events/csv/logs)
  profiles.py     `full` and `lite` sampler sets + rates
  quiesce.py      `stutter quiesce on|off|status`
  env.py          host/driver/kernel metadata
  util.py         clock, statx birth time, /proc parsers, nice/ionice/affinity
  deep.py         optional bpftrace off-CPU/sched-switch profile (`--deep`)
  collectors/     the samplers (procfs, nvidia, threads, hwmon, subproc, offcpu)
```

## Usage

```sh
# start a run (writes runs/<id>/, prints the Steam launch options to use)
./bin/stutter collect start --label mytest [--profile full|lite] \
    [--game-pid N] [--duration SECONDS] [--run-dir PATH] \
    [--no-offcpu] [--offcpu-hz 100] [--offcpu-stacks] [--offcpu-no-native] [--deep]

# launch the game with the printed MANGOHUD_CONFIGFILE option, then:
./bin/stutter collect mark match_loaded --detail "gameid=..."
./bin/stutter collect mark warmup_end
./bin/stutter collect stop

# inspect
./bin/stutter collect status [--run-dir PATH]
python3 tools/validate_run_dir.py runs/<id>
```

`detect` / `report` / `compare` / `selftest` are dispatched to
`detector/analyze/` when that package exists (see `bin/stutter`).

## One clock

Every row's `t_epoch` is `CLOCK_REALTIME` seconds (float). The supervisor and
all samplers call `util.epoch()`; nothing uses relative uptime except inside a
sampler (where it is converted immediately).

### MangoHud relative → epoch mapping

MangoHud logs a monotonic `elapsed` in **ns** since logging started. We anchor it
with the log file's **statx birth time** (`stx_btime`, ns):

```
t_epoch(frame) = btime_epoch + elapsed_ns/1e9 + offset_s
```

* `btime_epoch` is taken from the MangoHud log as soon as it appears (the log is
  written live, so it appears within a second of capture start).
* `offset_s` defaults to `0`; `collect start --mangohud-offset` exists to apply a
  calibration if a machine shows a constant bias.
* **Measured accuracy: +13.6 ms, stable** across two SIGSTOP injections (50 ms
  and 120 ms stalls) — well inside the 50 ms budget. See
  `docs/VALIDATION-collect.md` and `tools/validate_mangohud_sync.py`.

## Signals collected

Rates are the `full` profile; `lite` lowers them and drops the subprocess
samplers. Every `<name>.csv` has header `t_epoch,<cols...>`.

| file | sampler | full rate | contents |
|---|---|---|---|
| `frametimes.csv` | mangohud | per frame | `t_epoch,frametime_ms` |
| `gpu.csv` | NVML | 50 Hz | util, clocks, power, temp, VRAM, pstate, throttle bitmask, PCIe, enc/dec |
| `cpu.csv` | `/proc/stat` | 20 Hz | per-core util (32) + average |
| `cpufreq.csv` | cpufreq | 10 Hz | per-core `scaling_cur_freq` |
| `sys.csv` | procfs | 20 Hz | PSI cpu/io/mem (avg10+total), ctxt/intr/fork rates, procs_running/blocked, loadavg |
| `mem.csv` | meminfo+vmstat | 10 Hz | used/available/cached/dirty/writeback/slab, swap, pgmajfault/pswp/pgscan/allocstall rates |
| `disk.csv` | diskstats | 10 Hz | per-disk read/write MB/s + IOPS + busy % |
| `net.csv` | `/proc/net/dev` | 10 Hz | per-iface rx/tx Mbps, pps, error/drop deltas |
| `net_tcp.csv` | `ss -tin` | 1 Hz | retransmitted segs, sockets retransmitting, rtt max/p50, cwnd, Dota/Steam-port subset |
| `threads.csv` | `/proc/<pid>/task/*/stat` | 20 Hz | game pid, nthreads, proc CPU %, main-thread %, busiest thread tid/CPU%/core/CCD, rss |
| `threads_blocked.csv` | offcpu (`/proc/<pid>/task/*/{stat,wchan,syscall}`) | 100 Hz scan | per-thread **blocked-on**: `t_epoch,tid,comm,state,syscall,wchan` (transition log) |
| `threads_cpu.csv` | offcpu | 1 Hz | per-thread `cpu_pct` by tid/name |
| `dstate_stacks.log` | offcpu (`--offcpu-stacks`) | D-state only | `<t_epoch> tid=.. comm=.. wchan=.. \| <kernel frames>` (sudo -n, rate-limited) |
| `deep_offcpu.log` | deep (`--deep`) | per >5 ms off-CPU interval | epoch-prefixed bpftrace off-CPU lines with kernel+user stacks |
| `hwmon.csv` | hwmon + RAPL + battery | 4 Hz | k10temp Tctl/Tccd, NVMe temps, RAPL pkg/core W, battery W/% |
| `pipewire.csv` | `pw-top -b` | 1 Hz | xrun total/delta, node count, max busy |
| `kwin.csv` | `qdbus6` | 1 Hz | compositing active |
| `journal.log` | `journalctl -f -o short-unix` | live | all journal (epoch-prefixed) |
| `kwin.log` | `journalctl -t kwin_wayland` | live | KWin lines |
| `pipewire.log` | `journalctl -u pipewire…` | live | PipeWire/WirePlumber lines |
| `dmesg.log` | `journalctl -k` | live | kernel log |
| `dota-console.log` | file tail | live | Dota `console.log` **if** present (see DOTA-SIGNAL-SOURCES.md) |

`raw/` keeps untouched upstream data: `raw/mangohud/*.csv`, `raw/net_tcp_ss.log`.
Dynamic-column samplers (disk/net/hwmon) discover their columns in `prepare()`
and the CSV writer is created after that, so headers always match rows.

## Profiles

* **full** — everything above; GPU/CPU at 20–50 Hz. For short diagnostic runs.
* **lite** — no subprocess samplers (`net_tcp`, `pipewire`, `kwin` off), slower
  procfs/NVML rates. For long live proofs where overhead must be negligible.

Overhead measured with `tools/collector_overhead.py` (vkcube ≈143 fps, 30 s per
phase): **p50/p99 frametime deltas < 0.1 ms** with the full profile; one 36 ms
outlier appeared in the lite phase and is OS noise, not collector cost. See
`docs/VALIDATION-collect.md`.

## Off-CPU: what the threads are blocked on

`collectors/offcpu.py` answers "what are the game's threads blocked on during a
hitch". It reads `/proc/<pid>/task/<tid>/{stat,wchan,syscall}` for every thread at
`--offcpu-hz` (default **100 Hz**) and writes `threads_blocked.csv`
(`t_epoch,tid,comm,state,syscall,wchan`) — nvidia ioctls are told apart from other
ioctls (`ioctl_nv` / `ioctl_drm` / `ioctl`) via the ioctl magic byte, and syscalls
are decoded with a table (futex, poll, epoll_wait, read, write, nanosleep,
clock_nanosleep, …).

* The CSV is a **transition log**: a row is written only when a thread's
  `(state, syscall, wchan)` changes, plus a keepalive row every `keepalive_ms`
  (1000 ms full / 2000 ms lite). A row holds until the thread's next row (or the
  run end), so it is ~50x smaller than a full 100 Hz dump while losing no interval
  boundaries. `detector/analyze/blocked.py` rebuilds interval coverage from it.
* Reading ~225 `/proc` files per tick costs ~3.3 ms in Python (>30% of a core), so
  a tiny C helper (`collectors/offcpu_sampler.c`, built with `cc` on first use) is
  used by default; `--offcpu-no-native` forces the Python fallback on hosts without
  a compiler. Both produce byte-identical formats and the mode is recorded in
  `meta.offcpu`.
* `--offcpu-stacks` additionally captures `/proc/<tid>/stack` for **D-state**
  threads only (`sudo -n`, at most 2/s, same `(tid, wchan)` cached 5 s) into
  `dstate_stacks.log`; it disables itself if passwordless sudo is unavailable.
* Setting `STUTTER_GAME_COMM=<name>` overrides game discovery by process name, so a
  non-Dota app launched *after* the collector starts can be sampled — this is how
  `tools/validate_offcpu.py` points the sampler at its own `vkcube` (the app's comm,
  and its `argv[0]` basename as a fallback).

`--deep` is an **optional** root-mode complement: `deep.py` runs
`sudo -n bpftrace` with a `sched:sched_switch` program that records, for every
thread of the game process, each off-CPU interval longer than 5 ms with kernel and
user stacks, aggregated by thread name. `bpftrace`'s `nsecs` is CLOCK_MONOTONIC, so
the reader thread converts it to epoch seconds and writes `deep_offcpu.log` with
`<t_epoch>` prefixes (run-dir `<name>.log` contract).

## Priority, affinity, and no-orphan guarantees

* The supervisor re-nices itself to `nice 19` and `ioprio idle` at start.
* With `affinity: avoid-game` (default), once a game process is found it reads the
  game's allowed CPU set and pins the collectors to the complement (only when
  that is a strict, non-empty subset). Re-evaluated every 5 s.
* The supervisor owns all children (`journalctl`, `ss`, `pw-top`, `qdbus6`,
  `vkcube` is external). On SIGTERM it stops log tailers, joins sampler threads,
  final-flushes every file, writes end metadata and exits — no orphan processes.
* `collect start` is idempotent (refuses to double-start a live run);
  `collect stop` is idempotent (finalizes once, then no-ops).

### CCD topology note

On this 7945HX the L3 groups are `cpu 0-15 = CCD0`, `cpu 16-31 = CCD1`
(verified via `/sys/devices/system/cpu/cpu*/cache/index3/shared_cpu_list`). This
**differs** from the older `taskset -c 0-7,16-23` assumption in
`docs/HISTORY-triage.md`. `threads.csv:busiest_ccd` uses the real L3 map.

## `stutter quiesce`

```sh
./bin/stutter quiesce on [--run-dir D] [--pause-containers] [--dry-run]
./bin/stutter quiesce off [--run-dir D] [--rewarm]
./bin/stutter quiesce status
```

`on` records and then neutralises load that competes with the game:

* **Local LLM server** — (the implementation currently looks for an `ollama`
  service) records whether the service is active/enabled and which models are
  loaded, then stops the service (or unloads the models if the service was not
  the unit). A resident LLM server is a potential GPU competitor.
* **Heavy processes** — top CPU consumers (+ GPU users via NVML) are recorded and
  listed. Not killed.
* **Containers** — `docker stats` snapshot; only those measurably busy
  (CPU ≥ 5 %) are recorded, and only paused with `--pause-containers`.

`--dry-run` records the state (and what *would* be stopped) but changes nothing —
use it to inspect, or when the LLM service is shared with other work.

State is written to `runs/.quiesce-state.json` (and copied into the run dir as
`quiesce-state.json`). `off` restores **only what it recorded**: restarts the
LLM service if it was active, unpauses containers it paused. It will not
start the service if it was inactive. `--rewarm` additionally re-loads the models
that were loaded before, by re-running them (best effort; models otherwise load on
demand).

## Known gaps / not done here

* KWin per-frame stats are not exposed by a stable call on this build; the
  collector captures the KWin journal stream and compositing state only.
* `dota-console.log` is only tailed if the file exists (see DOTA-SIGNAL-SOURCES.md
  for what still needs a live launch).
* `nvidia-smi` is deliberately never spawned; if NVML is unavailable the `gpu`
  sampler is skipped and recorded in `meta.collector_skipped`.
* MangoHud's boundary: the first frame is anchored at logging start, which is
  ~1 s after the app process starts (MangoHud init), so launch-relative marks
  (`game_launched`) come from `collect mark`, not from the frametime stream.
