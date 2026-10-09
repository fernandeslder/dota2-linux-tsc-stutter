"""Tests for the blocked-on analysis (detector/analyze/blocked.py)."""

import json
import os

import pytest

from detector.analyze import blocked as blocked_mod
from detector.analyze import reporting
from detector.analyze.rundir import load_rundir

GAME_PID = 4321


def _write_run(path, n_hitches=20, futex_frac=0.7, with_blocked=True):
    os.makedirs(path, exist_ok=True)
    t0 = 1_700_000_000.0
    fps = 144.0
    dt = 1.0 / fps
    dur = 25.0 + n_hitches * 4.0 + 5.0

    ts, ft, hitches = [], [], []
    t, k = t0, 0
    while t < t0 + dur:
        target = t0 + 25.0 + 4.0 * k
        if k < n_hitches and len(hitches) == k and t >= target - dt / 2:
            ts.append(t)
            ft.append(70.0)
            hitches.append(t)
            k += 1
        else:
            ts.append(t)
            ft.append(1000.0 / fps)
        t += dt

    with open(os.path.join(path, "frametimes.csv"), "w") as fh:
        fh.write("t_epoch,frametime_ms\n")
        for a, b in zip(ts, ft):
            fh.write(f"{a:.6f},{b}\n")
    with open(os.path.join(path, "events.csv"), "w") as fh:
        fh.write("t_epoch,label,detail\n")
        fh.write(f"{t0 + 20:.6f},warmup_end,warmup_s=20.0\n")
        fh.write(f"{t0 + dur:.6f},window_end,collect stop\n")
    with open(os.path.join(path, "meta.json"), "w") as fh:
        json.dump({"run_id": os.path.basename(path), "game_pid": GAME_PID,
                   "collector_end_epoch": t0 + dur}, fh)

    if with_blocked:
        rows = []
        n_futex = int(round(futex_frac * len(hitches)))
        for i, th in enumerate(hitches):
            w = th - 0.07
            if i < n_futex:
                rows.append((w, GAME_PID, "dota2", "S", "futex", "futex_wait_queue_me"))
            else:
                rows.append((w, GAME_PID, "dota2", "S", "poll", "do_sys_poll"))
            rows.append((th + 0.001, GAME_PID, "dota2", "R", "-", "-"))
            rows.append((w, 4322, "render", "S", "ioctl_nv", "nv_fence_wait"))
            rows.append((th + 0.001, 4322, "render", "R", "-", "-"))
            rows.append((w, 4399, "dota2", "D", "read", "btrfs_read"))
            rows.append((th + 0.001, 4399, "dota2", "R", "-", "-"))
            for c in range(3):
                rows.append((w + c * 0.005, 5000 + c, "Async Pipeline", "S",
                             "futex", "futex_wait_queue_me"))
                rows.append((th + 0.001, 5000 + c, "Async Pipeline", "R", "-", "-"))
        rows.sort()
        with open(os.path.join(path, "threads_blocked.csv"), "w") as fh:
            fh.write("t_epoch,tid,comm,state,syscall,wchan\n")
            for r in rows:
                fh.write(f"{r[0]:.6f},{r[1]},{r[2]},{r[3]},{r[4]},{r[5]}\n")
        with open(os.path.join(path, "threads_cpu.csv"), "w") as fh:
            fh.write("t_epoch,tid,comm,cpu_pct\n")
            for i in range(20):
                fh.write(f"{t0 + 30 + i:.6f},{GAME_PID},dota2,{25.0 + i * 0.1:.3f}\n")
                fh.write(f"{t0 + 30 + i:.6f},4322,render,12.0\n")
                fh.write(f"{t0 + 30 + i:.6f},5000,Async Pipeline,3.0\n")
    return hitches


def _analyze(path):
    rd = load_rundir(path)
    verdict = reporting.analyze_run(rd)
    reporting.write_outputs(rd, verdict, os.path.join(path, "out"), plots=False)
    return rd, verdict


def test_blocked_ranking(tmp_path):
    hitches = _write_run(str(tmp_path), n_hitches=20, futex_frac=0.7)
    rd, verdict = _analyze(str(tmp_path))
    blocked = verdict["blocked"]
    assert blocked["available"] is True
    assert blocked["n_hitches_with_data"] == len(hitches)

    by_key = {(r["thread"], r["syscall"], r["wchan"]): r for r in blocked["rows"]}
    main_futex = by_key[("dota2 [main]", "futex", "futex_wait_queue_me")]
    assert abs(main_futex["hitches_frac"] - 0.7) < 0.15
    assert main_futex["coverage_mean"] > 0.9
    assert ("render", "ioctl_nv", "nv_fence_wait") in by_key
    assert ("dota2", "read", "btrfs_read") in by_key
    assert ("Async Pipeline", "futex", "futex_wait_queue_me") in by_key

    # per-thread-name CPU table, ranked
    cpu = blocked["per_thread_cpu"]
    assert cpu[0]["thread"] == "dota2"
    assert blocked["cpu_source"] == "threads_cpu.csv"

    # the special CSVs must not be treated as generic correlation signals
    assert "threads_blocked" not in rd.signals
    assert "threads_cpu" not in rd.signals

    # artifacts + report
    assert os.path.exists(os.path.join(rd.path, "out", "blocked_on.csv"))
    assert verdict["artifacts"]["blocked_on_csv"] == "blocked_on.csv"
    md = open(os.path.join(rd.path, "out", "report.md")).read()
    assert "blocked on during hitches" in md
    assert "ioctl_nv" in md


def test_blocked_unavailable_without_data(tmp_path):
    _write_run(str(tmp_path), n_hitches=6, with_blocked=False)
    rd, verdict = _analyze(str(tmp_path))
    assert verdict["blocked"]["available"] is False
    assert "threads_blocked.csv" in verdict["blocked"]["reason"]
    assert "not available" in open(os.path.join(rd.path, "out", "report.md")).read()


def test_analyze_blocked_empty_file(tmp_path):
    _write_run(str(tmp_path), n_hitches=6, with_blocked=True)
    open(os.path.join(str(tmp_path), "threads_blocked.csv"), "w").close()
    rd = load_rundir(str(tmp_path))
    events = []
    out = blocked_mod.analyze_blocked(rd, events, rd.t_end())
    assert out["available"] is False


def test_interval_coverage_boundaries():
    recs = [(100.0, 1, "x", "S", "futex", "w"),
            (101.0, 1, "x", "R", "-", "-"),
            (102.0, 1, "x", "S", "poll", "p")]
    intervals, comm_of = blocked_mod._build_intervals(recs, end_time=103.0)
    cov = blocked_mod._window_coverage(intervals, 100.5, 101.5)
    assert cov[("S", "futex", "w")][1] == pytest.approx(0.5)
    assert cov[("R", "-", "-")][1] == pytest.approx(0.5)
    cov2 = blocked_mod._window_coverage(intervals, 101.5, 103.5)
    assert cov2[("S", "poll", "p")][1] == pytest.approx(1.0)   # [102, 103] only
    assert cov2[("R", "-", "-")][1] == pytest.approx(0.5)
