"""E2E validation harness: REAL capture (vkcube + MangoHud + full collectors)
-> detect/report. Ground truth = injected SIGSTOP/SIGCONT stalls + CPU-burn bursts.

Writes derived summaries only (runs/validate-*/out/ + runs/validate-*/e2e-*.json);
raw/ stays gitignored. Must be run under the shared lock:
  flock /tmp/stutter-test.lock python3 tools/e2e_validate.py [scenario...]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import signal
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from detector.collect import util  # noqa: E402
from detector.collect.rundir import RunDir  # noqa: E402

BIN = os.path.join(ROOT, "bin", "stutter")
APP = "vkcube"
WARMUP_S = 20.0


def run(cmd, **kw):
    if cmd and cmd[0] == BIN:
        cmd = ["sh", BIN] + list(cmd[1:])
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, **kw)


def start_run(label, profile="full", warmup=WARMUP_S, run_dir=None):
    cmd = [BIN, "collect", "start", "--label", label, "--profile", profile,
           "--warmup", str(warmup)]
    if run_dir:
        cmd += ["--run-dir", run_dir]
    r = run(cmd)
    if r.returncode != 0:
        raise RuntimeError(f"collect start failed: {r.stdout}\n{r.stderr}")
    rd_path = None
    for line in r.stdout.splitlines():
        if line.startswith("run_dir:"):
            rd_path = line.split(":", 1)[1].strip()
    assert rd_path, f"no run_dir in output: {r.stdout}"
    return rd_path


def mark(label, detail="", run_dir=None):
    cmd = [BIN, "collect", "mark", label, "--detail", detail]
    if run_dir:
        cmd += ["--run-dir", run_dir]
    r = run(cmd)
    if r.returncode != 0:
        raise RuntimeError(f"mark failed: {r.stdout}\n{r.stderr}")
    return r.stdout.strip()


def stop_run(run_dir=None):
    cmd = [BIN, "collect", "stop"]
    if run_dir:
        cmd += ["--run-dir", run_dir]
    r = run(cmd)
    print(r.stdout.strip())
    if r.returncode != 0:
        raise RuntimeError(f"collect stop failed: {r.stdout}\n{r.stderr}")


def launch_app(conf):
    env = dict(os.environ)
    env["MANGOHUD"] = "1"
    env["MANGOHUD_CONFIGFILE"] = conf
    env["LD_PRELOAD"] = ""
    # exec so the wrapper pid IS vkcube (reliable SIGSTOP/SIGTERM/reap)
    return subprocess.Popen(["/bin/sh", "-c", "exec " + APP], cwd=ROOT, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=True)


def stop_app(app, timeout=5.0):
    try:
        os.killpg(os.getpgid(app.pid), signal.SIGTERM)
    except OSError:
        try:
            os.kill(app.pid, signal.SIGTERM)
        except OSError:
            return
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if app.poll() is not None:
            return
        time.sleep(0.1)
    try:
        os.killpg(os.getpgid(app.pid), signal.SIGKILL)
    except OSError:
        try:
            app.kill()
        except Exception:
            pass
    try:
        app.wait(timeout=5)
    except Exception:
        pass


def game_pid_of(app):
    """PID of the vkcube process (== wrapper pid with exec launch)."""
    return app.pid


def inject_stall(app, dur_ms, run_dir=None):
    """SIGSTOP burst; ground truth marker records SIGCONT epoch (== spike end)."""
    tgt = game_pid_of(app)
    t_send = util.epoch()
    os.kill(tgt, signal.SIGSTOP)
    time.sleep(dur_ms / 1000.0)
    t_cont = util.epoch()
    os.kill(tgt, signal.SIGCONT)
    mark("injected_stall",
         f"t_send={t_send:.6f} t_cont={t_cont:.6f} dur_ms={dur_ms} pid={app.pid}",
         run_dir=run_dir)
    return t_send, t_cont


def _spawn_load(cpus, nproc=4):
    """Start busy-loop workers pinned round-robin to ``cpus``; return the procs."""
    procs = []
    for i in range(nproc):
        cpu = cpus[i % len(cpus)]
        p = subprocess.Popen(["taskset", "-c", str(cpu), "sh", "-c", "while :; do :; done"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
        procs.append(p)
    return procs


def _kill_load(procs):
    for p in procs:
        try:
            p.terminate()
        except Exception:
            pass
    for p in procs:
        try:
            p.wait(timeout=5)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass


def inject_cpu_burn(dur_ms, nproc=4, run_dir=None, label="cpu_burn", cpus=None):
    """CPU stress burst (yes-loop workers); optionally pinned to specific CPUs."""
    procs = _spawn_load(cpus, nproc) if cpus else _spawn_load(list(range(nproc)), nproc)
    t0 = util.epoch()
    time.sleep(dur_ms / 1000.0)
    t1 = util.epoch()
    _kill_load(procs)
    mark(label, f"t0={t0:.6f} t1={t1:.6f} dur_ms={dur_ms} nproc={nproc} cpus={cpus}",
         run_dir=run_dir)
    return t0, t1


def load_excursion(run_dir, burns):
    """Verify a burn actually moved a *recorded* signal: mean procs_running (sys.csv)
    and mean per-burn-core util (cpu.csv) inside vs outside the burn windows."""
    import numpy as np
    out = {"n_burns": len(burns)}
    try:
        with open(os.path.join(run_dir, "sys.csv")) as fh:
            rows = list(csv.DictReader(fh))
        t = np.array([float(r["t_epoch"]) for r in rows])
        pr = np.array([float(r["procs_running"] or 0) for r in rows])
        hit = np.zeros(t.size, dtype=bool)
        for b in burns:
            hit |= (t >= b["t0"]) & (t <= b["t1"] + 0.2)
        if hit.any() and (~hit).any():
            out["procs_running_burn_mean"] = float(pr[hit].mean())
            out["procs_running_base_mean"] = float(pr[~hit].mean())
    except (OSError, KeyError, ValueError):
        pass
    cpus = sorted({c for b in burns for c in b.get("cpus", [])})
    if cpus:
        try:
            with open(os.path.join(run_dir, "cpu.csv")) as fh:
                rows = list(csv.DictReader(fh))
            t = np.array([float(r["t_epoch"]) for r in rows])
            hit = np.zeros(t.size, dtype=bool)
            for b in burns:
                hit |= (t >= b["t0"]) & (t <= b["t1"] + 0.2)
            vals = []
            for c in cpus:
                col = f"cpu{c}_util"
                if col in rows[0]:
                    v = np.array([float(r[col] or 0) for r in rows])
                    vals.append(v)
            if vals and hit.any() and (~hit).any():
                m = np.mean(vals, axis=0)
                out["burn_core_util_burn_mean"] = float(m[hit].mean())
                out["burn_core_util_base_mean"] = float(m[~hit].mean())
        except (OSError, KeyError, ValueError):
            pass
    return out


def busiest_cpu(run_dir, default=0):
    """Latest ``busiest_cpu`` from the game's threads.csv (0 if unavailable)."""
    p = os.path.join(run_dir, "threads.csv")
    try:
        with open(p) as fh:
            r = list(csv.DictReader(fh))
    except OSError:
        return default
    for row in reversed(r):
        v = (row.get("busiest_cpu") or "").strip()
        if v:
            try:
                return int(float(v))
            except ValueError:
                continue
    return default


def mixed_schedule(dur_s, period_s, sparse_s, offset_s, dur_lo, dur_hi, rng,
                   guard_s=0.6):
    """Pure schedule for the mixed scenario: periodic + sparse, decoupled.

    Returns a time-ordered list of ``(kind, t_rel_s, dur_ms)``. The periodic beat is
    advanced past the sparse tick (>= ``guard_s``) so a sparse stall never lands
    adjacent to a periodic one (the bug that made the previous mixed run a pure
    periodic run -- see docs/VALIDATION-e2e.md §4 / bug B1).
    """
    events = []
    next_periodic = period_s
    next_sparse = offset_s
    while True:
        if next_periodic >= dur_s and next_sparse >= dur_s:
            break
        if next_sparse <= next_periodic:
            if next_sparse >= dur_s:
                break
            events.append(("sparse", next_sparse, rng.uniform(dur_lo, dur_hi)))
            next_sparse += sparse_s
            while next_periodic <= events[-1][1] + guard_s:
                next_periodic += period_s
        else:
            if next_periodic >= dur_s:
                break
            # never land a periodic beat just before an upcoming sparse tick
            if next_sparse - next_periodic < guard_s:
                next_periodic += period_s
                continue
            events.append(("periodic", next_periodic, rng.uniform(dur_lo, dur_hi)))
            next_periodic += period_s
    return events


def loop_fixed(app, total_s, period_s, dur_ms_fn, run_dir, extra=None):
    """Inject stalls every period_s for total_s. Returns list of (t_send,t_cont,dur)."""
    gt = []
    t_end = time.monotonic() + total_s
    i = 0
    while time.monotonic() < t_end - period_s * 0.5:
        time.sleep(period_s)
        if time.monotonic() >= t_end:
            break
        dur = dur_ms_fn(i)
        gt.append((*inject_stall(app, dur, run_dir), dur))
        i += 1
        if extra:
            extra(i, gt)
    return gt


def save_gt(run_dir, gt, **kw):
    gt_rows = [{"t_send": a, "t_cont": b, "dur_ms": c} for a, b, c in gt]
    path = os.path.join(run_dir, "e2e-ground-truth.json")
    with open(path, "w") as fh:
        json.dump({"stalls": gt_rows, **kw}, fh, indent=2)
    return path


def load_gt(run_dir):
    with open(os.path.join(run_dir, "e2e-ground-truth.json")) as fh:
        return json.load(fh)


def read_hitches(run_dir):
    p = os.path.join(run_dir, "out", "hitches.csv")
    rows = []
    with open(p) as fh:
        for r in csv.DictReader(fh):
            rows.append((float(r["t_epoch"]), float(r["magnitude_ms"])))
    return rows


def score_detection(gt, hitches, tol_s=0.5):
    """Match each GT stall to nearest hitch within tol; report precision/recall
    and marker->spike epoch error distribution (hitch t - t_cont)."""
    used = [False] * len(hitches)
    tp_err, fn = [], 0
    for a, b, dur in gt:
        best, bestj = None, -1
        for j, (ht, hm) in enumerate(hitches):
            if used[j]:
                continue
            d = ht - b
            if abs(d) <= tol_s and (best is None or abs(d) < abs(best)):
                best, bestj = d, j
        if best is None:
            fn += 1
        else:
            used[bestj] = True
            tp_err.append(best)
    tp = len(tp_err)
    fp = sum(1 for u in used if not u)
    prec = tp / max(1, tp + fp)
    rec = tp / max(1, tp + fn)
    return {"tp": tp, "fp": fp, "fn": fn, "precision": round(prec, 4),
            "recall": round(rec, 4),
            "err_ms": sorted(round(e * 1000, 1) for e in tp_err)}


def scenario_clean(run_dir, dur_s=600.0):
    rd_path = start_run("e2e-clean", run_dir=run_dir)
    rd = RunDir(rd_path)
    conf = rd.read_meta()["mangohud"]["config_file"]
    app = launch_app(conf)
    try:
        time.sleep(WARMUP_S)
        mark("warmup_end", "e2e harness", run_dir=rd_path)
        time.sleep(dur_s)
    finally:
        stop_app(app)
        time.sleep(1.0)
        stop_run(rd_path)
    save_gt(rd_path, [], scenario="clean")
    print(f"CLEAN done: {rd_path}")
    return rd_path


def scenario_periodic(run_dir, dur_s=360.0, period_s=4.0, dur_lo=40.0, dur_hi=80.0):
    rd_path = start_run("e2e-periodic4s", run_dir=run_dir)
    rd = RunDir(rd_path)
    conf = rd.read_meta()["mangohud"]["config_file"]
    app = launch_app(conf)
    try:
        time.sleep(WARMUP_S)
        mark("warmup_end", "e2e harness", run_dir=rd_path)
        import random
        rng = random.Random(7)
        gt = loop_fixed(app, dur_s, period_s,
                        lambda i: rng.uniform(dur_lo, dur_hi), rd_path)
    finally:
        stop_app(app)
        time.sleep(1.0)
        stop_run(rd_path)
    save_gt(rd_path, gt, scenario="periodic", period_s=period_s)
    print(f"PERIODIC done: {rd_path} n_gt={len(gt)}")
    return rd_path


def scenario_sparse(run_dir, dur_s=600.0, period_s=45.0, dur_lo=40.0, dur_hi=80.0):
    rd_path = start_run("e2e-sparse45s", run_dir=run_dir)
    rd = RunDir(rd_path)
    conf = rd.read_meta()["mangohud"]["config_file"]
    app = launch_app(conf)
    try:
        time.sleep(WARMUP_S)
        mark("warmup_end", "e2e harness", run_dir=rd_path)
        import random
        rng = random.Random(11)
        gt = loop_fixed(app, dur_s, period_s,
                        lambda i: rng.uniform(dur_lo, dur_hi), rd_path)
    finally:
        stop_app(app)
        time.sleep(1.0)
        stop_run(rd_path)
    save_gt(rd_path, gt, scenario="sparse", period_s=period_s)
    print(f"SPARSE done: {rd_path} n_gt={len(gt)}")
    return rd_path


def scenario_mixed(run_dir, dur_s=600.0, period_s=4.0, sparse_s=45.0, offset_s=22.5):
    """4 s periodic + 45 s sparse, injected on two decoupled schedules (bug B1 fix)."""
    rd_path = start_run("e2e-mixed", run_dir=run_dir)
    rd = RunDir(rd_path)
    conf = rd.read_meta()["mangohud"]["config_file"]
    app = launch_app(conf)
    try:
        time.sleep(WARMUP_S)
        mark("warmup_end", "e2e harness", run_dir=rd_path)
        import random
        rng = random.Random(21)
        sched = mixed_schedule(dur_s, period_s, sparse_s, offset_s, 40.0, 80.0, rng)
        t_start = time.monotonic()
        gt = []
        for kind, t_rel, dur in sched:
            dt = (t_start + t_rel) - time.monotonic()
            if dt > 0:
                time.sleep(dt)
            gt.append((*inject_stall(app, dur, rd_path), dur))
    finally:
        stop_app(app)
        time.sleep(1.0)
        stop_run(rd_path)
    n_sparse = sum(1 for k, _, _ in sched if k == "sparse")
    save_gt(rd_path, gt, scenario="mixed", period_s=period_s,
            sparse_s=sparse_s, n_sparse_planned=n_sparse)
    print(f"MIXED done: {rd_path} n_gt={len(gt)} n_sparse={n_sparse}")
    return rd_path


def scenario_short_sparse(run_dir, dur_s=120.0, period_s=4.0):
    return scenario_periodic(run_dir, dur_s=dur_s, period_s=period_s)


def scenario_borderline(run_dir, dur_s=360.0, period_s=4.0, durs=(20.0, 30.0)):
    rd_path = start_run("e2e-borderline", run_dir=run_dir)
    rd = RunDir(rd_path)
    conf = rd.read_meta()["mangohud"]["config_file"]
    app = launch_app(conf)
    try:
        time.sleep(WARMUP_S)
        mark("warmup_end", "e2e harness", run_dir=rd_path)
        gt = []
        t_end = time.monotonic() + dur_s
        i = 0
        while time.monotonic() < t_end - period_s * 0.5:
            time.sleep(period_s)
            if time.monotonic() >= t_end:
                break
            d = durs[i % len(durs)]
            gt.append((*inject_stall(app, d, rd_path), d))
            i += 1
    finally:
        stop_app(app)
        time.sleep(1.0)
        stop_run(rd_path)
    save_gt(rd_path, gt, scenario="borderline", durs=list(durs))
    print(f"BORDERLINE done: {rd_path} n_gt={len(gt)}")
    return rd_path


def scenario_correlation(run_dir, dur_s=360.0, period_s=4.0, burn_ms=350.0,
                         burn_nproc=4, n_cpus=32):
    """4 s SIGSTOP stalls **co-timed** with a pinned CPU-load burst.

    The burst is pinned near the game's current busiest core (``threads.csv``) and
    held for ``burn_ms``, so it is active inside the +/-500 ms correlation window of
    the co-timed stall. Unlike the old 100 ms 4-thread unpinned burn, this raises
    recorded signals (``sys.csv procs_running``, per-core ``cpu.csv`` util), so the
    correlation table has a real signal to rank. ``load_excursion`` verifies the
    excursion appears in cpu.csv/sys.csv.
    """
    rd_path = start_run("e2e-correlate", run_dir=run_dir)
    rd = RunDir(rd_path)
    conf = rd.read_meta()["mangohud"]["config_file"]
    app = launch_app(conf)
    burns = []
    gt = []
    try:
        time.sleep(WARMUP_S)
        mark("warmup_end", "e2e harness", run_dir=rd_path)
        import random
        rng = random.Random(31)
        t_end = time.monotonic() + dur_s
        while time.monotonic() < t_end - period_s * 0.5:
            tick = time.monotonic() + period_s
            bc = busiest_cpu(rd_path, default=0)
            cpus = sorted({bc % n_cpus, (bc + 1) % n_cpus,
                           (bc + 4) % n_cpus, (bc + 8) % n_cpus})
            procs = _spawn_load(cpus, burn_nproc)
            t0 = util.epoch()
            dur = rng.uniform(40, 80)
            gt.append((*inject_stall(app, dur, rd_path), dur))
            while util.epoch() - t0 < burn_ms / 1000.0:
                time.sleep(0.02)
            t1 = util.epoch()
            _kill_load(procs)
            mark("cpu_burn", f"t0={t0:.6f} t1={t1:.6f} cpus={cpus} nproc={burn_nproc}",
                 run_dir=rd_path)
            burns.append({"t0": t0, "t1": t1, "cpus": cpus})
            wait = tick - time.monotonic()
            if wait > 0:
                time.sleep(wait)
    finally:
        stop_app(app)
        time.sleep(1.0)
        stop_run(rd_path)
    exc = load_excursion(rd_path, burns)
    save_gt(rd_path, gt, scenario="correlation",
            burns=[{"t0": a["t0"], "t1": a["t1"], "cpus": a["cpus"]} for a in burns],
            disturbance_check=exc)
    print(f"CORRELATION done: {rd_path} n_gt={len(gt)} n_burn={len(burns)} "
          f"excursion={exc}")
    return rd_path


SCENARIOS = {
    "clean": lambda rd: scenario_clean(rd),
    "periodic": lambda rd: scenario_periodic(rd),
    "sparse": lambda rd: scenario_sparse(rd),
    "mixed": lambda rd: scenario_mixed(rd),
    "short": lambda rd: scenario_short_sparse(rd),
    "borderline": lambda rd: scenario_borderline(rd),
    "correlation": lambda rd: scenario_correlation(rd),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("scenarios", nargs="+", choices=sorted(SCENARIOS),
                    help="which capture scenarios to run")
    ap.add_argument("--runs-root", default=os.path.join(ROOT, "runs"))
    args = ap.parse_args()
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    for sc in args.scenarios:
        rd = os.path.join(args.runs_root, f"validate-{sc}-{stamp}")
        SCENARIOS[sc](rd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
