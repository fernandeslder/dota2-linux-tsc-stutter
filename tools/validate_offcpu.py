#!/usr/bin/env python3
"""Validate the `offcpu` sampler + blocked-on report on a synthetic app (vkcube).

Takes the shared GPU test lock `/tmp/stutter-test.lock` itself and **refuses to
run without it**, so it can never perturb a live Dota trial.  Wait up to
``--lock-timeout`` seconds (default 600; 0 = fail fast).

Two phases run the same app under MangoHud for ``--seconds`` each:

  A  control : `stutter collect start --no-offcpu`
  B  offcpu  : `stutter collect start` (100 Hz + --offcpu-stacks), plus `--deep`

It compares frametime p50/p95/p99/mean (budget: |delta| < 0.2 ms for p50/p99),
prints the delta, then dumps ``meta.offcpu``, the ranked ``out/blocked_on.csv``
and the head of ``deep_offcpu.log``.  Exit code 0 = within budget and the
off-CPU artifacts are non-empty.

Usage: python3 tools/validate_offcpu.py [--seconds 20] [--app vkcube]
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import signal
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from detector.collect import mangohud  # noqa: E402
from detector.collect.rundir import RunDir  # noqa: E402

BIN = os.path.join(ROOT, "bin", "stutter")
RUNS = os.path.join(ROOT, "runs")
LOCK = "/tmp/stutter-test.lock"


def acquire_lock(timeout: float):
    fd = os.open(LOCK, os.O_RDWR | os.O_CREAT, 0o644)
    t0 = time.time()
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fd
        except OSError:
            if timeout <= 0 or time.time() - t0 > timeout:
                os.close(fd)
                return None
            print(f"[lock] busy, waiting... ({time.time()-t0:.0f}s)", flush=True)
            time.sleep(2)


def _launch(app, conf):
    env = dict(os.environ)
    env["MANGOHUD"] = "1"
    if conf:
        env["MANGOHUD_CONFIGFILE"] = conf
    return subprocess.Popen(["mangohud", app], cwd=ROOT, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=True)


def _stop(p):
    try:
        p.terminate()
        p.wait(timeout=5)
    except Exception:
        try:
            p.kill()
        except Exception:
            pass


def read_frames(run_dir):
    path = os.path.join(run_dir, "frametimes.csv")
    out = []
    if os.path.exists(path):
        with open(path) as fh:
            next(fh, None)
            for line in fh:
                parts = line.split(",")
                if len(parts) >= 2 and parts[1].strip():
                    out.append(float(parts[1]))
    return out


def phase(app, seconds, work, label, extra, game_comm=None):
    run_dir = os.path.join(work, label)
    cmd = [BIN, "collect", "start", "--label", label, "--profile", "full",
           "--run-dir", run_dir, "--duration", str(seconds + 6)] + extra
    env = dict(os.environ)
    if game_comm:
        # point the collector's process discovery at the app we launch, so the
        # off-CPU sampler targets the same process whose frametimes we measure
        env["STUTTER_GAME_COMM"] = game_comm
    subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, env=env)
    rd = RunDir(run_dir)
    conf = rd.read_meta().get("mangohud", {}).get("config_file")
    p = _launch(app, conf)
    time.sleep(seconds)
    _stop(p)
    time.sleep(1.0)
    subprocess.run([BIN, "collect", "stop", "--run-dir", run_dir],
                   cwd=ROOT, capture_output=True, text=True)
    return run_dir, read_frames(run_dir)


def stats(frames):
    import numpy as np
    a = np.asarray(frames, dtype=float)
    if a.size == 0:
        return {}
    return {"n": int(a.size), "mean": float(a.mean()),
            "p50": float(np.percentile(a, 50)),
            "p95": float(np.percentile(a, 95)),
            "p99": float(np.percentile(a, 99))}


def boot_ci_diff(a, b, q, n=2000, seed=1):
    """95% bootstrap CI for percentile(a, q) - percentile(b, q)."""
    import numpy as np
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    rng = np.random.default_rng(seed)
    d = np.empty(n)
    for i in range(n):
        d[i] = (np.percentile(rng.choice(a, a.size), q)
                - np.percentile(rng.choice(b, b.size), q))
    return float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", default="vkcube")
    ap.add_argument("--game-comm", default=None,
                    help="STUTTER_GAME_COMM to target (default: same as --app)")
    ap.add_argument("--seconds", type=float, default=20.0)
    ap.add_argument("--repeat", type=int, default=1,
                    help="run both phases N times and pool the frames (tightens p99)")
    ap.add_argument("--lock-timeout", type=float, default=600.0)
    args = ap.parse_args()
    if args.game_comm is None:
        args.game_comm = args.app

    fd = acquire_lock(args.lock_timeout)
    if fd is None:
        print(f"[lock] could not acquire {LOCK} within {args.lock_timeout:.0f}s; "
              "not running (would perturb a live trial)")
        return 3
    print(f"[lock] acquired {LOCK}")

    ts = time.strftime("%Y%m%d-%H%M%S")
    work = os.path.join(RUNS, f"offcpu-validate-{ts}")
    os.makedirs(work, exist_ok=True)
    print(f"[work] {work}")
    cframes, oframes, per_repeat = [], [], []
    odir = None
    try:
        for i in range(max(1, args.repeat)):
            print(f"[A{i+1}] control (--no-offcpu)...", flush=True)
            _, cf = phase(args.app, args.seconds, work, f"control-{i+1}",
                          ["--no-offcpu"], game_comm=args.game_comm)
            print(f"[B{i+1}] offcpu 100 Hz + stacks + deep...", flush=True)
            odir, of = phase(args.app, args.seconds, work, f"offcpu-{i+1}",
                             ["--offcpu-hz", "100", "--offcpu-stacks", "--deep"],
                             game_comm=args.game_comm)
            cframes += cf
            oframes += of
            per_repeat.append((stats(cf), stats(of)))
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
        print("[lock] released")

    cs, os_ = stats(cframes), stats(oframes)
    print("\n| metric | control | offcpu | delta |")
    print("|---|---|---|---|")
    for k in ("n", "mean", "p50", "p95", "p99"):
        cv, ov = cs.get(k), os_.get(k)
        if cv is None or ov is None:
            print(f"| {k} | - | - | - |")
        else:
            print(f"| {k} | {cv:.3f} | {ov:.3f} | {ov - cv:+.3f} |")
    if len(per_repeat) > 1:
        parts = []
        for c, o in per_repeat:
            parts.append(f"{o.get('p50', 0.0) - c.get('p50', 0.0):+.3f}/"
                         f"{o.get('p99', 0.0) - c.get('p99', 0.0):+.3f}")
        print("\nper-repeat delta (p50/p99 ms): " + ", ".join(parts))
    if cframes and oframes:
        for q in (50, 99):
            lo, hi = boot_ci_diff(oframes, cframes, q)
            print(f"[p{q}] delta {os_[f'p{q}'] - cs[f'p{q}']:+.3f} ms, "
                  f"95% bootstrap CI [{lo:+.3f}, {hi:+.3f}]")

    meta = RunDir(odir).read_meta()
    print("\n[meta.offcpu]", json.dumps(meta.get("offcpu"), indent=2))
    print("[meta.deep]", json.dumps(meta.get("deep"), indent=2))
    print("[meta.collector_skipped]", json.dumps(meta.get("collector_skipped"), indent=2))

    blocked = os.path.join(odir, "out", "blocked_on.csv")
    if os.path.exists(blocked):
        print("\n[blocked_on.csv]")
        with open(blocked) as fh:
            for i, line in enumerate(fh):
                if i > 8:
                    print("  ...")
                    break
                print("  " + line.rstrip())
    deep = os.path.join(odir, "deep_offcpu.log")
    if os.path.exists(deep):
        print("\n[deep_offcpu.log]")
        with open(deep) as fh:
            for i, line in enumerate(fh):
                if i > 6:
                    print("  ...")
                    break
                print("  " + line.rstrip())
    else:
        print("\n[deep_offcpu.log] MISSING")

    ok = True
    if not (cs and os_):
        print("FAIL: no frames captured")
        ok = False
    else:
        for k in ("p50", "p99"):
            if abs(os_[k] - cs[k]) > 0.2:
                print(f"FAIL: {k} delta {os_[k]-cs[k]:+.3f} ms > 0.2 ms budget")
                ok = False
    info = meta.get("offcpu") or {}
    if not info.get("pid"):
        print(f"FAIL: collector never found the app (STUTTER_GAME_COMM={args.game_comm}); "
              "the off-CPU sampler did not run")
        ok = False
    if info.get("blocked_rows", 0) < 1:
        print("FAIL: threads_blocked.csv empty")
        ok = False
    print("\n" + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
