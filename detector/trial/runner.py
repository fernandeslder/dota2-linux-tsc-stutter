"""`stutter trial run` and `stutter trial cleanup`.

`trial run` sequences one measurement and always leaves the machine clean:

    quiesce on (optional)
      -> collect start           (run-dir runs/<ts>-<label>/ + meta.json)
      -> wait for process + MangoHud frames flowing (timeout -> clean give-up)
      -> mark match_loaded
      -> sleep warm-up
      -> mark warmup_end
      -> record N minutes        (1-minute heartbeats; abort if the process dies
                                  or frames stop for >10 s)
      -> mark window_end
      -> collect stop
      -> quiesce off             (ALWAYS -- also on Ctrl-C / SIGTERM / exception)
      -> detect + report
      -> print verdict

The game is launched by the GUI-driving agent (see ``docs/TRIAL-PROCEDURE.md``);
``--launch`` exists so the whole wrapper can be exercised in tests with a
synthetic app such as ``vkcube``.  ``--wait-process`` names the process to watch.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from typing import List, Optional

from ..collect import cli as collect_cli
from ..collect import profiles, quiesce as quiesce_mod, util
from ..collect.rundir import RunDir

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUNS_DIR = os.path.join(REPO_ROOT, "runs")

FRAMES_STALL_S = 60.0  # MangoHud flushes its csv in bursts; 10 s false-aborted healthy live runs
MIN_FRAMES = 5


class TrialAbort(RuntimeError):
    def __init__(self, reason: str, code: int = 2):
        super().__init__(reason)
        self.reason = reason
        self.code = code


# ---------------------------------------------------------------------------
# process / frame helpers
# ---------------------------------------------------------------------------

def find_processes(name: str) -> List[int]:
    """PIDs whose comm or argv[0] basename equals *name*.

    Deliberately *not* a substring search over the whole cmdline: a wrapper such
    as ``sh -c vkcube`` or ``mangohud %command%`` would otherwise be mistaken for
    the game, which breaks the "did the game die?" check.
    """
    out = []
    try:
        entries = os.listdir("/proc")
    except OSError:
        return out
    me = os.getpid()
    for entry in entries:
        if not entry.isdigit():
            continue
        pid = int(entry)
        if pid == me or pid == os.getppid():
            continue
        comm = ""
        try:
            with open(f"/proc/{pid}/comm") as fh:
                comm = fh.read().strip()
        except OSError:
            continue
        if comm == name:
            if _pid_state(pid) == "Z":  # unreaped child: effectively dead
                continue
            out.append(pid)
            continue
        # Wine/Proton: argv[0] is a Windows path (backslashes, may contain spaces) and comm is a
        # thread name ("MainThrd"), so compare the basename of the raw argv[0] with '\\' as separator.
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as fh:
                argv0 = fh.read().split(b"\0")[0].decode("utf-8", "replace")
        except OSError:
            argv0 = ""
        if argv0 and argv0.replace("\\", "/").rsplit("/", 1)[-1] == name:
            if _pid_state(pid) == "Z":
                continue
            out.append(pid)
            continue
        cmd = util.proc_cmdline(pid)
        if cmd and os.path.basename(cmd.split()[0]) == name:
            if _pid_state(pid) == "Z":
                continue
            out.append(pid)
    return out


def _pid_state(pid: int) -> str:
    d = util.parse_pid_stat(util.read_text(f"/proc/{pid}/stat"))
    return d["state"] if d else ""


def _argv(pid: int) -> List[str]:
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as fh:
            raw = fh.read()
    except OSError:
        return []
    return [a.decode("utf-8", "replace") for a in raw.split(b"\0") if a]


def scan_argv(token: str) -> List[int]:
    """PIDs with *token* as an exact argv element.

    Exact-token matching (not substring) is deliberate: a shell whose command
    string merely mentions ``detector.collect.supervisor`` must never be mistaken
    for a supervisor and killed.
    """
    out = []
    me = os.getpid()
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        pid = int(entry)
        if pid == me:
            continue
        if token in _argv(pid):
            out.append(pid)
    return out


class FrameCounter:
    """Incrementally count rows in a growing ``frametimes.csv``."""

    def __init__(self, path: str):
        self.path = path
        self.offset = 0
        self.lines = 0

    def poll(self) -> int:
        try:
            with open(self.path, "rb") as fh:
                fh.seek(self.offset)
                data = fh.read()
                self.offset += len(data)
                self.lines += data.count(b"\n")
        except OSError:
            pass
        return max(0, self.lines - 1)  # minus header

    @property
    def frames(self) -> int:
        return max(0, self.lines - 1)


# ---------------------------------------------------------------------------
# small namespace helpers for the collect/quiesce entry points
# ---------------------------------------------------------------------------

def _ns(**kw):
    return argparse.Namespace(**kw)


def _collect_start(run_dir, label, profile, launch_opts, warmup, proton=False,
                   deep=False, offcpu_stacks=False, no_offcpu=False):
    return collect_cli.cmd_start(_ns(
        run_dir=run_dir, label=label, profile=profile, launch_opts=launch_opts,
        warmup=warmup, game_pid=None, duration=0.0, mangohud_offset=0.0,
        mangohud_extra={}, no_mangohud=False, proton=proton, dota_console_log="",
        deep=deep, offcpu_stacks=offcpu_stacks, no_offcpu=no_offcpu,
        offcpu_hz=None, offcpu_no_native=False))


def _collect_stop(run_dir):
    return collect_cli.cmd_stop(_ns(run_dir=run_dir, label=""))


def _mark(run_dir, label, detail=""):
    return collect_cli.cmd_mark(_ns(mark_label=label, detail=detail, run_dir=run_dir, label=""))


def _quiesce_on(run_dir, dry_run=False, pause_containers=False):
    return quiesce_mod.quiesce_on(_ns(run_dir=run_dir, pause_containers=pause_containers,
                                      dry_run=dry_run))


def _quiesce_off(run_dir):
    return quiesce_mod.quiesce_off(_ns(run_dir=run_dir, state="", rewarm=False))


# ---------------------------------------------------------------------------
# signal handling
# ---------------------------------------------------------------------------

def _install_handlers():
    def _handler(signum, _frame):
        raise TrialAbort(f"interrupted by signal {signum}")
    old = {}
    for s in (signal.SIGINT, signal.SIGTERM):
        old[s] = signal.signal(s, _handler)
    return old


def _restore_handlers(old):
    for s, h in old.items():
        try:
            signal.signal(s, h)
        except (ValueError, OSError):
            pass


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------

def _current_dota_launch_options(account, vdf_path) -> str:
    from . import steam as steammod
    try:
        acc = steammod.find_dota_config(account, vdf_path)
        return steammod.get_launch_options(acc) or ""
    except steammod.SteamConfigError:
        return ""


def run_trial(args) -> int:
    label = args.label or "trial"
    run_dir = os.path.abspath(args.run_dir) if args.run_dir else os.path.join(
        RUNS_DIR, collect_cli.new_run_id(label))
    old_handlers = _install_handlers()
    aborted: Optional[str] = None
    launched: Optional[subprocess.Popen] = None
    started = False
    window_started = False
    try:
        if args.quiesce:
            _quiesce_on(run_dir if started else None, dry_run=args.quiesce_dry_run,
                        pause_containers=args.pause_containers)

        dota_opts = _current_dota_launch_options(args.account, args.vdf)
        rc = _collect_start(run_dir, label, args.profile, dota_opts, args.warmup,
                            proton=args.proton, deep=args.deep,
                            offcpu_stacks=args.offcpu_stacks, no_offcpu=args.no_offcpu)
        if rc != 0:
            raise TrialAbort("collect start failed", code=1)
        started = True
        meta = RunDir(run_dir).read_meta()
        RunDir(run_dir).update_meta(trial={
            "label": label,
            "minutes": args.minutes,
            "warmup_s": args.warmup,
            "wait_process": args.wait_process,
            "profile": args.profile,
            "quiesce": bool(args.quiesce),
            "launch_cmd": args.launch or "",
            "launch_options_under_test": dota_opts,
        })

        if args.mangohud_link:
            os.makedirs(os.path.join(run_dir, "raw", "mangohud"), exist_ok=True)
            tmp = args.mangohud_link + ".tmp"
            if os.path.lexists(tmp):
                os.remove(tmp)
            os.symlink(os.path.join(run_dir, "raw", "mangohud"), tmp)
            os.replace(tmp, args.mangohud_link)
            print(f"[trial] MangoHud output link {args.mangohud_link} -> {run_dir}/raw/mangohud")

        if args.launch:
            launched = _launch_app(args.launch, meta)

        deadline = time.time() + args.timeout
        pids, frames = _wait_for_game(args.wait_process, run_dir, deadline, args.timeout)
        if args.go_file:
            print(f"[trial] game up; waiting for go-file {args.go_file} (touch it once the match is live)")
            while not os.path.exists(args.go_file):
                if not find_processes(args.wait_process):
                    raise TrialAbort(f"game process {args.wait_process!r} died before go-file")
                if time.time() > deadline + args.go_timeout:
                    raise TrialAbort(f"go-file never appeared within {args.go_timeout:.0f}s")
                time.sleep(0.5)
        _mark(run_dir, "match_loaded",
              f"process={args.wait_process} pids={pids} frames={frames}")

        _sleep_interruptible(args.warmup)
        _mark(run_dir, "warmup_end", f"warmup_s={args.warmup}")
        window_started = True

        _record_window(run_dir, args.wait_process, args.minutes)
        _mark(run_dir, "window_end", f"minutes={args.minutes}")
    except TrialAbort as exc:
        aborted = exc.reason
        if started and window_started:
            try:
                _mark(run_dir, "window_end", f"aborted: {exc.reason}")
            except Exception:
                pass
    except KeyboardInterrupt as exc:  # pragma: no cover - handler converts these
        aborted = str(exc) or "KeyboardInterrupt"
    finally:
        if launched is not None:
            _terminate(launched)
        if started:
            try:
                _collect_stop(run_dir)
            except Exception as exc:  # never let cleanup mask the verdict
                sys.stderr.write(f"[trial] collect stop failed: {exc}\n")
        try:
            _quiesce_off(run_dir)
        except Exception as exc:
            sys.stderr.write(f"[trial] quiesce off failed: {exc}\n")
        _restore_handlers(old_handlers)

    return _finish(run_dir, args, aborted, started)


def _launch_app(cmd: str, meta: dict) -> subprocess.Popen:
    env = dict(os.environ)
    mh = meta.get("mangohud", {})
    env["MANGOHUD"] = "1"
    if mh.get("config_file"):
        env["MANGOHUD_CONFIGFILE"] = mh["config_file"]
    env["LD_PRELOAD"] = ""  # let the Vulkan implicit layer do the work
    print(f"[trial] launching (dev): {cmd}")
    return subprocess.Popen(["/bin/sh", "-c", cmd], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=True)


def _terminate(proc: subprocess.Popen, timeout: float = 5.0):
    pid = proc.pid
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except OSError:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return
        time.sleep(0.1)
    try:
        os.killpg(os.getpgid(pid), signal.SIGKILL)
    except OSError:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
    try:
        proc.wait(timeout=2)
    except Exception:
        pass


def _sleep_interruptible(seconds: float) -> None:
    end = time.monotonic() + max(0.0, seconds)
    while True:
        remaining = end - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(0.5, remaining))


def _wait_for_game(name: str, run_dir: str, deadline: float, timeout: float):
    counter = FrameCounter(os.path.join(run_dir, "frametimes.csv"))
    last_report = 0.0
    while time.time() < deadline:
        pids = find_processes(name)
        frames = counter.poll()
        if pids and frames >= MIN_FRAMES:
            print(f"[trial] {name} up (pids {pids}), {frames} frames flowing")
            return pids, frames
        if time.time() - last_report > 10:
            print(f"[trial] waiting for {name!r} + frames ... "
                  f"(pids={len(pids)} frames={frames})")
            last_report = time.time()
        time.sleep(0.5)
    raise TrialAbort(f"timeout after {timeout:.0f}s: process {name!r} and/or MangoHud "
                     f"frames never appeared (last: pids={find_processes(name)} "
                     f"frames={counter.poll()})")


def _record_window(run_dir: str, name: str, minutes: float) -> None:
    counter = FrameCounter(os.path.join(run_dir, "frametimes.csv"))
    counter.poll()
    end = time.time() + minutes * 60.0
    last_hb = time.time()
    last_progress = time.monotonic()
    prev = counter.frames
    last_raw = 0
    print(f"[trial] recording {minutes:.1f} min window (heartbeat each minute)")
    while time.time() < end:
        time.sleep(0.5)
        if not find_processes(name):
            raise TrialAbort(f"game process {name!r} died during the window "
                             f"(frames={counter.frames})")
        n = counter.poll()
        # progress = frametimes.csv rows OR growth of MangoHud's raw csv (the collector flushes frametimes.csv in
        # large batches, so row counts alone can stall for a minute while frames are flowing)
        raw_size = 0
        try:
            rawdir = os.path.join(run_dir, "raw", "mangohud")
            raw_size = max((os.path.getsize(os.path.join(rawdir, f)) for f in os.listdir(rawdir)), default=0)
        except OSError:
            pass
        if n > prev or raw_size > last_raw:
            prev = max(prev, n)
            last_raw = max(last_raw, raw_size)
            last_progress = time.monotonic()
        elif time.monotonic() - last_progress > FRAMES_STALL_S:
            raise TrialAbort(f"MangoHud frames stopped for >{FRAMES_STALL_S:.0f}s "
                             f"(last count {n})")
        if time.time() - last_hb >= 60.0:
            done = minutes - (end - time.time()) / 60.0
            print(f"[trial] heartbeat {done:.1f}/{minutes:.1f} min, frames={n}")
            try:
                RunDir(run_dir).append_event("heartbeat", f"frames={n} elapsed_min={done:.1f}")
            except Exception:
                pass
            last_hb = time.time()


def _finish(run_dir: str, args, aborted: Optional[str], started: bool) -> int:
    if not started or not os.path.isdir(run_dir):
        print(f"[trial] aborted before collection started: {aborted}", file=sys.stderr)
        return 1
    ft = os.path.join(run_dir, "frametimes.csv")
    if not os.path.exists(ft) or os.path.getsize(ft) < 32:
        print(f"[trial] no frames captured in {run_dir}; aborted: {aborted}", file=sys.stderr)
        return 1 if aborted else 3
    try:
        verdict, fixed_res = _analyze(run_dir, args)
    except Exception as exc:
        print(f"[trial] analysis failed: {exc}", file=sys.stderr)
        return 1
    _print_verdict(verdict, fixed_res, run_dir, aborted)
    if aborted:
        return 2
    return 0


def _analyze(run_dir: str, args) -> tuple:
    from ..analyze.rundir import load_rundir
    from ..analyze import reporting, fixed as fixed_mod
    rd = load_rundir(run_dir)
    verdict = reporting.analyze_run(rd, n_perm=args.n_perm)
    out = os.path.join(run_dir, "out")
    reporting.write_outputs(rd, verdict, out, plots=not args.no_plots)
    with open(os.path.join(out, "verdict.json")) as fh:
        loaded = json.load(fh)
    fixed_res = fixed_mod.check_fixed([loaded], fixed_mod.load_def())
    return loaded, fixed_res


def _print_verdict(v: dict, fixed_res: dict, run_dir: str, aborted: Optional[str]) -> None:
    h = v["hitches"]
    ft = v["frametime"]
    p = v["periodicity"]
    kind = p.get("kind", "?")
    periodic = "yes" if (kind in ("periodic", "mixed")
                         or (p.get("steady") or {}).get("significant")) else "no"
    if not p.get("sparse_assessable", False):
        sparse = "insufficient-window"
    elif (p.get("sparse") or {}).get("significant"):
        sparse = "yes"
    else:
        sparse = "no"
    print()
    print(f"=== trial verdict: {v.get('run_id')} ===")
    print(f"run_dir:  {run_dir}")
    print(f"window:   {v['window']['duration_s']/60.0:.1f} min "
          f"(warm-up source: {v['window']['warmup_source']}), "
          f"{v['window']['n_frames']} frames")
    print(f"hitches:  {h['count']} ({h['per_min']:.2f}/min), worst {h['worst_ms']:.1f} ms, "
          f"median {h['median_ms']:.1f} ms, low-tier {h['low_count']}")
    print(f"lows:     1% {ft['fps_1pct_low']:.1f} fps, 0.1% {ft['fps_0.1pct_low']:.1f} fps, "
          f"mean {ft['mean_fps']:.1f} fps")
    print(f"periodic: {periodic} (kind={kind})")
    print(f"sparse:   {sparse}")
    note = " (PROVISIONAL thresholds)" if fixed_res.get("provisional") else ""
    print(f"fixed:    {'PASS' if fixed_res['passed'] else 'FAIL'}{note}")
    if aborted:
        print(f"ABORTED:  {aborted}")


# ---------------------------------------------------------------------------
# cleanup
# ---------------------------------------------------------------------------

def _kill(pid: int, what: str, actions: List[str]) -> None:
    for sig in (signal.SIGTERM,):
        try:
            os.kill(pid, sig)
        except OSError:
            return
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except OSError:
            actions.append(f"stopped {what} pid {pid}")
            return
        time.sleep(0.2)
    try:
        os.kill(pid, signal.SIGKILL)
        actions.append(f"killed {what} pid {pid}")
    except OSError:
        pass


def _under_repo(path: str) -> bool:
    try:
        return os.path.commonpath([os.path.realpath(path), REPO_ROOT]) == REPO_ROOT
    except (ValueError, OSError):
        return False


def _is_ours(pid: int) -> bool:
    """True when the process belongs to *this* repo/worktree (cwd or cmdline).

    Orca runs several worktrees of this project side by side; cleanup must never
    kill a sibling worktree's collector, so every scanned pid is scoped here.
    """
    try:
        cwd = os.readlink(f"/proc/{pid}/cwd")
        if cwd and _under_repo(cwd):
            return True
    except OSError:
        pass
    return REPO_ROOT in util.proc_cmdline(pid)


def cleanup(kill_mangohud: bool = True, purge_state: bool = True,
            out=None) -> int:
    """Stop every collector / logger *this worktree* left and restore quiesce.

    Safe to run any time: it only targets processes and state it recognises as
    belonging to this repository, so it cannot disturb another agent's run.
    """
    out = out or sys.stdout
    actions: List[str] = []
    killed: set = set()

    # 1. run dirs with a live collector (ours by construction)
    for run_dir in collect_cli.list_run_dirs():
        st = RunDir(run_dir).read_collector_state()
        if st.get("state") == "running" and collect_cli.is_collector(st.get("pid", 0)):
            _kill(st["pid"], f"collector ({os.path.basename(run_dir)})", actions)
            killed.add(st["pid"])

    # 2. any other supervisor of ours (e.g. from a crashed start)
    for pid in scan_argv("detector.collect.supervisor"):
        if pid in killed or not _is_ours(pid):
            continue
        _kill(pid, "collector supervisor", actions)
        killed.add(pid)

    # 3. stray MangoHud LD_PRELOAD wrappers we may have started
    if kill_mangohud:
        for entry in os.listdir("/proc"):
            if not entry.isdigit():
                continue
            pid = int(entry)
            try:
                with open(f"/proc/{pid}/comm") as fh:
                    comm = fh.read().strip()
            except OSError:
                continue
            if comm == "mangohud" and _is_ours(pid):
                _kill(pid, "mangohud wrapper", actions)

    # 4. restore quiesce (our state file) and purge it
    try:
        _quiesce_off("")
    except Exception as exc:
        actions.append(f"quiesce off error: {exc}")
    if purge_state and os.path.exists(quiesce_mod.STATE_PATH):
        try:
            os.unlink(quiesce_mod.STATE_PATH)
            actions.append("removed runs/.quiesce-state.json")
        except OSError:
            pass

    for a in actions:
        print(f"[cleanup] {a}", file=out)

    # 5. verify nothing *of ours* is left
    leftovers = [p for p in scan_argv("detector.collect.supervisor") if _is_ours(p)]
    left_mh = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{int(entry)}/comm") as fh:
                if fh.read().strip() == "mangohud" and _is_ours(int(entry)):
                    left_mh.append(int(entry))
        except OSError:
            pass
    remaining = leftovers + left_mh
    if remaining:
        print(f"[cleanup] WARNING: {remaining} still present", file=out)
        return 1
    print("[cleanup] clean: no collectors, mangohud loggers, or quiesce state remain",
          file=out)
    return 0


def cmd_run(args) -> int:
    return run_trial(args)


def cmd_cleanup(args) -> int:
    return cleanup(kill_mangohud=not args.no_kill_mangohud, purge_state=not args.keep_state)


# ---------------------------------------------------------------------------
# argparse
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="stutter trial")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="sequence one trial and print the verdict")
    r.add_argument("--label", default="trial")
    r.add_argument("--minutes", type=float, default=15.0, help="window length in minutes")
    r.add_argument("--warmup", type=float, default=20.0, help="warm-up seconds before the window")
    r.add_argument("--quiesce", action="store_true", help="quiesce competing load first")
    r.add_argument("--quiesce-dry-run", action="store_true",
                   help="record what quiesce would stop but change nothing")
    r.add_argument("--pause-containers", action="store_true")
    r.add_argument("--wait-process", default="dota2",
                   help="process name to wait for (default dota2; e.g. vkcube for tests)")
    r.add_argument("--profile", default="full", choices=sorted(profiles.PROFILES))
    r.add_argument("--timeout", type=float, default=600.0,
                   help="seconds to wait for the process + first frames")
    r.add_argument("--run-dir", default=None)
    r.add_argument("--deep", action="store_true", help="collect: bpftrace off-CPU profile")
    r.add_argument("--offcpu-stacks", action="store_true")
    r.add_argument("--no-offcpu", action="store_true")
    r.add_argument("--go-file", default=None,
                   help="after the game is up, wait for this file to exist (touch it when the "
                        "match is live); the warm-up then starts from that moment")
    r.add_argument("--go-timeout", type=float, default=900.0,
                   help="extra seconds to wait for --go-file after the game is up")
    r.add_argument("--mangohud-link", default=None,
                   help="symlink to point at <run-dir>/raw/mangohud (static MangoHud config "
                        "output_folder in the Steam launch string)")
    r.add_argument("--launch", default=None,
                   help="dev/test hook: shell command to launch under MangoHud "
                        "(production launches Dota from Steam instead)")
    r.add_argument("--account", default=None, help="Steam account id for the launch options")
    r.add_argument("--vdf", default=None, help="explicit localconfig.vdf")
    r.add_argument("--proton", action="store_true", help="emit/consider Proton launch options")
    r.add_argument("--n-perm", type=int, default=None)
    r.add_argument("--no-plots", action="store_true")
    r.set_defaults(func=cmd_run)

    c = sub.add_parser("cleanup", help="stop collectors/loggers and restore quiesce")
    c.add_argument("--no-kill-mangohud", action="store_true")
    c.add_argument("--keep-state", action="store_true", help="keep the quiesce state file")
    c.set_defaults(func=cmd_cleanup)
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
