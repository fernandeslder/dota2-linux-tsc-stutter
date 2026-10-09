"""Game-process discovery and per-thread CPU sampling.

Threads are the usual suspect for this stutter (engine main thread saturation,
thread migration across CCDs).  We sample /proc/<pid>/task/*/stat at the
sampler's rate and report the aggregate plus the busiest thread and its
core / CCD placement.
"""

from __future__ import annotations

import os
from typing import List, Optional

from .. import util
from . import Sampler

GAME_COMMS = {"dota2", "dota2.exe", "dota2_steamrt", "dota2client"}
GAME_HINTS = ("dota 2 beta", "dota2", "dota 2")


def _comm(pid: int) -> str:
    try:
        with open(f"/proc/{pid}/comm") as fh:
            return fh.read().strip()
    except OSError:
        return ""


def _find_by_comm(name: str, exclude: set):
    """Find a live process whose comm (or argv[0] basename) is exactly *name*.

    GAME_COMM override for tests / non-Dota apps.  Exact-comm is tried first so
    a `mangohud vkcube` wrapper (comm `mangohud`) is not mistaken for `vkcube`.
    """
    if not name:
        return None
    try:
        entries = os.listdir("/proc")
    except OSError:
        return None
    cmdline_match = None
    for entry in entries:
        if not entry.isdigit():
            continue
        pid = int(entry)
        if pid in exclude:
            continue
        if _comm(pid) == name:
            return pid
        if cmdline_match is None:
            cmd = util.proc_cmdline(pid)
            if cmd and os.path.basename(cmd.split()[0]) == name:
                cmdline_match = pid
    return cmdline_match


def find_game_pid(exclude: Optional[set] = None) -> Optional[int]:
    """Best-effort discovery of the Dota process (native *or* Proton/wine).

    ``STUTTER_GAME_COMM`` overrides discovery by process name -- used by
    ``tools/validate_offcpu.py`` and `trial run --launch` so a non-Dota app
    (vkcube) can be collected against, launched *after* the collector starts.
    """
    exclude = exclude or set()
    override = os.environ.get("STUTTER_GAME_COMM", "").strip()
    if override:
        pid = _find_by_comm(override, exclude)
        if pid:
            return pid
    candidates = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        pid = int(entry)
        if pid in exclude:
            continue
        comm = _comm(pid)
        if comm in GAME_COMMS:
            candidates.append((0, pid))
            continue
        # Proton: the real game runs under a wineserver/steam child; look at cmdline
        if comm in ("wine64-preloader", "wine64", "dota2.exe"):
            cmd = util.proc_cmdline(pid).lower()
            if any(h in cmd for h in GAME_HINTS):
                candidates.append((1, pid))
    if not candidates:
        return None
    candidates.sort()
    return candidates[0][1]


class ThreadSampler(Sampler):
    name = "threads"
    columns = [
        "pid", "nthreads", "proc_cpu_pct", "main_cpu_pct",
        "busiest_tid", "busiest_cpu_pct", "busiest_cpu", "busiest_ccd",
        "proc_rss_mib", "nthreads_gt50pct",
    ]

    def __init__(self, pid: Optional[int] = None, hertz: float = 250.0):
        self.pid = pid
        self.hertz = hertz
        self._prev = {}      # tid -> (utime+stime)
        self._prev_t = None

    def _threads(self) -> dict:
        if not self.pid:
            return {}
        taskdir = f"/proc/{self.pid}/task"
        out = {}
        try:
            tids = os.listdir(taskdir)
        except OSError:
            return {}
        for tid in tids:
            txt = util.read_text(os.path.join(taskdir, tid, "stat"))
            d = util.parse_pid_stat(txt)
            if d:
                out[int(tid)] = d
        return out

    def prepare(self) -> None:
        self._prev = {tid: d["utime"] + d["stime"] for tid, d in self._threads().items()}
        self._prev_t = util.epoch()

    def sample(self, t: float) -> Optional[list]:
        if not self.pid or not os.path.exists(f"/proc/{self.pid}"):
            found = find_game_pid()
            if found:
                self.pid = found
                self._prev = {}
                self._prev_t = t
        if not self.pid:
            return [None] * len(self.columns)
        threads = self._threads()
        if not threads:
            return [None] * len(self.columns)
        dt = max(1e-6, t - (self._prev_t or t))
        cur = {}
        busiest_tid = -1
        busiest_pct = -1.0
        busiest_cpu = -1
        proc_ticks = 0
        main_pct = None
        over50 = 0
        jiff = float(os.sysconf("SC_CLK_TCK"))
        effective = 100.0 / (jiff * dt) if jiff * dt > 0 else 0.0
        for tid, d in threads.items():
            ticks = d["utime"] + d["stime"]
            cur[tid] = ticks
            prev = self._prev.get(tid)
            if prev is None:
                continue
            delta = ticks - prev
            pct = delta * effective
            proc_ticks += delta
            if pct > 50.0:
                over50 += 1
            if tid == self.pid:
                main_pct = pct
            if delta > busiest_pct:
                busiest_pct = pct
                busiest_tid = tid
                busiest_cpu = d["processor"]
        self._prev = cur
        self._prev_t = t
        proc_pct = proc_ticks * effective
        rss = None
        try:
            with open(f"/proc/{self.pid}/statm") as fh:
                pages = int(fh.read().split()[1])
            rss = pages * os.sysconf("SC_PAGE_SIZE") / 1048576.0
        except (OSError, ValueError, IndexError):
            pass
        ccd = util.ccd_of_cpu(busiest_cpu) if busiest_cpu >= 0 else None
        return [
            self.pid, len(threads), round(proc_pct, 2), _r(main_pct),
            busiest_tid if busiest_tid >= 0 else None, _r(busiest_pct if busiest_pct >= 0 else None),
            busiest_cpu if busiest_cpu >= 0 else None, ccd,
            _r(rss), over50,
        ]


def _r(x):
    return None if x is None else round(x, 2)
