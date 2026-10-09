"""`stutter quiesce on|off` -- record competing background load, then restore exactly.

What counts as load that competes with the game:
  * Ollama GPU models (typically the main GPU competitor): stop the service / unload
    models, recording exactly what was running so `off` can restore it.
  * Other heavy processes: recorded (CPU/IO/GPU) and listed; not killed.
  * Containers: only touched when measurably busy, and only paused with
    `--pause-containers` (recorded so `off` unpauses).

State is written to `runs/.quiesce-state.json` (and, when a run dir is given,
copied into that run dir as `quiesce-state.json`).  `off` refuses to touch
anything it did not record.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from typing import List, Optional

from . import env, util
from .rundir import RunDir

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUNS_DIR = os.path.join(REPO_ROOT, "runs")
STATE_PATH = os.path.join(RUNS_DIR, ".quiesce-state.json")
GPU_BUSY_MIB = 200.0
CONTAINER_BUSY_PCT = 5.0


# ---------------------------------------------------------------------------
# probes
# ---------------------------------------------------------------------------

def _sudo() -> List[str]:
    return ["sudo", "-n"] if util.have("sudo") else []


def systemctl(action: str, unit: str, scope: str = "system") -> tuple:
    cmd = _sudo() + ["systemctl"]
    if scope == "user":
        cmd = ["systemctl", "--user"]
    cmd += [action, unit]
    rc, out, err = util.run_capture(cmd, timeout=30)
    return rc, (out + err).strip()


def systemctl_active(unit: str) -> Optional[bool]:
    rc, out, _ = util.run_capture(["systemctl", "is-active", unit], timeout=5)
    if rc not in (0, 3):
        return None
    return out.strip() == "active"


def systemctl_enabled(unit: str) -> Optional[bool]:
    rc, out, _ = util.run_capture(["systemctl", "is-enabled", unit], timeout=5)
    if rc not in (0, 1):
        return None
    return out.strip() in ("enabled", "enabled-runtime", "static")


def ollama_ps() -> List[dict]:
    if not util.have("ollama"):
        return []
    rc, out, _ = util.run_capture(["ollama", "ps"], timeout=10)
    if rc != 0:
        return []
    models = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 3 and parts[0] != "NAME":
            models.append({"name": parts[0], "id": parts[1], "size": parts[2],
                           "processor": parts[3] if len(parts) > 3 else ""})
    return models


def top_processes(n: int = 15, sample: float = 0.3) -> List[dict]:
    """Top processes by CPU% over a short sample, plus GPU memory users."""
    def snapshot():
        snap = {}
        for entry in os.listdir("/proc"):
            if not entry.isdigit():
                continue
            try:
                with open(f"/proc/{entry}/stat") as fh:
                    d = util.parse_pid_stat(fh.read())
            except OSError:
                continue
            if d:
                snap[int(entry)] = d
        return snap

    a = snapshot()
    t0 = time.monotonic()
    time.sleep(sample)
    b = snapshot()
    dt = max(1e-6, time.monotonic() - t0)
    jiff = float(os.sysconf("SC_CLK_TCK"))
    rows = []
    for pid, d in b.items():
        prev = a.get(pid)
        if not prev:
            continue
        ticks = (d["utime"] + d["stime"]) - (prev["utime"] + prev["stime"])
        cpu = ticks / jiff / dt * 100.0
        rows.append({"pid": pid, "comm": d["comm"], "cpu_pct": round(cpu, 1),
                     "rss_mib": round(d["rss_pages"] * os.sysconf("SC_PAGE_SIZE") / 1048576.0, 1)})
    rows.sort(key=lambda r: r["cpu_pct"], reverse=True)
    rows = rows[:n]
    # annotate GPU users
    try:
        from .collectors import nvidia
        gpu = {p["pid"]: p for p in nvidia.running_processes()}
    except Exception:
        gpu = {}
    for r in rows:
        if r["pid"] in gpu:
            r["gpu_kind"] = gpu[r["pid"]]["kind"]
            r["vram_mib"] = gpu[r["pid"]].get("used_mib")
    return rows


def busy_containers(threshold: float = CONTAINER_BUSY_PCT) -> List[dict]:
    if not util.have("docker"):
        return []
    rc, out, _ = util.run_capture(
        ["docker", "stats", "--no-stream", "--format",
         "{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"], timeout=15)
    if rc != 0:
        return []
    out_containers = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        try:
            cpu = float(parts[1].rstrip("%"))
        except ValueError:
            continue
        out_containers.append({"name": parts[0], "cpu_pct": cpu,
                               "mem": parts[2] if len(parts) > 2 else ""})
    return [c for c in out_containers if c["cpu_pct"] >= threshold]


# ---------------------------------------------------------------------------
# on / off
# ---------------------------------------------------------------------------

def quiesce_on(args) -> int:
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH) as fh:
                existing = json.load(fh)
            if not existing.get("restored"):
                print(f"quiesce already on (state {STATE_PATH}); run `quiesce off` first")
                return 0
        except ValueError:
            pass

    state = {
        "version": 1,
        "t_on_epoch": util.epoch(),
        "host": env.host_info(REPO_ROOT).get("hostname", ""),
        "actions": [],
        "dry_run": bool(getattr(args, "dry_run", False)),
    }

    # --- Ollama ---------------------------------------------------------
    ollama = {"installed": util.have("ollama"), "unit": "ollama",
              "system_active": systemctl_active("ollama") if util.have("ollama") else None,
              "system_enabled": systemctl_enabled("ollama") if util.have("ollama") else None,
              "loaded_models": ollama_ps()}
    ollama["action"] = "none"
    if ollama["installed"]:
        if ollama["system_active"]:
            if state["dry_run"]:
                ollama["action"] = "would_stop_service"
            else:
                rc, msg = systemctl("stop", "ollama")
                ollama["action"] = "stopped_service" if rc == 0 else "stop_failed"
                ollama["stop_result"] = msg
                state["actions"].append(f"systemctl stop ollama rc={rc}")
        elif ollama["loaded_models"]:
            if state["dry_run"]:
                ollama["action"] = "would_unload_models"
            else:
                stopped = []
                for m in ollama["loaded_models"]:
                    rc, _, _ = util.run_capture(["ollama", "stop", m["name"]], timeout=20)
                    stopped.append({"model": m["name"], "rc": rc})
                ollama["action"] = "unloaded_models"
                ollama["unload_results"] = stopped
                state["actions"].append(f"ollama stop {len(stopped)} models")
    state["ollama"] = ollama

    # --- heavy processes (recorded only) --------------------------------
    state["heavy_processes"] = top_processes()

    # --- containers -----------------------------------------------------
    state["containers"] = busy_containers()
    state["containers_action"] = "recorded"
    if args.pause_containers and state["containers"]:
        if state["dry_run"]:
            state["containers_action"] = "would_pause"
        else:
            paused = []
            for c in state["containers"]:
                rc, out, err = util.run_capture(["docker", "pause", c["name"]], timeout=20)
                paused.append({"name": c["name"], "rc": rc})
            state["containers_action"] = "paused"
            state["containers_paused"] = paused
            state["actions"].append(f"docker pause {len(paused)} containers")

    state["restored"] = False
    _write_state(state, args.run_dir)
    print(f"quiesce on: {json.dumps({'ollama': ollama['action'], 'heavy': len(state['heavy_processes']), 'containers': len(state['containers'])})}")
    return 0


def quiesce_off(args) -> int:
    state_path = args.state or STATE_PATH
    if not os.path.exists(state_path):
        print(f"quiesce not on (no state at {state_path})")
        return 0
    with open(state_path) as fh:
        state = json.load(fh)
    if state.get("restored"):
        print("quiesce already restored")
        return 0

    actions = []
    ollama = state.get("ollama", {})
    if state.get("dry_run"):
        actions.append("dry-run: nothing was changed, nothing to restore")
    elif ollama.get("installed"):
        if ollama.get("action") == "stopped_service" and ollama.get("system_active"):
            rc, msg = systemctl("start", "ollama")
            actions.append(f"systemctl start ollama rc={rc}")
            # best-effort: re-warm models that were loaded before we stopped it
            if rc == 0 and ollama.get("loaded_models") and args.rewarm:
                for m in ollama["loaded_models"]:
                    rc2, _, _ = util.run_capture(["ollama", "run", m["name"], ""], timeout=60)
                    actions.append(f"rewarm {m['name']} rc={rc2}")
        elif ollama.get("action") == "unloaded_models":
            actions.append("models were unloaded; they reload on demand (not re-warmed)")

    if not state.get("dry_run") and state.get("containers_action") == "paused":
        for c in state.get("containers_paused", []):
            rc, _, _ = util.run_capture(["docker", "unpause", c["name"]], timeout=20)
            actions.append(f"docker unpause {c['name']} rc={rc}")

    state["restored"] = True
    state["t_off_epoch"] = util.epoch()
    state["restore_actions"] = actions
    _write_state(state, args.run_dir, state_path=state_path)
    print("quiesce off restored: " + ("; ".join(actions) if actions else "nothing to restore"))
    return 0


def quiesce_status(args) -> int:
    state_path = args.state or STATE_PATH
    if not os.path.exists(state_path):
        print("quiesce off")
        return 0
    with open(state_path) as fh:
        state = json.load(fh)
    print(json.dumps({
        "active": not state.get("restored", False),
        "t_on_epoch": state.get("t_on_epoch"),
        "ollama_action": state.get("ollama", {}).get("action"),
        "ollama_was_active": state.get("ollama", {}).get("system_active"),
        "containers": len(state.get("containers", [])),
    }, indent=2))
    return 0


def _write_state(state: dict, run_dir: Optional[str] = None, state_path: str = STATE_PATH) -> None:
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    tmp = state_path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(state, fh, indent=2, sort_keys=True, default=str)
        fh.write("\n")
    os.replace(tmp, state_path)
    if run_dir and os.path.isdir(run_dir):
        dst = os.path.join(run_dir, "quiesce-state.json")
        try:
            with open(dst, "w") as fh:
                json.dump(state, fh, indent=2, sort_keys=True, default=str)
                fh.write("\n")
        except OSError:
            pass


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(prog="stutter quiesce")
    sub = ap.add_subparsers(dest="cmd", required=True)
    on = sub.add_parser("on")
    on.add_argument("--run-dir", default="")
    on.add_argument("--pause-containers", action="store_true")
    on.add_argument("--dry-run", action="store_true",
                    help="record the state and what would be stopped, but change nothing")
    on.set_defaults(func=quiesce_on)
    off = sub.add_parser("off")
    off.add_argument("--run-dir", default="")
    off.add_argument("--state", default="")
    off.add_argument("--rewarm", action="store_true",
                     help="re-load Ollama models that were loaded before quiesce")
    off.set_defaults(func=quiesce_off)
    st = sub.add_parser("status")
    st.add_argument("--state", default="")
    st.set_defaults(func=quiesce_status)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
