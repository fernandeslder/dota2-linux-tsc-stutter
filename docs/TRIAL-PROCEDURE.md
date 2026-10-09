# Trial procedure — the exact steps a GUI-driving agent follows

This is the runbook for producing **one live Dota 2 trial**. The wrapper
(`stutter trial run`) does the sequencing, marking, analysis and cleanup; the agent
does the **GUI part only** (launch the game, load into a match, watch a timer) and
captures screenshots as evidence. Nothing here launches Dota by itself.

> Read [`docs/README-detector.md`](README-detector.md) → "Trial" for the command
> reference, and [`docs/DETECTOR-COLLECT.md`](DETECTOR-COLLECT.md) for what the
> collectors record.

---

## 0. Preconditions (do these first)

```sh
# 1. machine is ready — no FAIL lines. AC must read "AC online".
./bin/stutter preflight

# 2. nothing left over from a previous attempt
./bin/stutter trial cleanup

# 3. know which launch options are under test (record them; do not edit Steam by hand)
./bin/stutter launchopts --get
```

* **AC unplugged is a hard FAIL** (this is a laptop; battery changes the power/clock
  budget). Plug in before starting.
* If you will change Dota's launch options for this trial, use the tool, never the
  Steam UI (it rewrites the file on quit and a hand-edit is silently lost):
  ```sh
  ./bin/stutter launchopts --steam-shutdown        # quit Steam so the write sticks
  ./bin/stutter launchopts --set "<string>"
  ./bin/stutter launchopts --get                   # verify
  # ... start Steam again, run the trial ...
  ./bin/stutter launchopts --restore <backup>      # put it back afterwards
  ```
  Every write backs the file up under `ledger/backups/` first.

## 1. Pin the run-dir and start the trial

Pin `--run-dir` so the screenshot paths below are known up front.

```sh
./bin/stutter trial run \
    --run-dir runs/GUI-baseline \
    --label baseline \
    --minutes 15 \
    --warmup 60 \
    --quiesce \
    --profile lite
```

* `--quiesce` stops a local LLM server's GPU models and pauses measurably-busy containers for the
  duration; `cleanup`/the `finally` always restores exactly what it changed.
* `--warmup 60` gives the agent a full minute to get from the main menu into the match
  (warm-up starts the moment frames flow — i.e. at the menu).
* `--profile lite` for final proofs (negligible overhead); `full` for diagnosis.

The command **blocks** and prints progress. It does not launch Dota.

## 2. Launch Dota 2 (GUI)

* Steam → Dota 2 → **Play**. (Steam must be running; `preflight` checks this.)
* 📸 **Screenshot 1** → `runs/GUI-baseline/gui/01-steam-play.png`
  (Steam library with the Play button, so we can see the app is the right one).

The wrapper is waiting for the `dota2` process and the first MangoHud frames. When they
appear it prints `dota2 up (pids …)` and marks `match_loaded`.

## 3. Load into a match (GUI)

* Get into the game state you are measuring — a **live spectate** match (the baseline
  protocol) or a bot match, per the trial plan.
* Wait until the map is fully loaded and frames are clearly rendering.
* 📸 **Screenshot 2** → `runs/GUI-baseline/gui/02-match-loaded.png`
  (the in-game state, so the window clearly corresponds to a loaded match).
* The wrapper prints `[trial] recording 15.0 min window (heartbeat each minute)` after
  warm-up; from then on it logs one heartbeat per minute:

  ```
  [trial] heartbeat 1.0/15.0 min, frames=8712
  [trial] heartbeat 2.0/15.0 min, frames=17423
  ...
  ```

* **Do not touch anything else.** Do not alt-tab, do not open overlays — every action
  lands in the frametime stream and the correlation tables.

## 4. End of window (automatic)

At the end of `--minutes` the wrapper: marks `window_end` → `collect stop` →
`quiesce off` → runs `detect` + `report` → prints the verdict:

```
=== trial verdict: GUI-baseline ===
run_dir:  .../runs/GUI-baseline
window:   15.0 min (warm-up source: mark), 129640 frames
hitches:  3 (0.20/min), worst 41.2 ms, median 18.1 ms, low-tier 12
lows:     1% 118.4 fps, 0.1% 91.0 fps, mean 143.8 fps
periodic: no (kind=aperiodic)
sparse:   no
fixed:    FAIL (PROVISIONAL thresholds)
```

* 📸 **Screenshot 3** → `runs/GUI-baseline/gui/03-verdict.png` (the terminal with the
  verdict, so the run id and numbers are provable).

## 5. Fail-safes (what the wrapper does if something goes wrong)

| situation | wrapper behaviour |
|---|---|
| Dota never starts / no frames within `--timeout` | clean give-up with the reason, exit 2, nothing left running |
| the game process dies mid-window | aborts with `game process 'dota2' died …`, still stops + quiesces, exit 2 |
| frames stop for > 10 s | aborts with `MangoHud frames stopped …`, exit 2 |
| **Ctrl-C / SIGTERM** | aborts, and the cleanup handlers still `collect stop` + `quiesce off`, exit 2 |

In every failure case you still get a partial run-dir and a verdict for the frames that
existed, plus a printed reason. Follow up with `./bin/stutter trial cleanup`.

## 6. After the run

```sh
./bin/stutter trial cleanup                 # guarantees a clean machine
python3 tools/validate_run_dir.py runs/GUI-baseline   # optional contract check
```

Artifacts to hand back (all under the run-dir):

| path | what |
|---|---|
| `runs/GUI-baseline/meta.json` | launch options under test, git rev, kernel, driver, profile |
| `runs/GUI-baseline/events.csv` | marks: `run_start`, `match_loaded`, `warmup_end`, `window_end`, heartbeats |
| `runs/GUI-baseline/out/verdict.json` | the machine-readable verdict |
| `runs/GUI-baseline/out/report.md` | human-readable report |
| `runs/GUI-baseline/out/*.png` | frametime trace, hitch timeline, interval histogram, spectrum, correlation panel |
| `runs/GUI-baseline/gui/*.png` | the agent's screenshots (steps 2, 3, 4) |

## Anti-flakiness checklist

* One trial per boot when possible; if you run several, `trial cleanup` between them.
* Do not run two collectors at once (they share the repo `runs/` dir and the CPU).
* Keep the room's power/thermal state comparable between A and B runs (same profile,
  same display mode, VRR as recorded by `preflight`).
* Record, do not "fix", anything unusual (a plug pull, a Steam update prompt) — the
  correlation tables are only trustworthy if the intervention is written down.
