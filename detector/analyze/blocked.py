"""What were the game's threads *blocked on* during each hitch?

Consumes the ``offcpu`` sampler's output (``threads_blocked.csv``) and turns it
into a ranked "blocked-on" table plus a per-thread-name CPU table, both reported
per run in ``report.md`` and ``verdict.json``.

``threads_blocked.csv`` is a *transition* log: each row means "this thread entered
``(state, syscall, wchan)`` at ``t_epoch`` and stayed until its next row (or the
run end)".  So instead of counting samples we measure **interval coverage**: for
each hitch we look at the window

    [hitch_start - max(pre_ms, magnitude_ms), hitch_end]

(``magnitude_ms`` extends a single long frame back to when it started) and, per
thread, intersect the window with that thread's intervals.  Buckets covering
``>= MIN_COVERAGE`` of the window count as "present" for that hitch; ``R`` (running
threads) are not "blocked" and are excluded from the ranking (their coverage is
used for the CPU proxy fallback).

Everything degrades gracefully: a run-dir without ``threads_blocked.csv`` (e.g.
the pre-existing ``runs/live-baseline-1``) yields ``{"available": false, ...}``
and the report says so instead of inventing numbers.
"""

from __future__ import annotations

import os
from typing import Optional

import numpy as np

from .config import (BLOCKED_MAX_ROWS, BLOCKED_MAX_WINDOW_S, BLOCKED_MIN_COVERAGE,
                     BLOCKED_PRE_MS)

BLOCKED_CSV = "threads_blocked.csv"
CPU_CSV = "threads_cpu.csv"

#: CSVs that must not be treated as generic correlation signals.
SPECIAL_CSV = {BLOCKED_CSV, CPU_CSV}


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------

def load_blocked(path: str) -> list:
    """Parse ``threads_blocked.csv`` -> list of (t, tid, comm, state, syscall, wchan)."""
    recs = []
    try:
        with open(path, "r", errors="replace") as fh:
            fh.readline()  # header
            for line in fh:
                line = line.rstrip("\n")
                if not line:
                    continue
                parts = line.split(",", 5)
                if len(parts) < 6:
                    continue
                try:
                    t = float(parts[0])
                    tid = int(parts[1])
                except ValueError:
                    continue
                recs.append((t, tid, parts[2], parts[3], parts[4], parts[5]))
    except OSError:
        return []
    return recs


def _build_intervals(recs: list, end_time: float):
    """Group rows per tid into contiguous intervals; return (intervals, comm_of)."""
    by_tid = {}
    for t, tid, comm, state, sc, wchan in recs:
        by_tid.setdefault(tid, []).append((t, comm, state, sc, wchan))
    intervals = {}
    comm_of = {}
    for tid, rows in by_tid.items():
        rows.sort(key=lambda r: r[0])
        t0, t1, buckets = [], [], []
        for i, (t, comm, state, sc, wchan) in enumerate(rows):
            nxt = rows[i + 1][0] if i + 1 < len(rows) else end_time
            if nxt < t:
                nxt = t
            t0.append(t)
            t1.append(nxt)
            buckets.append((state, sc, wchan))
            comm_of[tid] = comm
        intervals[tid] = (np.asarray(t0, dtype=float),
                          np.asarray(t1, dtype=float), buckets)
    return intervals, comm_of


def _window_coverage(intervals: dict, a: float, b: float) -> dict:
    """bucket -> {tid: covered_seconds} for the window [a, b]."""
    out = {}
    for tid, (t0, t1, buckets) in intervals.items():
        i = int(np.searchsorted(t1, a, side="right"))
        j = int(np.searchsorted(t0, b, side="left"))
        for k in range(i, j):
            ov = min(t1[k], b) - max(t0[k], a)
            if ov <= 0:
                continue
            d = out.setdefault(buckets[k], {})
            d[tid] = d.get(tid, 0.0) + float(ov)
    return out


# ---------------------------------------------------------------------------
# analysis
# ---------------------------------------------------------------------------

def analyze_blocked(rundir, events, run_end: Optional[float],
                    pre_ms: float = BLOCKED_PRE_MS,
                    min_coverage: float = BLOCKED_MIN_COVERAGE,
                    max_rows: int = BLOCKED_MAX_ROWS) -> dict:
    path = os.path.join(rundir.path, BLOCKED_CSV)
    if not os.path.exists(path):
        return {"available": False,
                "reason": "threads_blocked.csv not present "
                          "(this run predates the offcpu sampler)"}
    recs = load_blocked(path)
    if not recs:
        return {"available": False, "reason": "threads_blocked.csv empty"}

    end_time = max(float(run_end or 0.0), max(r[0] for r in recs))
    intervals, comm_of = _build_intervals(recs, end_time)
    main_tid = None
    try:
        gp = int(rundir.meta.get("game_pid") or 0)
        main_tid = gp if gp in intervals else None
    except (TypeError, ValueError):
        main_tid = None

    events = [e for e in events if getattr(e, "severity", "high") == "high"]

    agg = {}          # (label, state, syscall, wchan) -> accumulation
    main_agg = {}     # (state, syscall, wchan) -> seconds (main thread only)
    n_used = 0
    win_desc = None
    for hi, e in enumerate(events):
        mag_s = (getattr(e, "magnitude_ms", 0.0) or 0.0) / 1000.0
        pre_s = max(pre_ms / 1000.0, mag_s)
        b = max(float(e.t_end), float(e.t))
        a = float(e.t) - pre_s
        win_len = b - a
        if win_len <= 0:
            continue
        if win_len > BLOCKED_MAX_WINDOW_S:       # clamp pathological spans
            a = b - BLOCKED_MAX_WINDOW_S
            win_len = BLOCKED_MAX_WINDOW_S
        if win_desc is None:
            win_desc = ("[hitch_start - max(pre_ms, magnitude_ms), hitch_end]")
        n_used += 1

        cov = _window_coverage(intervals, a, b)
        per_group = {}
        for bucket, tids in cov.items():
            state, sc, wchan = bucket
            if state == "R":
                continue
            for tid, secs in tids.items():
                if secs <= 0:
                    continue
                comm = comm_of.get(tid, "?")
                label = comm + (" [main]" if main_tid and tid == main_tid else "")
                g = per_group.setdefault((label, state, sc, wchan), [0.0, 0])
                if secs > g[0]:
                    g[0] = secs
                g[1] += 1
            if main_tid is not None and main_tid in tids:
                main_agg[bucket] = main_agg.get(bucket, 0.0) + float(tids[main_tid])

        for key, (max_tid_secs, n_tids) in per_group.items():
            frac = max_tid_secs / win_len
            if frac < min_coverage:
                continue
            rec = agg.setdefault(key, {"hitches": set(), "cov": [], "threads": [],
                                       "total_s": 0.0})
            rec["hitches"].add(hi)
            rec["cov"].append(frac)
            rec["threads"].append(n_tids)
            rec["total_s"] += max_tid_secs

    denom = max(1, n_used)
    rows = []
    for (label, state, sc, wchan), rec in agg.items():
        cov = np.asarray(rec["cov"], dtype=float)
        rows.append({
            "thread": label,
            "state": state,
            "syscall": sc,
            "wchan": wchan,
            "hitches": len(rec["hitches"]),
            "hitches_frac": len(rec["hitches"]) / denom,
            "coverage_mean": float(cov.mean()) if cov.size else 0.0,
            "coverage_p50": float(np.median(cov)) if cov.size else 0.0,
            "total_s": float(rec["total_s"]),
            "threads_mean": float(np.mean(rec["threads"])) if rec["threads"] else 0.0,
        })
    rows.sort(key=lambda r: (r["hitches_frac"], r["coverage_mean"]), reverse=True)

    main_total = sum(main_agg.values())
    main_thread = []
    if main_total > 0:
        for (state, sc, wchan), secs in sorted(main_agg.items(),
                                               key=lambda kv: kv[1], reverse=True)[:8]:
            main_thread.append({"state": state, "syscall": sc, "wchan": wchan,
                                "seconds": secs, "frac": secs / main_total})

    per_cpu, cpu_source = _cpu_table(rundir, intervals, comm_of, end_time)

    return {
        "available": True,
        "window_rule": win_desc or "[hitch_start - pre_ms, hitch_end]",
        "pre_ms": pre_ms,
        "min_coverage": min_coverage,
        "n_hitches": len(events),
        "n_hitches_with_data": n_used,
        "n_threads_seen": len(comm_of),
        "game_pid": main_tid,
        "rows": rows[:max_rows],
        "n_rows_total": len(rows),
        "main_thread": main_thread,
        "per_thread_cpu": per_cpu,
        "cpu_source": cpu_source,
        "notes": _notes(recs, intervals, events),
    }


def _notes(recs, intervals, events) -> list:
    notes = []
    if not events:
        notes.append("no hitches in the analysis window")
    if not intervals:
        notes.append("no thread intervals parsed")
    return notes


def _cpu_table(rundir, intervals, comm_of, end_time):
    """Per-thread-name CPU: real cpu_pct from threads_cpu.csv, else R-fraction."""
    path = os.path.join(rundir.path, CPU_CSV)
    if os.path.exists(path):
        sums, counts, tids = {}, {}, {}
        try:
            with open(path, "r", errors="replace") as fh:
                fh.readline()
                for line in fh:
                    parts = line.rstrip("\n").split(",", 3)
                    if len(parts) < 4:
                        continue
                    try:
                        float(parts[0])
                        tid = int(parts[1])
                        pct = float(parts[3])
                    except ValueError:
                        continue
                    comm = parts[2]
                    sums[comm] = sums.get(comm, 0.0) + pct
                    counts[comm] = counts.get(comm, 0) + 1
                    tids.setdefault(comm, set()).add(tid)
        except OSError:
            sums = {}
        if sums:
            table = [{"thread": c, "cpu_pct_mean": sums[c] / counts[c],
                      "samples": counts[c], "n_threads": len(tids.get(c, ()))}
                     for c in sums]
            table.sort(key=lambda r: r["cpu_pct_mean"], reverse=True)
            return table, CPU_CSV

    # fallback: fraction of wall time each thread-name spent in state R
    run_s, span = {}, {}
    for tid, (t0, t1, buckets) in intervals.items():
        comm = comm_of.get(tid, "?")
        first = t0[0] if t0.size else end_time
        span[comm] = max(span.get(comm, 0.0), end_time - first)
        for k, (state, _sc, _w) in enumerate(buckets):
            if state == "R":
                run_s[comm] = run_s.get(comm, 0.0) + float(t1[k] - t0[k])
    table = []
    for comm, s in run_s.items():
        if span.get(comm, 0.0) > 0:
            table.append({"thread": comm, "cpu_pct_mean": s / span[comm] * 100.0,
                          "samples": None, "n_threads": None})
    table.sort(key=lambda r: r["cpu_pct_mean"], reverse=True)
    return table, "running-fraction"


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------

BLOCKED_CSV_HEADER = ["thread", "state", "syscall", "wchan", "hitches",
                      "hitches_frac", "coverage_mean", "coverage_p50",
                      "total_s", "threads_mean"]


def write_blocked_csv(path: str, blocked: dict) -> None:
    import csv as _csv
    with open(path, "w", newline="") as fh:
        w = _csv.writer(fh)
        w.writerow(BLOCKED_CSV_HEADER)
        for r in blocked.get("rows", []):
            w.writerow([r["thread"], r["state"], r["syscall"], r["wchan"],
                        r["hitches"], f"{r['hitches_frac']:.4f}",
                        f"{r['coverage_mean']:.4f}", f"{r['coverage_p50']:.4f}",
                        f"{r['total_s']:.4f}", f"{r['threads_mean']:.2f}"])


def render_blocked_md(blocked: dict) -> str:
    L = ["## What the threads were blocked on during hitches", ""]
    if not blocked.get("available"):
        L.append(f"_not available: {blocked.get('reason', 'no data')}_")
        L.append("")
        return "\n".join(L) + "\n"
    L.append(f"- window per hitch: {blocked['window_rule']} "
             f"(pre_ms={blocked['pre_ms']:.0f}); threads seen: {blocked['n_threads_seen']}")
    L.append(f"- hitches analysed: {blocked['n_hitches_with_data']}/{blocked['n_hitches']} "
             f"(a bucket counts when it covers >= {100*blocked['min_coverage']:.0f}% of the window)")
    if blocked.get("main_thread"):
        parts = [f"{m['state']}/{m['syscall']} {m['wchan']} ({100*m['frac']:.0f}%)"
                 for m in blocked["main_thread"][:4]]
        L.append(f"- main thread off-CPU buckets: " + "; ".join(parts))
    L.append("")
    rows = blocked.get("rows", [])
    if rows:
        L.append("| thread | state | syscall | wchan | hitches | % hitches | coverage | threads |")
        L.append("|---|---|---|---|---|---|---|---|")
        for r in rows:
            L.append(f"| {r['thread']} | {r['state']} | {r['syscall']} | {r['wchan']} | "
                     f"{r['hitches']} | {100*r['hitches_frac']:.1f}% | "
                     f"{100*r['coverage_mean']:.0f}% | {r['threads_mean']:.1f} |")
    else:
        L.append("_no thread/bucket passed the coverage threshold around hitches_")
    cpu = blocked.get("per_thread_cpu", [])
    if cpu:
        L.append("")
        L.append(f"### Per-thread-name CPU ({blocked.get('cpu_source')})")
        L.append("")
        L.append("| thread | cpu% (mean) | samples | threads |")
        L.append("|---|---|---|---|")
        for r in cpu[:15]:
            L.append(f"| {r['thread']} | {r['cpu_pct_mean']:.2f} | "
                     f"{r.get('samples') if r.get('samples') is not None else '-'} | "
                     f"{r.get('n_threads') if r.get('n_threads') is not None else '-'} |")
    for n in blocked.get("notes", []):
        L.append(f"- note: {n}")
    L.append("")
    return "\n".join(L) + "\n"
