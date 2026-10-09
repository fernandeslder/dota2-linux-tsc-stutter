#!/usr/bin/env python3
"""Attribute Dota 2 frametime hitches from a system-wide scheduler trace.

Inputs
------
* ``perf``      : a ``perf record -e sched:sched_switch -e sched:sched_waking -a``
                  capture.  Either the raw ``perf.data`` (we shell out to
                  ``perf script``) or an already-dumped ``perf script`` text.
* ``mangohud``  : the MangoHud ``*.csv`` raw log (has ``frametime``/``elapsed``).
* ``offset``    : epoch calibration (s) added to ``btime + elapsed_ns/1e9``.
                  ``0.0`` reproduces the collector's ``frametimes.csv``; the
                  measured residual is ~+0.0136 s.
* ``--mono-offset`` : epoch = perf CLOCK_MONOTONIC + this.  Frames are mapped
                  into the perf clock with it.

Pipeline
--------
1. Map every MangoHud frame to epoch, then into the perf monotonic clock.
2. Select "hitches" (frametime > ``--min-frametime`` ms) inside the perf window.
3. Per hitch rebuild the per-CPU timeline (who ran, idle fraction) and, for the
   Dota **main** thread (tid == tgid) and every **render** thread
   (``VKRenderThread``), find the longest blocked (sleeping) interval that
   overlaps the hitch.  At the end of that interval the thread resumes: report
   the ``sched_waking`` that woke it (the waker) and chase the waker back up to
   ``--chain`` levels.
4. Compare against ``--control`` random same-length control windows to rank
   which tasks / wakers / CPUs are *enriched* during hitches.
5. Report periodic structure of the hitches and of boundary events.

Example
-------
    tools/sched_stall_analysis.py /tmp/stutter-live/perf-S1.data \\
        runs/live-S1-sched/raw/mangohud/dota2_2026-10-08_22-26-04.csv 0.0 \\
        --game-pid 3838464 --mono-offset 1791395966.6282375 --json out.json

The trace is streamed twice (one cheap discovery pass, one index pass); the
report goes to stdout and, with ``--json``, to a file for downstream tooling.
"""

from __future__ import annotations

import argparse
import bisect
import json
import os
import re
import statistics
import subprocess
import sys
import random
from collections import Counter, defaultdict

# ---------------------------------------------------------------------------
# perf script line grammar
# ---------------------------------------------------------------------------

RE_PREFIX = re.compile(
    r"^\s*(?P<comm>.*?)\s+(?P<pid>\d+)/(?P<tid>\d+)\s+\[(?P<cpu>\d+)\]\s+"
    r"(?P<time>\d+\.\d+):\s+(?P<event>\S+?):\s?(?P<payload>prev_comm=.*|comm=.*)$"
)
RE_SWITCH = re.compile(
    r"prev_comm=(?P<pc>\S+)\s+prev_pid=(?P<pp>\d+)\s+prev_prio=(?P<pprio>\d+)\s+"
    r"prev_state=(?P<pstate>\S+)\s+==>\s+next_comm=(?P<nc>\S+)\s+"
    r"next_pid=(?P<np>\d+)\s+next_prio=(?P<nprio>\d+)"
)
RE_WAKING = re.compile(
    r"comm=(?P<wc>\S+)\s+pid=(?P<wp>\d+)\s+prio=(?P<wprio>-?\d+)\s+"
    r"target_cpu=(?P<tcpu>\d+)"
)


def _looks_like_script(path: str) -> bool:
    try:
        with open(path, "r", errors="replace") as fh:
            for _ in range(5):
                line = fh.readline()
                if not line:
                    break
                if RE_PREFIX.match(line) and ("sched_switch" in line or "sched_waking" in line):
                    return True
    except OSError:
        return False
    return False


def iter_script_lines(perf_path: str):
    """Yield perf-script text lines from a raw perf.data or a pre-dumped file."""
    if _looks_like_script(perf_path):
        with open(perf_path, "r", errors="replace") as fh:
            yield from fh
        return
    cmd = ["perf", "script", "-f", "-i", perf_path,
           "-F", "comm,pid,tid,cpu,time,event,trace"]
    if os.geteuid() != 0:
        cmd = ["sudo", "-n"] + cmd
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            text=True, errors="replace", bufsize=1 << 20)
    assert proc.stdout is not None
    for line in proc.stdout:
        yield line
    proc.wait()


# ---------------------------------------------------------------------------
# trace model
# ---------------------------------------------------------------------------

def _is_blocked(state: str) -> bool:
    return not state.startswith("R")


class Trace:
    def __init__(self):
        self.cpu_times = defaultdict(list)
        self.cpu_prev_pid = defaultdict(list)
        self.cpu_next_pid = defaultdict(list)
        self.cpu_next_comm = defaultdict(list)
        self.cpu_prev_state = defaultdict(list)
        # sched_waking index by wakee pid (all pids, for waker chains)
        self.wk_times = defaultdict(list)
        self.wk_waker_cpu = defaultdict(list)
        self.wk_waker_comm = defaultdict(list)
        self.wk_waker_pid = defaultdict(list)
        # sched_switch index restricted to the traced task set (dota threads)
        self.sw_out_times = defaultdict(list)
        self.sw_out_cpu = defaultdict(list)
        self.sw_out_state = defaultdict(list)
        self.sw_out_next = defaultdict(list)
        self.sw_in_times = defaultdict(list)
        self.sw_in_cpu = defaultdict(list)
        self.sw_in_prev_comm = defaultdict(list)
        self.sw_in_prev_pid = defaultdict(list)
        # global bookkeeping
        self.t_first = None
        self.t_last = None
        self.n_switch = 0
        self.n_waking = 0
        self.comm_switchin_times = defaultdict(list)   # all comms (boundary)
        self.blocked = []              # sorted [(out_t, in_t, tid)] blocked dota intervals
        self.blocked_starts = []
        self.blocked_by_tid = defaultdict(list)
        self.t_set = set()
        self._intern = sys.intern

    def add_switch(self, t, cpu, pc, pp, pstate, nc, np):
        self.cpu_times[cpu].append(t)
        self.cpu_prev_pid[cpu].append(pp)
        self.cpu_next_pid[cpu].append(np)
        self.cpu_next_comm[cpu].append(self._intern(nc))
        self.cpu_prev_state[cpu].append(pstate)
        self.n_switch += 1
        if pp in self.t_set:
            self.sw_out_times[pp].append(t)
            self.sw_out_cpu[pp].append(cpu)
            self.sw_out_state[pp].append(pstate)
            self.sw_out_next[pp].append(self._intern(nc))
        if np in self.t_set:
            self.sw_in_times[np].append(t)
            self.sw_in_cpu[np].append(cpu)
            self.sw_in_prev_comm[np].append(self._intern(pc))
            self.sw_in_prev_pid[np].append(pp)
        if self.t_first is None or t < self.t_first:
            self.t_first = t
        if self.t_last is None or t > self.t_last:
            self.t_last = t

    def add_waking(self, t, waker_cpu, waker_comm, waker_pid, wakee_pid):
        self.n_waking += 1
        self.wk_times[wakee_pid].append(t)
        self.wk_waker_cpu[wakee_pid].append(waker_cpu)
        self.wk_waker_comm[wakee_pid].append(self._intern(waker_comm))
        self.wk_waker_pid[wakee_pid].append(waker_pid)
        if self.t_first is None or t < self.t_first:
            self.t_first = t
        if self.t_last is None or t > self.t_last:
            self.t_last = t

    def finalise(self):
        for cpu, comms in self.cpu_next_comm.items():
            ts = self.cpu_times[cpu]
            for k, c in enumerate(comms):
                self.comm_switchin_times[c].append(ts[k])
        for c in self.comm_switchin_times:
            self.comm_switchin_times[c].sort()
        bi = []
        for tid, outs in self.sw_out_times.items():
            states = self.sw_out_state[tid]
            ins = self.sw_in_times.get(tid, [])
            for j, o in enumerate(outs):
                if not _is_blocked(states[j]):
                    continue
                k = bisect.bisect_right(ins, o)
                if k < len(ins):
                    bi.append((o, ins[k], tid))
        bi.sort()
        self.blocked = bi
        self.blocked_starts = [x[0] for x in bi]
        for o, i, tid in bi:
            self.blocked_by_tid[tid].append((o, i))

    # -- occupancy ---------------------------------------------------------
    def occupancy(self, cpu, a, b):
        """(comm_seconds, idle_seconds) for [a, b) on *cpu*."""
        times = self.cpu_times[cpu]
        if not times:
            return {}, 0.0
        i = bisect.bisect_right(times, a) - 1
        if i < 0:
            i = 0
            cur_start = times[0]
        else:
            cur_start = a
        ncomm = self.cpu_next_comm[cpu]
        npid = self.cpu_next_pid[cpu]
        acc = defaultdict(float)
        idle = 0.0
        cur_name, cur_pid = ncomm[i], npid[i]
        j = i + 1
        n = len(times)
        while j < n and times[j] < b:
            dt = times[j] - cur_start
            if dt > 0:
                acc[cur_name] += dt
                if cur_pid == 0:
                    idle += dt
            cur_name, cur_pid = ncomm[j], npid[j]
            cur_start = times[j]
            j += 1
        dt = b - cur_start
        if dt > 0:
            acc[cur_name] += dt
            if cur_pid == 0:
                idle += dt
        return dict(acc), idle

    def last_waking(self, pid, lo, hi):
        ts = self.wk_times.get(pid)
        if not ts:
            return None
        i = bisect.bisect_right(ts, hi) - 1
        if i < 0 or ts[i] < lo:
            return None
        return ts[i], self.wk_waker_cpu[pid][i], self.wk_waker_comm[pid][i], self.wk_waker_pid[pid][i]

    def blocked_intervals(self, tid, a, b):
        """Blocked intervals of *tid* overlapping [a, b]."""
        out = []
        for o, i in self.blocked_by_tid.get(tid, ()):  # small per-thread list
            if i < a:
                continue
            if o > b:
                break
            out.append((o, i))
        return out

    def blocked_frac(self, tid, a, b):
        dur = b - a
        if dur <= 0:
            return 0.0
        tot = 0.0
        for o, i in self.blocked_intervals(tid, a, b):
            tot += min(b, i) - max(a, o)
        return tot / dur

    def chain(self, tid, t_lo, t_hi, levels=3):
        """Follow wake dependencies: who woke tid, who woke that, ..."""
        out = []
        cur = tid
        lo, hi = t_lo, t_hi
        for _ in range(levels):
            wk = self.last_waking(cur, lo, hi)
            if not wk:
                break
            t, wcpu, wcomm, wpid = wk
            out.append({"wakee": cur, "t": t, "waker": wcomm, "waker_pid": wpid,
                        "waker_cpu": wcpu})
            if wpid == 0 or wcomm.startswith("swapper"):
                break
            ts = self.cpu_times.get(wcpu)
            tin = None
            if ts:
                k = bisect.bisect_right(ts, t) - 1
                while k >= 0 and ts[k] >= t - 0.05:
                    if self.cpu_next_pid[wcpu][k] == wpid:
                        tin = ts[k]
                        break
                    k -= 1
            if tin is None:
                break
            cur, hi, lo = wpid, t, max(lo, tin - 0.20)
        return out


def discover_threads(perf_path, game_pid):
    """First pass: find the (game_pid, tid) pairs and their thread comms."""
    tids = defaultdict(set)
    comm = {}
    dota2_count = Counter()
    for line in iter_script_lines(perf_path):
        m = RE_PREFIX.match(line)
        if not m:
            continue
        pid = int(m.group("pid"))
        tid = int(m.group("tid"))
        tids[pid].add(tid)
        comm[tid] = m.group("comm")
        s = RE_SWITCH.search(m.group("payload"))
        if s and s.group("nc") == "dota2":
            dota2_count[pid] += 1
    if game_pid is None:
        game_pid = dota2_count.most_common(1)[0][0] if dota2_count else None
    if game_pid is None:
        return None, {}
    return game_pid, {tid: comm[tid] for tid in tids.get(game_pid, ())}


def parse_trace(perf_path, task_tids):
    tr = Trace()
    tr.t_set = set(task_tids)
    for line in iter_script_lines(perf_path):
        m = RE_PREFIX.match(line)
        if not m:
            continue
        payload = m.group("payload")
        t = float(m.group("time"))
        cpu = int(m.group("cpu"))
        if payload.startswith("prev_comm="):
            s = RE_SWITCH.search(payload)
            if s:
                tr.add_switch(t, cpu, s.group("pc"), int(s.group("pp")), s.group("pstate"),
                              s.group("nc"), int(s.group("np")))
        elif payload.startswith("comm="):
            w = RE_WAKING.search(payload)
            if w:
                tr.add_waking(t, cpu, m.group("comm"), int(m.group("tid")), int(w.group("wp")))
    tr.finalise()
    return tr


# ---------------------------------------------------------------------------
# MangoHud
# ---------------------------------------------------------------------------

def birthtime_ns(path):
    import ctypes as C
    import ctypes.util

    class ts(C.Structure):
        _fields_ = [("tv_sec", C.c_int64), ("tv_nsec", C.c_uint32), ("__r", C.c_int32)]

    class stxbuf(C.Structure):
        _fields_ = [
            ("stx_mask", C.c_uint32), ("stx_blksize", C.c_uint32),
            ("stx_attributes", C.c_uint64), ("stx_nlink", C.c_uint32),
            ("stx_uid", C.c_uint32), ("stx_gid", C.c_uint32),
            ("stx_mode", C.c_uint16), ("__spare0", C.c_uint16 * 1),
            ("stx_ino", C.c_uint64), ("stx_size", C.c_uint64), ("stx_blocks", C.c_uint64),
            ("stx_attributes_mask", C.c_uint64), ("stx_atime", ts), ("stx_btime", ts),
            ("stx_ctime", ts), ("stx_mtime", ts),
            ("stx_rdev_major", C.c_uint32), ("stx_rdev_minor", C.c_uint32),
            ("stx_dev_major", C.c_uint32), ("stx_dev_minor", C.c_uint32),
            ("__spare2", C.c_uint64 * 14),
        ]
    try:
        libc = C.CDLL(C.util.find_library("c") or "libc.so.6", use_errno=True)
        fn = libc.statx
    except Exception:
        return None
    fn.argtypes = [C.c_int, C.c_char_p, C.c_int, C.c_uint, C.POINTER(stxbuf)]
    fn.restype = C.c_int
    buf = stxbuf()
    if fn(-100, os.fsencode(path), 0x100, 0xFFF, C.byref(buf)) != 0:
        return None
    if not (buf.stx_mask & 0x800):
        return None
    return buf.stx_btime.tv_sec * 1_000_000_000 + buf.stx_btime.tv_nsec


def read_mangohud(path, birth_ns, offset_s):
    """Return (frames, t0); frames = [(t_epoch, frametime_ms)]."""
    t0 = (birth_ns / 1e9 if birth_ns is not None else os.path.getmtime(path)) + offset_s
    frames = []
    with open(path, "r", errors="replace") as fh:
        cols = None
        for line in fh:
            if line.startswith("fps,") and "frametime" in line:
                cols = [c.strip() for c in line.rstrip("\n").split(",")]
                continue
            if cols is None or not line.strip():
                continue
            p = line.rstrip("\n").split(",")
            try:
                ft = float(p[cols.index("frametime")])
                el = float(p[cols.index("elapsed")])
            except (ValueError, IndexError):
                continue
            if 0.0 < ft <= 10000.0:
                frames.append((t0 + el / 1e9, ft))
    return frames, t0


# ---------------------------------------------------------------------------
# analysis
# ---------------------------------------------------------------------------

def _is_idle(comm):
    return comm.startswith("swapper")


def window_stats(tr, lo, hi):
    """Per-cpu occupancy over [lo, hi), plus idle/silent fractions."""
    task_time = defaultdict(float)
    per_cpu_idle = {}
    per_cpu_top = {}
    total_idle = 0.0
    ncpu = 0
    dur = hi - lo
    for cpu in tr.cpu_times:
        acc, idle = tr.occupancy(cpu, lo, hi)
        if not acc and idle <= 0:
            continue
        ncpu += 1
        per_cpu_idle[cpu] = idle / dur if dur > 0 else 0.0
        total_idle += idle
        act = {c: v for c, v in acc.items() if not _is_idle(c)}
        if act:
            per_cpu_top[cpu] = max(act, key=act.get)
        for c, dt in acc.items():
            task_time[c] += dt
    cpu0_acc, cpu0_idle = tr.occupancy(0, lo, hi) if 0 in tr.cpu_times else ({}, 0.0)
    return {
        "dur": dur, "ncpu": ncpu, "task_time": dict(task_time),
        "per_cpu_idle": per_cpu_idle, "per_cpu_top": per_cpu_top,
        "idle_all": total_idle / (dur * ncpu) if dur > 0 and ncpu else 0.0,
        "cpu0_task_time": {c: v for c, v in cpu0_acc.items() if not _is_idle(c)},
        "cpu0_idle_frac": cpu0_idle / dur if dur > 0 else 0.0,
    }


def top_tasks(task_time, cap, k=8):
    ranked = sorted(((c, v) for c, v in task_time.items() if not _is_idle(c)),
                    key=lambda kv: -kv[1])[:k]
    return [{"comm": c, "sec": v, "frac": v / cap if cap else 0} for c, v in ranked]


def hitch_analysis(tr, frames, perf_lo, perf_hi, min_ft, chain_levels, main_tid):
    hitches = []
    for t, ft in frames:
        if ft <= min_ft or t < perf_lo or t > perf_hi:
            continue
        win_lo = max(perf_lo, t - ft / 1000.0)
        win_hi = min(perf_hi, t)
        st = window_stats(tr, win_lo, win_hi)
        cap = st["dur"] * st["ncpu"]
        rec = {"t_end": t, "frametime_ms": ft, "win_lo": win_lo, "win_hi": win_hi, **st}
        rec["top_tasks"] = top_tasks(st["task_time"], cap)
        busy = {c: (1.0 - f) for c, f in st["per_cpu_idle"].items()}
        rec["busiest_cpu"] = max(busy, key=busy.get) if busy else -1
        rec["cpu0_idle"] = st["per_cpu_idle"].get(0)
        rec["cpu0_top"] = st["per_cpu_top"].get(0)
        # dota threads whose *blocking originated* inside the hitch window
        threads = []
        for tid in tr.sw_out_times:
            best = None
            for o, i in tr.blocked_intervals(tid, win_lo, win_hi):
                if o < win_lo - 0.10:          # began before the hitch: not the culprit
                    continue
                if i - o < 0.020:
                    continue
                if best is None or (i - o) > (best[1] - best[0]):
                    best = (o, i)
            if best:
                threads.append({"tid": tid, "block_ms": (best[1] - best[0]) * 1000.0,
                                "out_t": best[0], "in_t": best[1]})
        threads.sort(key=lambda x: -x["block_ms"])
        for e in threads:
            wk = tr.last_waking(e["tid"], e["out_t"], e["in_t"])
            j = bisect.bisect_right(tr.sw_in_times[e["tid"]], e["in_t"]) - 1
            e["out_state"] = tr.sw_out_state[e["tid"]][
                bisect.bisect_right(tr.sw_out_times[e["tid"]], e["out_t"]) - 1]
            e["resume_cpu"] = tr.sw_in_cpu[e["tid"]][j] if j >= 0 else None
            e["ran_before"] = tr.sw_in_prev_comm[e["tid"]][j] if j >= 0 else None
            e["waker"] = ({"t": wk[0], "cpu": wk[1], "comm": wk[2], "pid": wk[3]} if wk else None)
            e["waker_lag_ms"] = (e["in_t"] - wk[0]) * 1000.0 if wk else None
            if wk:
                e["waker_chain"] = tr.chain(wk[3], e["out_t"], wk[0], chain_levels)
        rec["threads"] = threads
        # dedicated main-thread record (relaxed window so a block starting at the
        # frame boundary is not missed)
        rec["main"] = None
        if main_tid is not None:
            best = None
            best_key = None
            for o, i in tr.blocked_intervals(main_tid, win_lo - 0.6, win_hi):
                if i - o < 0.020:
                    continue
                overlap = min(i, win_hi) - max(o, win_lo)
                started_in = o >= win_lo - 0.05
                key = (1 if started_in else 0, overlap)
                if best_key is None or key > best_key:
                    best_key, best = key, (o, i)
            if best:
                o, i = best
                wk = tr.last_waking(main_tid, o, i)
                j = bisect.bisect_right(tr.sw_in_times[main_tid], i) - 1
                me = {"tid": main_tid, "block_ms": (i - o) * 1000.0,
                      "overlap_ms": (min(i, win_hi) - max(o, win_lo)) * 1000.0,
                      "started_in_window": o >= win_lo - 0.05, "out_t": o, "in_t": i,
                      "out_state": tr.sw_out_state[main_tid][
                          bisect.bisect_right(tr.sw_out_times[main_tid], o) - 1],
                      "resume_cpu": tr.sw_in_cpu[main_tid][j] if j >= 0 else None,
                      "ran_before": tr.sw_in_prev_comm[main_tid][j] if j >= 0 else None,
                      "waker": ({"t": wk[0], "cpu": wk[1], "comm": wk[2], "pid": wk[3]} if wk else None),
                      "waker_lag_ms": (i - wk[0]) * 1000.0 if wk else None}
                if wk:
                    me["waker_chain"] = tr.chain(wk[3], o, wk[0], chain_levels)
                rec["main"] = me
        # other threads blocked for most of the hitch (concurrency)
        rec["concurrent"] = [e for e in threads
                             if e["tid"] != main_tid and e["block_ms"] >= 0.5 * ft]
        # also the single longest block anywhere (context; may be a background poller)
        rec["longest_any"] = max(
            ({"tid": tid, "block_ms": (i - o) * 1000.0}
             for tid in tr.sw_out_times for o, i in tr.blocked_intervals(tid, win_lo, win_hi)),
            key=lambda x: x["block_ms"], default=None)
        hitches.append(rec)
    return hitches


def control_windows(tr, hitches, perf_lo, perf_hi, n, rng, main_tid, render_tids):
    lengths = [h["dur"] for h in hitches]
    out = []
    if not lengths:
        return out
    span = perf_hi - perf_lo
    for _ in range(n):
        length = rng.choice(lengths)
        if span <= length:
            break
        lo = rng.uniform(perf_lo, perf_hi - length)
        hi = lo + length
        st = window_stats(tr, lo, hi)
        st["main_block_frac"] = tr.blocked_frac(main_tid, lo, hi) if main_tid else 0.0
        st["render_block_frac"] = (statistics.fmean(tr.blocked_frac(t, lo, hi) for t in render_tids)
                                   if render_tids else 0.0)
        out.append({"lo": lo, "hi": hi, **st})
    return out


def enrichment(hitches, controls):
    """Rank comms by mean wall-normalised share difference (hitch - control)."""

    def mean_shares(recs):
        acc = defaultdict(float)
        n = 0
        for r in recs:
            cap = r["dur"] * r["ncpu"]
            if cap <= 0:
                continue
            n += 1
            for c, dt in r["task_time"].items():
                acc[c] += dt / cap
        return ({c: v / n for c, v in acc.items()} if n else {}), n

    hs, hn = mean_shares(hitches)
    cs, cn = mean_shares(controls)
    rows = []
    for c in set(hs) | set(cs):
        h, k = hs.get(c, 0.0), cs.get(c, 0.0)
        rows.append({"comm": c, "hitch": h, "control": k, "delta": h - k,
                     "ratio": (h / k if k > 1e-12 else float("inf"))})
    rows.sort(key=lambda r: -r["delta"])
    return rows


def periodicity(times):
    if len(times) < 3:
        return {"n": len(times)}
    ts = sorted(times)
    iv = [b - a for a, b in zip(ts, ts[1:])]
    lo, hi = ts[0], ts[-1]
    binw = 0.050
    nb = max(1, int((hi - lo) / binw) + 1)
    series = [0.0] * nb
    for t in ts:
        series[min(nb - 1, int((t - lo) / binw))] = 1.0
    mean = sum(series) / nb
    var = sum((x - mean) ** 2 for x in series) / nb
    ac = []
    for lag in range(1, min(nb, 400)):
        num = sum((series[i] - mean) * (series[i + lag] - mean) for i in range(nb - lag))
        ac.append((lag * binw, num / (nb - lag) / var if var > 0 else 0.0))
    ac.sort(key=lambda x: -x[1])
    return {"n": len(ts), "interval_median_s": statistics.median(iv),
            "interval_mean_s": statistics.fmean(iv), "interval_min_s": min(iv),
            "interval_max_s": max(iv),
            "ac_peak_period_s": ac[0][0] if ac else None,
            "ac_peak_value": ac[0][1] if ac else None}


def boundary_enrichment(tr, events, perf_lo, perf_hi, window=0.010, top=25):
    span = perf_hi - perf_lo
    ev = sorted(events)
    rows = []
    for c, ts in tr.comm_switchin_times.items():
        rate = len(ts) / span if span > 0 else 0.0
        hits = 0
        j = 0
        ns = len(ev)
        for t in ts:
            while j < ns and ev[j] < t - window:
                j += 1
            if j < ns and ev[j] <= t + window:
                hits += 1
        expected = rate * (2 * window) * ns
        if expected > 0 and hits > 0:
            rows.append({"comm": c, "hits": hits, "expected": expected,
                         "lift": hits / expected, "events": len(ts)})
    rows.sort(key=lambda r: -(r["hits"] - r["expected"]))
    return rows[:top]


# ---------------------------------------------------------------------------
# reporting
# ---------------------------------------------------------------------------

def _chain_str(entry):
    ch = entry.get("waker_chain") or []
    return " -> ".join(f"{c['waker']}({c['waker_cpu']})" for c in ch[:3])


def build_report(args, tr, frames, hitches, controls, enrich, comm_of, main_tid, render_tids,
                 peri, peri_resume, boundary, boundary_resume):
    L = []
    dur = tr.t_last - tr.t_first
    L.append("## Window & mapping")
    L.append(f"* perf window : mono {tr.t_first:.4f}..{tr.t_last:.4f} = "
             f"epoch {args.mono_offset + tr.t_first:.3f}..{args.mono_offset + tr.t_last:.3f} ({dur:.1f}s)")
    L.append(f"* frames mapped: {len(frames)}  (mangohud offset {args.offset:+.4f}s)")
    L.append(f"* hitches >{args.min_frametime:g} ms: {len(hitches)} ({len(hitches)/dur*60:.1f}/min)")
    L.append(f"* control windows: {len(controls)}")
    L.append("")
    L.append(f"## Dota thread map (pid {args.game_pid}, main tid={main_tid})")
    for tid, c in sorted(comm_of.items()):
        tag = " MAIN" if tid == main_tid else (" render" if c == "VKRenderThread" else "")
        L.append(f"* {c}: tid={tid}{tag}")
    L.append("")
    L.append("## Main thread: stall window, switch-out, and the waker that ends it")
    L.append("```")
    L.append(f"{'hitch_t':>12s} {'ft_ms':>7s} {'blk_ms':>8s} {'ovl_ms':>8s} {'in':>3s} {'cpu0idle%':>9s} {'out_st':>6s} "
             f"{'waker':>16s} {'wk_cpu':>6s} {'lag':>6s} {'chain':>30s}")
    for h in hitches:
        e = h.get("main")
        if not e:
            L.append(f"{h['t_end']+args.mono_offset:12.3f} {h['frametime_ms']:7.1f} "
                     f"{'(main not blocked)':>10s}")
            continue
        wk = e.get("waker") or {}
        lag = f"{e.get('waker_lag_ms'):.2f}" if e.get("waker_lag_ms") is not None else "-"
        L.append(f"{h['t_end']+args.mono_offset:12.3f} {h['frametime_ms']:7.1f} {e['block_ms']:8.1f} "
                 f"{e['overlap_ms']:8.1f} {('Y' if e['started_in_window'] else 'n'):>3s} "
                 f"{(h['cpu0_idle'] or 0)*100:9.1f} {e['out_state']:>6s} "
                 f"{str(wk.get('comm'))[:16]:>16s} {str(wk.get('cpu')):>6s} {lag:>6s} {_chain_str(e)[:30]:>30s}")
    L.append("```")
    L.append("")
    L.append("## Other dota threads blocked for >= 50% of the hitch")
    L.append("```")
    L.append(f"{'hitch_t':>12s} {'ft_ms':>7s} {'tid':>9s} {'comm':>16s} {'blocked_ms':>10s} "
             f"{'out_state':>9s} {'waker':>16s} {'wk_cpu':>6s}")
    for h in hitches:
        for e in h.get("concurrent", []):
            wk = e.get("waker") or {}
            L.append(f"{h['t_end']+args.mono_offset:12.3f} {h['frametime_ms']:7.1f} {e['tid']:9d} "
                     f"{comm_of.get(e['tid'],'?')[:16]:>16s} {e['block_ms']:10.1f} "
                     f"{e['out_state']:>9s} {str(wk.get('comm'))[:16]:>16s} {str(wk.get('cpu')):>6s}")
    L.append("```")
    L.append("")
    L.append("## All blocked dota threads during hitches (sum of block time)")
    L.append("```")
    agg = defaultdict(lambda: [0.0, 0])
    for h in hitches:
        for e in h["threads"]:
            agg[e["tid"]][0] += e["block_ms"]
            agg[e["tid"]][1] += 1
    for tid, (ms, n) in sorted(agg.items(), key=lambda kv: -kv[1][0])[:20]:
        L.append(f"{comm_of.get(tid,'?')[:18]:>18s} tid={tid:<9d} blocked_total={ms/1000:8.2f}s  hitches={n}")
    L.append("```")
    L.append("")
    L.append("## Per-hitch CPU picture (first 12)")
    hdr = (f"{'hitch_t':>12s} {'ft_ms':>7s} {'idle%':>6s} {'cpu0idle%':>9s} {'cpu0_top':>14s} "
           f"{'busy_cpu':>8s} {'top_task':>18s} {'main_block':>10s}")
    L.append("```")
    L.append(hdr)
    L.append("-" * len(hdr))
    for h in hitches[:12]:
        topc = h["top_tasks"][0]["comm"] if h["top_tasks"] else "-"
        e = next((x for x in h["threads"] if x["tid"] == main_tid), None)
        mb = f"{e['block_ms']:.0f}ms" if e else "-"
        L.append(f"{h['t_end']+args.mono_offset:12.3f} {h['frametime_ms']:7.1f} {h['idle_all']*100:6.1f} "
                 f"{(h['cpu0_idle'] or 0)*100:9.1f} {str(h['cpu0_top'])[:14]:>14s} "
                 f"{h['busiest_cpu']:8d} {topc[:18]:>18s} {mb:>10s}")
    L.append("```")
    L.append("")
    L.append("## cpu0 activity (mean seconds per window; hitch vs control)")
    c0h = defaultdict(float)
    c0c = defaultdict(float)
    for h in hitches:
        for c, v in h["cpu0_task_time"].items():
            c0h[c] += v
    for c in controls:
        for cc, v in c["cpu0_task_time"].items():
            c0c[cc] += v
    nh, nc = max(1, len(hitches)), max(1, len(controls))
    c0_idle_h = statistics.fmean([h["cpu0_idle_frac"] for h in hitches]) if hitches else 0.0
    c0_idle_c = statistics.fmean([c["cpu0_idle_frac"] for c in controls]) if controls else 0.0
    L.append("```")
    L.append(f"{'comm':28s} {'hitch_s':>9s} {'ctrl_s':>9s} {'ratio':>7s}")
    for c, v in sorted(c0h.items(), key=lambda kv: -kv[1])[:12]:
        ch = v / nh
        cc = c0c.get(c, 0.0) / nc
        L.append(f"{c[:28]:28s} {ch:9.4f} {cc:9.4f} {(ch/cc if cc>1e-9 else float('inf')):7.2f}")
    L.append(f"{'(cpu0 idle)':28s} {c0_idle_h:9.4f} {c0_idle_c:9.4f}")
    L.append("```")
    L.append("")
    L.append("## Wakers that end the main-thread stall (count over hitches)")
    L.append("```")
    wc = Counter()
    for h in hitches:
        e = next((x for x in h["threads"] if x["tid"] == main_tid), None)
        if e and e.get("waker"):
            wc[e["waker"]["comm"]] += 1
    for comm, n in wc.most_common(15):
        L.append(f"{comm[:32]:32s} {n:5d}")
    L.append("```")
    L.append("")
    L.append("## Enriched tasks during hitches (wall-normalised share, hitch - control)")
    L.append("```")
    L.append(f"{'comm':30s} {'hitch%':>8s} {'ctrl%':>8s} {'delta%':>8s} {'ratio':>7s}")
    for r in enrich[:20]:
        L.append(f"{r['comm'][:30]:30s} {r['hitch']*100:8.3f} {r['control']*100:8.3f} "
                 f"{r['delta']*100:+8.3f} {r['ratio']:7.2f}")
    L.append("```")
    L.append("")
    hb = statistics.fmean([next((x["block_ms"] for x in h["threads"] if x["tid"] == main_tid), 0.0)
                           for h in hitches]) if hitches else 0.0
    hrb = statistics.fmean([statistics.fmean([x["block_ms"] for x in h["threads"]
                                             if comm_of.get(x["tid"]) == "VKRenderThread"] or [0.0])
                            for h in hitches]) if hitches else 0.0
    cb = statistics.fmean([c["main_block_frac"] for c in controls]) if controls else 0.0
    crb = statistics.fmean([c["render_block_frac"] for c in controls]) if controls else 0.0
    hidle = statistics.fmean([h["idle_all"] for h in hitches]) if hitches else 0.0
    cidle = statistics.fmean([c["idle_all"] for c in controls]) if controls else 0.0
    L.append("## Aggregate (hitch vs control)")
    L.append(f"* cpu idle fraction      : hitch {hidle*100:.2f}%   control {cidle*100:.2f}%")
    L.append(f"* main-thread blocked    : hitch {hb:.1f}ms/window   control {cb*100:.2f}% of window")
    L.append(f"* render-thread blocked  : hitch {hrb:.1f}ms/window   control {crb*100:.2f}% of window")
    L.append("")
    L.append("## Periodicity")
    L.append("* hitch occurrence:")
    for k, v in peri.items():
        L.append(f"    - {k}: {v}")
    L.append("* main-thread stall-end times:")
    for k, v in peri_resume.items():
        L.append(f"    - {k}: {v}")
    L.append("")
    L.append("## Boundary events (switch-ins within +-10 ms of hitch start)")
    L.append("```")
    L.append(f"{'comm':30s} {'hits':>5s} {'exp':>8s} {'lift':>6s} {'events':>9s}")
    for r in boundary:
        L.append(f"{r['comm'][:30]:30s} {r['hits']:5d} {r['expected']:8.1f} "
                 f"{r['lift']:6.1f} {r['events']:9d}")
    L.append("```")
    L.append("")
    L.append("## Boundary events (switch-ins within +-10 ms of main-thread stall end)")
    L.append("```")
    L.append(f"{'comm':30s} {'hits':>5s} {'exp':>8s} {'lift':>6s} {'events':>9s}")
    for r in boundary_resume:
        L.append(f"{r['comm'][:30]:30s} {r['hits']:5d} {r['expected']:8.1f} "
                 f"{r['lift']:6.1f} {r['events']:9d}")
    L.append("```")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("perf")
    ap.add_argument("mangohud")
    ap.add_argument("offset", nargs="?", type=float, default=0.0)
    ap.add_argument("--birth-ns", type=float, default=None)
    ap.add_argument("--mono-offset", type=float, default=0.0,
                    help="epoch = perf_monotonic + this")
    ap.add_argument("--game-pid", type=int, default=None)
    ap.add_argument("--main-tid", type=int, default=None,
                    help="main thread tid (defaults to the game pid)")
    ap.add_argument("--min-frametime", type=float, default=60.0)
    ap.add_argument("--chain", type=int, default=3, help="waker chain depth")
    ap.add_argument("--control", type=int, default=300)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--window-start", type=float, default=None)
    ap.add_argument("--window-end", type=float, default=None)
    ap.add_argument("--json", default=None)
    args = ap.parse_args(argv)

    birth = int(args.birth_ns) if args.birth_ns is not None else birthtime_ns(args.mangohud)
    frames_epoch, t0 = read_mangohud(args.mangohud, birth, args.offset)
    frames = [(t - args.mono_offset, ft) for t, ft in frames_epoch]

    game_pid, comm_of = discover_threads(args.perf, args.game_pid)
    if game_pid is None:
        print("could not determine game pid; pass --game-pid", file=sys.stderr)
        return 2
    args.game_pid = game_pid
    render_tids = sorted(t for t, c in comm_of.items() if c == "VKRenderThread")

    tr = parse_trace(args.perf, set(comm_of))
    main_tid = args.main_tid
    if main_tid is None:
        if game_pid in comm_of:
            main_tid = game_pid
        else:  # no tid == tgid: pick the busiest 'dota2'-named thread
            cands = [t for t, c in comm_of.items() if c == "dota2"]
            main_tid = max(cands, key=lambda t: len(tr.sw_in_times.get(t, [])), default=None)
    perf_lo = tr.t_first if args.window_start is None else args.window_start - args.mono_offset
    perf_hi = tr.t_last if args.window_end is None else args.window_end - args.mono_offset

    hitches = hitch_analysis(tr, frames, perf_lo, perf_hi, args.min_frametime, args.chain, main_tid)
    rng = random.Random(args.seed)
    controls = control_windows(tr, hitches, perf_lo, perf_hi, args.control, rng,
                               main_tid, render_tids)
    enrich = enrichment(hitches, controls)
    peri = periodicity([h["t_end"] for h in hitches])
    peri_resume = periodicity([h["main"]["in_t"] for h in hitches if h.get("main")])
    boundary = boundary_enrichment(tr, [h["win_lo"] for h in hitches], perf_lo, perf_hi)
    resume_events = [h["main"]["in_t"] for h in hitches if h.get("main")]
    boundary_resume = boundary_enrichment(tr, resume_events, perf_lo, perf_hi)

    print(build_report(args, tr, frames, hitches, controls, enrich, comm_of, main_tid,
                       render_tids, peri, peri_resume, boundary, boundary_resume))

    if args.json:
        def clean(h):
            hh = dict(h)
            hh["t_end_epoch"] = h["t_end"] + args.mono_offset
            hh["win_lo_epoch"] = h["win_lo"] + args.mono_offset
            hh["win_hi_epoch"] = h["win_hi"] + args.mono_offset
            for e in hh.get("threads", []):
                e["out_epoch"] = e["out_t"] + args.mono_offset
                e["in_epoch"] = e["in_t"] + args.mono_offset
            m = hh.get("main")
            if m:
                m["out_epoch"] = m["out_t"] + args.mono_offset
                m["in_epoch"] = m["in_t"] + args.mono_offset
            return hh
        payload = {
            "perf_window": [tr.t_first, tr.t_last],
            "perf_window_epoch": [tr.t_first + args.mono_offset, tr.t_last + args.mono_offset],
            "mono_offset": args.mono_offset, "mangohud_offset": args.offset,
            "game_pid": game_pid, "main_tid": main_tid,
            "dota_threads": {str(t): c for t, c in sorted(comm_of.items())},
            "n_hitches": len(hitches),
            "hitches": [clean(h) for h in hitches],
            "enrichment": enrich,
            "periodicity_hitch": peri, "periodicity_resume": peri_resume,
            "boundary": boundary,
        }
        with open(args.json, "w") as fh:
            json.dump(payload, fh, indent=1, default=str)
        print(f"\n[json written to {args.json}]", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
