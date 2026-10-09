#!/usr/bin/env python3
"""Quantify collector overhead on a synthetic app.

Runs the same app (default vkcube, VSYNC-capped to the display refresh ~=144 fps)
under three conditions and compares the frametime distribution:

  1. mangohud-only        : MangoHud log, no collector
  2. full                 : MangoHud log + `stutter collect` (profile full)
  3. lite                 : MangoHud log + `stutter collect` (profile lite)

Outputs a markdown table + JSON under runs/overhead-<ts>/ and prints the table.

Usage: python3 tools/collector_overhead.py [--seconds 30] [--app vkcube] [--skip-lite]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from detector.collect import mangohud, util  # noqa: E402
from detector.collect.rundir import RunDir  # noqa: E402

BIN = os.path.join(ROOT, "bin", "stutter")
RUNS = os.path.join(ROOT, "runs")


def _stats(frametimes_ms):
    import numpy as np
    a = np.asarray(frametimes_ms, dtype=float)
    if a.size == 0:
        return {}
    return {
        "n": int(a.size),
        "mean_ms": round(float(a.mean()), 3),
        "p50_ms": round(float(np.percentile(a, 50)), 3),
        "p95_ms": round(float(np.percentile(a, 95)), 3),
        "p99_ms": round(float(np.percentile(a, 99)), 3),
        "p999_ms": round(float(np.percentile(a, 99.9)), 3),
        "max_ms": round(float(a.max()), 3),
        "std_ms": round(float(a.std()), 3),
        # hitch proxy: >2.5x the 13.9ms 144fps budget (final K set by analyze)
        "hitches_gt34_75ms": int((a > 34.75).sum()),
    }


def _launch_app(app, conf):
    env = dict(os.environ)
    env["MANGOHUD"] = "1"
    if conf:
        env["MANGOHUD_CONFIGFILE"] = conf
    return subprocess.Popen(["mangohud", app], cwd=ROOT, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=True)


def _stop_app(p):
    try:
        p.terminate()
        p.wait(timeout=5)
    except Exception:
        try:
            p.kill()
        except Exception:
            pass


def phase_mangohud_only(app, seconds, work):
    folder = os.path.join(work, "mh_only")
    os.makedirs(folder, exist_ok=True)
    conf = mangohud.write_config_file(os.path.join(folder, "mh.conf"),
                                      mangohud.default_config(folder))
    p = _launch_app(app, conf)
    time.sleep(seconds)
    _stop_app(p)
    time.sleep(0.5)
    log = mangohud.find_log_file(folder)
    frames = mangohud.read_frames(log) if log else []
    return _stats([ft for _el, ft in frames]), log


def phase_collector(app, seconds, work, profile):
    run_dir = os.path.join(work, f"run_{profile}")
    subprocess.run([BIN, "collect", "start", "--label", f"overhead-{profile}",
                    "--profile", profile, "--run-dir", run_dir],
                   cwd=ROOT, capture_output=True, text=True)
    rd = RunDir(run_dir)
    conf = rd.read_meta()["mangohud"]["config_file"]
    p = _launch_app(app, conf)
    time.sleep(seconds)
    _stop_app(p)
    time.sleep(1.0)
    subprocess.run([BIN, "collect", "stop", "--run-dir", run_dir],
                   cwd=ROOT, capture_output=True, text=True)
    frames = []
    if os.path.exists(rd.frametimes_path):
        with open(rd.frametimes_path) as fh:
            next(fh, None)
            for line in fh:
                parts = line.split(",")
                if len(parts) >= 2 and parts[1].strip():
                    frames.append(float(parts[1]))
    return _stats(frames), run_dir


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", default="vkcube")
    ap.add_argument("--seconds", type=float, default=30.0)
    ap.add_argument("--skip-lite", action="store_true")
    args = ap.parse_args()

    ts = time.strftime("%Y%m%d-%H%M%S")
    work = os.path.join(RUNS, f"overhead-{ts}")
    os.makedirs(work, exist_ok=True)

    results = {}
    print(f"[overhead] workdir {work}")
    for name in (["mangohud_only", "full"] + ([] if args.skip_lite else ["lite"])):
        print(f"[overhead] phase {name} ({args.seconds}s)...")
        t0 = util.epoch()
        if name == "mangohud_only":
            stats, ref = phase_mangohud_only(args.app, args.seconds, work)
        else:
            stats, ref = phase_collector(args.app, args.seconds, work, name)
        stats["seconds"] = args.seconds
        stats["t_start_epoch"] = t0
        stats["artifact"] = ref
        results[name] = stats
        print(f"           {stats}")

    base = results.get("mangohud_only", {})
    lines = ["# Collector overhead on a synthetic app", "",
             f"- app: `{args.app}` , {args.seconds:.0f}s per phase",
             f"- generated: {time.strftime('%Y-%m-%d %H:%M:%S')}", "",
             "| metric | mangohud only | full | lite | full delta | lite delta |",
             "|---|---|---|---|---|---|"]
    for k in ("n", "mean_ms", "p50_ms", "p95_ms", "p99_ms", "p999_ms", "max_ms",
              "std_ms", "hitches_gt34_75ms"):
        row = [k, base.get(k, "-"), results.get("full", {}).get(k, "-"),
               results.get("lite", {}).get(k, "-")]
        for variant in ("full", "lite"):
            v = results.get(variant, {}).get(k)
            b = base.get(k)
            if isinstance(v, (int, float)) and isinstance(b, (int, float)):
                row.append(f"{v - b:+.3f}")
            else:
                row.append("-")
        lines.append("| " + " | ".join(str(x) for x in row) + " |")
    report = "\n".join(lines) + "\n"
    with open(os.path.join(work, "report.md"), "w") as fh:
        fh.write(report)
    with open(os.path.join(work, "report.json"), "w") as fh:
        json.dump(results, fh, indent=2)
    print()
    print(report)
    print(f"[overhead] wrote {work}/report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
