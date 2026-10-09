"""`stutter collect ...` CLI: start / stop / mark / status."""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
from typing import Optional

from . import env, mangohud, profiles, util
from .rundir import RunDir

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUNS_DIR = os.path.join(REPO_ROOT, "runs")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def pid_alive(pid: int) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def is_collector(pid: int) -> bool:
    if not pid_alive(pid):
        return False
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as fh:
            cmd = fh.read().decode("utf-8", "replace")
    except OSError:
        return False
    return "detector.collect.supervisor" in cmd


def _slug(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", s or "").strip("-")
    return s or "run"


def new_run_id(label: str = "") -> str:
    ts = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    return f"{ts}-{_slug(label)}" if label else ts


def list_run_dirs() -> list:
    if not os.path.isdir(RUNS_DIR):
        return []
    out = []
    for name in os.listdir(RUNS_DIR):
        p = os.path.join(RUNS_DIR, name)
        if os.path.isdir(p) and os.path.exists(os.path.join(p, "meta.json")):
            out.append(p)
    out.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return out


def active_run_dir() -> Optional[str]:
    for p in list_run_dirs():
        st = RunDir(p).read_collector_state()
        if st.get("state") == "running" and is_collector(st.get("pid", 0)):
            return p
    return None


def resolve_run_dir(explicit: Optional[str], args_label: str = "") -> str:
    if explicit:
        return os.path.abspath(explicit)
    if args_label:
        cand = [p for p in list_run_dirs() if os.path.basename(p).endswith(_slug(args_label))]
        if cand:
            return cand[0]
    act = active_run_dir()
    if act:
        return act
    runs = list_run_dirs()
    if runs:
        return runs[0]
    raise SystemExit("no run directory found; pass --run-dir")


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------

def cmd_start(args) -> int:
    run_dir = os.path.abspath(args.run_dir) if args.run_dir else os.path.join(
        RUNS_DIR, new_run_id(args.label))
    rd = RunDir(run_dir)
    rd.create(label=args.label, launch_opts=args.launch_opts)

    state = rd.read_collector_state()
    if state.get("state") == "running" and is_collector(state.get("pid", 0)):
        print(f"collector already running (pid {state['pid']}) in {run_dir}")
        return 0
    # stale state
    rd.clear_collector_state()

    profile = profiles.get(args.profile)
    host = env.host_info(REPO_ROOT)
    mh_dir = mangohud.raw_dir(run_dir)
    os.makedirs(mh_dir, exist_ok=True)
    conf_path = os.path.join(run_dir, "raw", "mangohud.conf")
    cfg = mangohud.default_config(mh_dir, extra=args.mangohud_extra)
    mangohud.write_config_file(conf_path, cfg)
    opts = mangohud.launch_options(conf_path, native_vulkan=not args.proton)

    t0 = util.epoch()
    rd.write_meta({
        "run_id": rd.run_id,
        "label": args.label,
        "launch_opts": args.launch_opts,
        "collector_profile": profile["profile"],
        "t_start_epoch": t0,
        "warmup_s": float(args.warmup),
        "host": host,
        "mangohud": {
            "config_file": conf_path,
            "folder": mh_dir,
            "config": cfg,
            "launch_options": opts,
            "command_line": mangohud.config_env(cfg),
        },
        "mangohud_offset_s": float(args.mangohud_offset),
        "dota_console_log": args.dota_console_log or _guess_console_log(),
        "offcpu": {"enabled": not args.no_offcpu, "hz": args.offcpu_hz,
                   "stacks": bool(args.offcpu_stacks),
                   "native": not args.offcpu_no_native},
        "deep": bool(args.deep),
    })
    rd.append_event("run_start", f"label={args.label} profile={profile['profile']}")

    cmd = [sys.executable, "-m", "detector.collect.supervisor",
           "--run-dir", run_dir, "--profile", args.profile,
           "--mangohud-offset", str(args.mangohud_offset)]
    if args.game_pid:
        cmd += ["--game-pid", str(args.game_pid)]
    if args.duration:
        cmd += ["--duration", str(args.duration)]
    if args.no_mangohud:
        cmd += ["--no-mangohud"]
    if args.no_offcpu:
        cmd += ["--no-offcpu"]
    if args.offcpu_hz:
        cmd += ["--offcpu-hz", str(args.offcpu_hz)]
    if args.offcpu_stacks:
        cmd += ["--offcpu-stacks"]
    if args.offcpu_no_native:
        cmd += ["--offcpu-no-native"]
    if args.deep:
        cmd += ["--deep"]

    logf = open(os.path.join(run_dir, "collector.out"), "ab")
    child_env = dict(os.environ)
    child_env["PYTHONPATH"] = REPO_ROOT + os.pathsep + child_env.get("PYTHONPATH", "")
    proc = subprocess.Popen(cmd, cwd=REPO_ROOT, env=child_env,
                            stdin=subprocess.DEVNULL, stdout=logf, stderr=subprocess.STDOUT,
                            start_new_session=True)

    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        st = rd.read_collector_state()
        if st.get("state") == "running" and pid_alive(st.get("pid", 0)):
            break
        if proc.poll() is not None:
            print(f"collector exited early (rc={proc.returncode}); see {run_dir}/collector.out")
            return 1
        time.sleep(0.1)

    st = rd.read_collector_state()
    print(f"collector started: pid={st.get('pid', proc.pid)} profile={profile['profile']}")
    print(f"run_dir: {run_dir}")
    print(f"mangohud config: {conf_path}")
    print(f"steam launch option (native Vulkan): {opts['native_vulkan_layer']}")
    print(f"steam launch option (wrapper):       {opts['wrapper']}")
    return 0


def cmd_stop(args) -> int:
    run_dir = resolve_run_dir(args.run_dir, getattr(args, "label", ""))
    rd = RunDir(run_dir)
    state = rd.read_collector_state()
    pid = state.get("pid")
    if state.get("state") == "running" and is_collector(pid):
        os.kill(pid, signal.SIGTERM)
        deadline = time.monotonic() + 20.0
        while time.monotonic() < deadline and is_collector(pid):
            time.sleep(0.2)
        if is_collector(pid):
            sys.stderr.write(f"collector pid {pid} did not exit; sending SIGKILL\n")
            os.kill(pid, signal.SIGKILL)
            time.sleep(0.5)
        print(f"collector stopped (pid {pid})")
    else:
        print("collector not running (nothing to stop)")

    _finalize(rd)
    _print_summary(rd)
    return 0


def _finalize(rd: RunDir) -> None:
    state = rd.read_collector_state()
    if state.get("finalized"):
        return
    rd.append_event("window_end", "collect stop")
    end = util.epoch()
    meta = rd.read_meta()
    meta.setdefault("t_end_epoch", end)
    meta["t_end_epoch"] = meta.get("t_end_epoch") or end
    rd.write_meta(meta)
    state.update({"state": "stopped", "finalized": True, "finalized_epoch": end})
    rd.write_collector_state(state)


def _print_summary(rd: RunDir) -> None:
    print(f"run_dir: {rd.root}")
    counts = {}
    for name in sorted(os.listdir(rd.root)) if os.path.isdir(rd.root) else []:
        if name.endswith(".csv"):
            p = os.path.join(rd.root, name)
            try:
                with open(p) as fh:
                    n = max(0, sum(1 for _ in fh) - 1)
            except OSError:
                n = 0
            counts[name] = n
    for name, n in counts.items():
        print(f"  {name}: {n} rows")


def cmd_mark(args) -> int:
    run_dir = resolve_run_dir(args.run_dir, getattr(args, "label", ""))
    rd = RunDir(run_dir)
    t = rd.append_event(args.mark_label, args.detail or "")
    st = rd.read_collector_state()
    running = st.get("state") == "running" and is_collector(st.get("pid", 0))
    print(f"marked {args.mark_label!r} at {t:.6f} in {run_dir} (collector {'running' if running else 'not running'})")
    return 0


def cmd_status(args) -> int:
    run_dir = resolve_run_dir(args.run_dir, getattr(args, "label", ""))
    rd = RunDir(run_dir)
    st = rd.read_collector_state()
    meta = rd.read_meta()
    live = st.get("state") == "running" and is_collector(st.get("pid", 0))
    info = {
        "run_dir": run_dir,
        "collector_pid": st.get("pid"),
        "state": st.get("state", "unknown"),
        "live": live,
        "profile": st.get("profile"),
        "started_epoch": st.get("started_epoch"),
        "mangohud_log": meta.get("mangohud_log"),
    }
    if live:
        try:
            with open(f"/proc/{st['pid']}/stat") as fh:
                d = util.parse_pid_stat(fh.read())
            info["nthreads"] = d["num_threads"] if d else None
        except OSError:
            pass
    print(json.dumps(info, indent=2, default=str))
    return 0 if live or st.get("state") == "stopped" else 1


def _guess_console_log() -> str:
    """Dota `-condebug` writes game/dota/console.log under the Steam install."""
    import glob
    pats = [
        os.path.expanduser("~/.steam/steam/steamapps/common/dota 2 beta/game/dota/console.log"),
        os.path.expanduser("~/.local/share/Steam/steamapps/common/dota 2 beta/game/dota/console.log"),
    ]
    for p in pats:
        if os.path.exists(p):
            return p
    for p in glob.glob(os.path.expanduser(
            "~/.steam/steam/steamapps/common/dota 2 beta/game/dota/console.log")):
        return p
    return ""


# ---------------------------------------------------------------------------
# argparse
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="stutter collect")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("start", help="start all collectors for a run")
    ps.add_argument("--run-dir")
    ps.add_argument("--label", default="")
    ps.add_argument("--profile", default="full", choices=sorted(profiles.PROFILES))
    ps.add_argument("--launch-opts", default="")
    ps.add_argument("--warmup", type=float, default=20.0)
    ps.add_argument("--game-pid", type=int, default=None)
    ps.add_argument("--duration", type=float, default=0.0, help="auto-stop after N seconds")
    ps.add_argument("--mangohud-offset", type=float, default=0.0)
    ps.add_argument("--mangohud-extra", action="append", default=[],
                    help="extra MangoHud config KEY=VALUE (repeatable)")
    ps.add_argument("--no-mangohud", action="store_true")
    ps.add_argument("--proton", action="store_true", help="emit Proton launch options")
    ps.add_argument("--dota-console-log", default="")
    ps.add_argument("--no-offcpu", action="store_true",
                    help="disable the off-CPU (blocked-on) sampler")
    ps.add_argument("--offcpu-hz", type=float, default=None,
                    help="off-CPU scan rate in Hz (default 100)")
    ps.add_argument("--offcpu-stacks", action="store_true",
                    help="also capture kernel stacks of D-state threads (sudo -n)")
    ps.add_argument("--offcpu-no-native", action="store_true",
                    help="force the Python off-CPU sampler (skip the C helper)")
    ps.add_argument("--deep", action="store_true",
                    help="also run the bpftrace off-CPU/sched-switch profile (sudo -n)")
    ps.set_defaults(func=cmd_start)

    pt = sub.add_parser("stop", help="stop collectors and finalize the run dir")
    pt.add_argument("--run-dir")
    pt.add_argument("--label", default="")
    pt.set_defaults(func=cmd_stop)

    pm = sub.add_parser("mark", help="append a mark to events.csv")
    pm.add_argument("mark_label")
    pm.add_argument("--detail", default="")
    pm.add_argument("--run-dir")
    pm.add_argument("--label", default="")
    pm.set_defaults(func=cmd_mark)

    pst = sub.add_parser("status", help="show collector state")
    pst.add_argument("--run-dir")
    pst.add_argument("--label", default="")
    pst.set_defaults(func=cmd_status)
    return ap


def main(argv: Optional[list] = None) -> int:
    args = build_parser().parse_args(argv)
    # normalise KEY=VALUE extras
    if getattr(args, "mangohud_extra", None):
        extra = {}
        for item in args.mangohud_extra:
            if "=" in item:
                k, v = item.split("=", 1)
                extra[k] = v
        args.mangohud_extra = extra
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
