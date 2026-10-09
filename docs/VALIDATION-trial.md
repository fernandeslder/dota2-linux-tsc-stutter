# Trial-tooling validation (evidence)

Scope: `detector/trial/` + the `preflight` / `launchopts` / `trial` subcommands of
`bin/stutter`. All numbers below were produced on this machine (CachyOS, kernel
`6.18.55-1-cachyos-lts`, Ryzen 9 7945HX, RTX 4080 Laptop, driver `615.71.09`,
MangoHud 0.8.4). Nothing here is claimed without the command that produced it.

**No Dota 2 was launched, no real Steam config was modified, and no GUI was driven.**
The wrapper was exercised end-to-end with `vkcube` standing in for the game.

## 1. Unit tests

```
$ python3 -m pytest tests -q
84 passed in 6.4s
```

The trial half adds 43 tests (`tests/test_trial_{vdf,steam,launchopts,cli,runner}.py`)
covering: VDF parse/escape/comment handling, surgical single-line set, insert, delete,
binary-VDF rejection, malformed input, quote round-trips; Steam account selection (prefer
the account that actually sets `LaunchOptions`), explicit `--account`/`--vdf`, backup +
verify + restore, refusal while Steam runs, dry-run; the launch-string builder
(native forces `-vulkan` once, Proton does not; MangoHud config has `fps_only=0`,
`autostart_log=1`, `log_duration=0`); CLI arg handling and dispatch; and runner helpers
(`find_processes` skips wrappers and zombies, incremental `FrameCounter`, window aborts,
scoped `cleanup`).

## 2. `preflight` (read-only)

```
$ ./bin/stutter preflight
[PASS] nvidia-gpu        NVIDIA GeForce RTX 4080 Laptop GPU, driver 615.71.09
[PASS] vulkan-device     Dota would use: NVIDIA GeForce RTX 4080 Laptop GPU (PHYSICAL_DEVICE_TYPE_DISCRETE_GPU, driverID DRIVER_ID_NVIDIA_PROPRIETARY)
[WARN] nvidia-clocks     pstate P0, sm 2460/3105 MHz, throttle 0x…, persistence Disabled, clock-lock SUPPORTED; persistence disabled (first-use clock ramp may add latency)
[PASS] nvidia-powerd     active
[WARN] llm-server        active, 1 model(s) loaded: <model> (GPU competitor; use `stutter trial run --quiesce`)
[WARN] containers        4 running: container-1, container-2, container-3, container-4 (CPU/IO competitors)
[PASS] steam             running (pids …)
[PASS] mangohud          0.8.4-1+; Vulkan layer present
[PASS] dota              installed at …/dota 2 beta; LaunchOptions="LD_PRELOAD=\"\" SDL_AUDIODRIVER=pulseaudio %command% -vulkan -threads 8 -high -novid -map dota -nojoy +fps_max 144"
[PASS] display           2560x1440@144 (144 Hz), VRR=incapable, compositing=on
[PASS] cpu-governor      governor=performance, EPP=performance
[PASS] platform-profile  performance (…)
[PASS] disk              514.6 GiB free on the runs filesystem
[PASS] versions          kernel 6.18.55-1-cachyos-lts, NVIDIA driver 615.71.09
[PASS] ac-power          AC online; BAT0=Full
SUMMARY: 12 PASS, 3 WARN, 0 FAIL
```

Service, container and model names in the transcript above are generalised (the local LLM server check is named after the server's own service in the real tool); the display connector name is omitted.

Exit code 0 (no FAIL). The AC check is the one deliberate hard failure on a laptop; with
AC online it is PASS.

## 3. `launchopts` against the real Steam data (read-only)

The real config is account **STEAMID** (it is the one that sets `LaunchOptions`).

```
$ ./bin/stutter launchopts --get
LD_PRELOAD="" SDL_AUDIODRIVER=pulseaudio %command% -vulkan -threads 8 -high -novid -map dota -nojoy +fps_max 144

$ ./bin/stutter launchopts --build --mangohud --base '-threads 8 +fps_max 144'
native:  LD_PRELOAD="" MANGOHUD=1 MANGOHUD_CONFIGFILE=…/runs/mangohud-manual/mangohud.conf %command% -threads 8 +fps_max 144 -vulkan
proton:  LD_PRELOAD="" MANGOHUD=1 MANGOHUD_CONFIGFILE=…/runs/mangohud-manual/mangohud.conf %command% -threads 8 +fps_max 144
wrapper: MANGOHUD_CONFIGFILE=…/runs/mangohud-manual/mangohud.conf mangohud %command% -threads 8 +fps_max 144 -vulkan
```

The VDF editor was also run against **copies** of both real account files: setting
`LaunchOptions` on the 90 180-byte `STEAMID` file changed **exactly one line** and left
the other 1623 lines byte-identical; on the `1603832975` file (a `570` node with no
`LaunchOptions`) it inserted the key at the same indentation as its siblings. The real
files were never written (Steam was running; a write there is not part of this validation).

## 4. End-to-end wrapper with `vkcube`

```
$ ./bin/stutter trial run --label vkcube-e2e --minutes 0.3 --warmup 1 \
      --wait-process vkcube --launch vkcube --no-plots --timeout 60
collector started: pid=3418455 profile=full
run_dir: runs/20261008-180603-vkcube-e2e
mangohud config: runs/20261008-180603-vkcube-e2e/raw/mangohud.conf
[trial] launching (dev): vkcube
[trial] vkcube up (pids [3416819, …]), 7 frames flowing
marked 'match_loaded' … marked 'warmup_end' …
[trial] recording 0.3 min window (heartbeat each minute)
marked 'window_end' …
collector stopped (pid 3418455)
… frametimes.csv: 2766 rows; gpu.csv: 1282; cpu.csv: 515; …
=== trial verdict: 20261008-180603-vkcube-e2e ===
window:   0.3 min (warm-up source: mark), 2597 frames
hitches:  8 (26.56/min), worst 38.6 ms, median 20.5 ms, low-tier 13
lows:     1% 58.3 fps, 0.1% 34.6 fps, mean 143.7 fps
periodic: no (kind=aperiodic)
sparse:   insufficient-window
fixed:    FAIL (PROVISIONAL thresholds)
EXIT=0
```

(A `vkcube` run is not a Dota baseline — the 8 hitches are Vulkan/MangoHud startup noise —
but it proves the whole pipeline: run-dir contract, all samplers, marks, `detect`, `report`,
verdict.)

## 5. Abort paths

| path | command | result |
|---|---|---|
| kill the game mid-window | `pkill -x vkcube` ~8 s into a 2-min window | `ABORTED: game process 'vkcube' died during the window (frames=893)`, exit **2**, collector stopped |
| Ctrl-C / SIGTERM | `kill -INT <runner-pid>` ~8 s in | `ABORTED: interrupted by signal 2`, exit **2**, `quiesce status` → `off` |
| never appears | `--timeout 0` with no process | `timeout after 0s: process … never appeared`, clean give-up |

After each: `pgrep -ax 'vkcube|detector.collect.supervisor'` shows no collector/dead-game
process of ours (an unreaped zombie is skipped by `find_processes` and reaped on exit).

## 6. `cleanup` scoping (shared machine)

Orca runs several worktrees of this project side by side, and another agent had a live
collector under `…/dota2-fix/e2e-validate`. Verified:

```
$ ./bin/stutter trial cleanup
[cleanup] stopped collector (cleantest) pid 3441472
[cleanup] clean: no collectors, mangohud loggers, or quiesce state remain
# the e2e-validate worktree's supervisor was NOT touched (its cwd/argv is outside this repo)
```

`cleanup` matches supervisors by an **exact argv token** (`-m detector.collect.supervisor`)
and scopes every candidate by `cwd`/argv to this worktree, so a shell whose command string
merely mentions the marker is never killed.

## Known gaps carried forward

* **Live Dota 2 numbers are still owed** (run-to-run variance, final K/FLOOR, the real
  "fixed" thresholds): the wrapper is validated on `vkcube`; a GUI-driving agent must run
  the Dota baseline x3 (spec Validation c) using `docs/TRIAL-PROCEDURE.md`.
* **A real `launchopts --set/--restore` cycle was not performed** on the live config
  (Steam running, shared box); it is covered by unit tests on synthetic Steam trees plus
  surgical-edit tests on copies of the real file.
* `nvidia-smi` reports "Applications Clocks: deprecated" on this driver, so `preflight`
  reports pstate / current-vs-max clocks / `-lgc` support rather than a definitive
  "locked" flag (no consumer-card query exposes the lock state directly).
* KWin per-frame stats are still not exposed (collector-only limitation).
