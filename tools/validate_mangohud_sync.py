#!/usr/bin/env python3
"""Validate the MangoHud relative-time -> CLOCK_REALTIME epoch mapping.

Method: run the collector, launch a synthetic 144 fps app (vkcube) under
MangoHud, then freeze it with SIGSTOP for a known interval.  The frozen frame
is the largest frametime spike in the log; the instant it *completes* is the
SIGCONT time.  From the spike's `elapsed` value we recover the implied logging
start and compare it against the log file's statx birth time:

    implied_t0 = t_cont - elapsed_spike/1e9
    delta      = btime - implied_t0        (want |delta| <= 50 ms)

It also checks the collector's own frametimes.csv for the spike and reports the
residual against the SIGCONT marker.

Usage:  python3 tools/validate_mangohud_sync.py [--stop-ms 60] [--settle 6]
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from detector.collect import mangohud, util  # noqa: E402
from detector.collect.rundir import RunDir  # noqa: E402

BIN = os.path.join(ROOT, "bin", "stutter")


def _run(cmd, **kw):
    return subprocess.run(cmd, cwd=ROOT, **kw)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="syncval")
    ap.add_argument("--app", default="vkcube")
    ap.add_argument("--settle", type=float, default=6.0, help="seconds before the stop")
    ap.add_argument("--after", type=float, default=3.0, help="seconds after resume")
    ap.add_argument("--stop-ms", type=float, default=60.0)
    ap.add_argument("--offset", type=float, default=0.0)
    args = ap.parse_args()

    start = _run([BIN, "collect", "start", "--label", args.label,
                  "--mangohud-offset", str(args.offset)],
                 capture_output=True, text=True)
    print(start.stdout.strip())
    if start.returncode != 0:
        print(start.stderr, file=sys.stderr)
        return 1
    run_dir = None
    for line in start.stdout.splitlines():
        if line.startswith("run_dir:"):
            run_dir = line.split(":", 1)[1].strip()
    assert run_dir, "run_dir not reported"
    rd = RunDir(run_dir)
    conf = rd.read_meta()["mangohud"]["config_file"]

    env = dict(os.environ)
    env["MANGOHUD_CONFIGFILE"] = conf
    env["MANGOHUD"] = "1"
    app = subprocess.Popen(["mangohud", args.app], cwd=ROOT, env=env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           start_new_session=True)
    try:
        time.sleep(args.settle)
        t_send = util.epoch()
        os.kill(app.pid, signal.SIGSTOP)
        time.sleep(args.stop_ms / 1000.0)
        t_cont = util.epoch()
        os.kill(app.pid, signal.SIGCONT)
        _run([BIN, "collect", "mark", "injected_stall",
              "--detail", f"t_send={t_send:.6f} t_cont={t_cont:.6f} dur_ms={args.stop_ms}"],
             capture_output=True, text=True)
        time.sleep(args.after)
    finally:
        try:
            app.terminate()
            app.wait(timeout=5)
        except Exception:
            app.kill()
    _run([BIN, "collect", "stop"], capture_output=True, text=True)

    # ---- analyse ---------------------------------------------------------
    meta = rd.read_meta()
    log_file = meta.get("mangohud_log")
    btime_ns = meta.get("mangohud_birth_ns")
    if not log_file or not os.path.exists(log_file):
        print("FAIL: no MangoHud log captured")
        return 2
    frames = mangohud.read_frames(log_file)
    if not frames:
        print("FAIL: MangoHud log has no frames")
        return 2
    spikes = sorted(range(len(frames)), key=lambda i: frames[i][1], reverse=True)[:3]
    print(f"log_file={log_file}")
    print(f"btime={btime_ns/1e9 if btime_ns else None} t_cont={t_cont:.6f}")
    print(f"frames={len(frames)}")
    i = spikes[0]
    elapsed_ns, ft_ms = frames[i]
    implied_t0 = t_cont - elapsed_ns / 1e9
    delta_ms = ((btime_ns / 1e9) - implied_t0) * 1000.0 if btime_ns else None
    print(f"top spike: idx={i} frametime={ft_ms:.2f}ms elapsed={elapsed_ns/1e9:.4f}s")
    print(f"implied_t0={implied_t0:.6f}")
    if delta_ms is not None:
        print(f"btime - implied_t0 = {delta_ms:+.2f} ms  (target |delta| <= 50 ms)")
    # collector's frametimes.csv
    best = None
    with open(rd.frametimes_path) as fh:
        next(fh)
        for line in fh:
            t, v = line.split(",")[:2]
            t, v = float(t), float(v)
            if best is None or v > best[1]:
                best = (t, v)
    if best:
        print(f"collector frametimes: max {best[1]:.2f}ms at t={best[0]:.6f} "
              f"(residual vs t_cont {1000*(best[0]-t_cont):+.2f} ms)")
    ok = delta_ms is not None and abs(delta_ms) <= 50.0
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
