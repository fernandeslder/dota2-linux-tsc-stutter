"""Load a run-dir that follows the run-dir data contract.

Contract (``docs/SPEC-detector.md``)::

    runs/<run-id>/
      meta.json
      events.csv            t_epoch,label,detail
      frametimes.csv        t_epoch,frametime_ms   (one row per frame)
      <name>.csv            t_epoch,<numeric cols...>
      <name>.log            <t_epoch> <text>
      raw/                  untouched raw logs
      out/                  derived outputs

Every ``<name>.csv`` other than ``events.csv`` / ``frametimes.csv`` is treated
generically: each numeric column becomes a correlation signal. Nothing is hardcoded.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from .config import DEFAULT_WARMUP_S, MAX_PLAUSIBLE_FRAMETIME_MS
from .blocked import SPECIAL_CSV as _SPECIAL_CSV

RESERVED_CSV = {"events.csv", "frametimes.csv"}


class RunDirError(RuntimeError):
    pass


@dataclass
class Signal:
    """One generic ``<name>.csv`` stream: an epoch time column + numeric columns."""

    name: str
    path: str
    t: np.ndarray
    columns: dict

    def dt_median(self) -> float:
        if len(self.t) < 2:
            return float("nan")
        return float(np.median(np.diff(self.t)))


@dataclass
class LogStream:
    """One ``<name>.log`` stream: ``<t_epoch> <text>`` per line."""

    name: str
    path: str
    t: np.ndarray
    lines: list


@dataclass
class RunDir:
    path: str
    run_id: str
    meta: dict
    events: list                                  # list of (t, label, detail)
    t: np.ndarray                                 # frame epoch seconds (sorted)
    frametime_ms: np.ndarray                      # frame frametimes (ms)
    signals: dict = field(default_factory=dict)   # name -> Signal
    logs: dict = field(default_factory=dict)      # name -> LogStream
    warnings: list = field(default_factory=list)
    frametime_quality: dict = field(default_factory=dict)

    def event_labels(self) -> list:
        return [e[1] for e in self.events]

    def first_mark(self, label: str) -> Optional[float]:
        for t, lab, _ in self.events:
            if lab == label:
                return t
        return None

    def warmup_end(self, fallback_s: float = DEFAULT_WARMUP_S) -> float:
        """Warm-up end = the ``warmup_end`` mark, else ``run_start + fallback_s``."""
        mark = self.first_mark("warmup_end")
        if mark is not None:
            return mark
        start = self.first_mark("run_start")
        if start is None and len(self.t):
            start = float(self.t[0])
        if start is None:
            start = 0.0
        return float(start) + fallback_s

    def t_end(self) -> float:
        end = self.first_mark("window_end")
        if end is not None:
            return end
        if len(self.t):
            return float(self.t[-1]) + float(self.frametime_ms[-1]) / 1000.0
        return 0.0


def _read_csv_numeric(path: str):
    """Read a CSV with a header; return ``(header, 2D float array, stats)``.

    Individual cells that are empty or non-numeric become ``NaN`` (never drop the
    whole row) -- real signal CSVs (gpu.csv, threads.csv, ...) legitimately leave
    cells blank, and dropping the row would silently discard the *entire* signal.
    Only rows whose time column fails to parse are dropped. The first column is
    the epoch time column.
    """
    stats = {"rows_parsed": 0, "rows_dropped_time": 0, "cells_nan": 0}
    with open(path, "r", errors="replace") as fh:
        header_line = fh.readline()
        if not header_line:
            return [], np.empty((0, 0)), stats
        header = [h.strip() for h in header_line.rstrip("\n").split(",")]
        ncol = len(header)
        rows = []
        for line in fh:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split(",")
            try:
                t = float(parts[0])
            except (ValueError, IndexError):
                stats["rows_dropped_time"] += 1
                continue
            vals = [t]
            for j in range(1, ncol):
                try:
                    vals.append(float(parts[j]))
                except (ValueError, IndexError):
                    vals.append(np.nan)
                    stats["cells_nan"] += 1
            rows.append(vals)
    stats["rows_parsed"] = len(rows)
    if not rows:
        return header, np.empty((0, ncol)), stats
    arr = np.asarray(rows, dtype=float)
    return header, arr, stats


def sanitize_frametimes(t: np.ndarray, f: np.ndarray,
                        max_ms: float = MAX_PLAUSIBLE_FRAMETIME_MS):
    """Drop physically implausible per-frame frametimes and report the tally.

    Rejects non-finite, non-positive, and ``> max_ms`` values (a MangoHud logging
    glitch writes ``fps~1e-5, frametime~1e8 ms`` a couple of times per run; left
    in, it poisons ``worst_ms`` and the fps lows). ``t`` and ``f`` stay aligned.
    """
    f = np.asarray(f, dtype=float)
    n = f.size
    finite = np.isfinite(f)
    positive = f > 0
    plausible = f <= max_ms
    keep = finite & positive & plausible
    bad = np.flatnonzero(~keep)
    examples = [{"t_epoch": float(t[i]), "frametime_ms": float(f[i])} for i in bad[:5]]
    quality = {
        "rows_total": int(n),
        "rows_kept": int(keep.sum()),
        "rows_rejected": int((~keep).sum()),
        "reasons": {
            "nonfinite": int((~finite).sum()),
            "nonpositive": int((finite & ~positive).sum()),
            "over_max": int((finite & positive & ~plausible).sum()),
        },
        "max_plausible_ms": float(max_ms),
        "rejected_examples": examples,
    }
    return np.asarray(t)[keep], f[keep], quality


def load_signal(path: str, name: str) -> Signal:
    header, arr, _ = _read_csv_numeric(path)
    if arr.size == 0 or len(header) < 2:
        return Signal(name=name, path=path, t=np.empty(0), columns={})
    order = np.argsort(arr[:, 0], kind="stable")
    t = arr[order, 0]
    columns = {}
    for j in range(1, len(header)):
        cols = header[j]
        if not cols:
            continue
        columns[cols] = arr[order, j]
    return Signal(name=name, path=path, t=t, columns=columns)


def load_log(path: str, name: str) -> LogStream:
    ts, lines = [], []
    with open(path, "r", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split(" ", 1)
            try:
                t = float(parts[0])
            except (ValueError, IndexError):
                continue
            ts.append(t)
            lines.append(parts[1] if len(parts) > 1 else "")
    order = np.argsort(np.asarray(ts, dtype=float), kind="stable") if ts else []
    t = np.asarray(ts, dtype=float)[order] if ts else np.empty(0)
    ls = [lines[i] for i in order] if ts else []
    return LogStream(name=name, path=path, t=t, lines=ls)


def load_events(path: str) -> list:
    events = []
    if not os.path.exists(path):
        return events
    with open(path, "r", errors="replace") as fh:
        header = fh.readline()
        for line in fh:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split(",")
            if len(parts) < 2:
                continue
            try:
                t = float(parts[0])
            except ValueError:
                continue
            label = parts[1].strip()
            detail = parts[2].strip() if len(parts) > 2 else ""
            events.append((t, label, detail))
    events.sort(key=lambda e: e[0])
    return events


def load_rundir(path: str) -> RunDir:
    if not os.path.isdir(path):
        raise RunDirError(f"run-dir does not exist: {path}")

    meta = {}
    load_warnings = []
    meta_path = os.path.join(path, "meta.json")
    if os.path.exists(meta_path):
        try:
            with open(meta_path) as fh:
                meta = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            load_warnings.append(f"meta.json unreadable: {exc}")
            meta = {}
    run_id = meta.get("run_id") or os.path.basename(os.path.normpath(path))

    events = load_events(os.path.join(path, "events.csv"))

    ft_path = os.path.join(path, "frametimes.csv")
    if not os.path.exists(ft_path):
        raise RunDirError(f"frametimes.csv missing in {path}")
    header, arr, arr_stats = _read_csv_numeric(ft_path)
    if arr.size == 0:
        raise RunDirError(f"frametimes.csv empty in {path}")
    order = np.argsort(arr[:, 0], kind="stable")
    t = arr[order, 0]
    ft_col = None
    for cand in ("frametime_ms", "frametime", "ms"):
        if cand in header:
            ft_col = header.index(cand)
            break
    if ft_col is None:
        if len(header) < 2:
            raise RunDirError(f"frametimes.csv has no frametime column: {header}")
        ft_col = 1
    raw_ft = arr[order, ft_col]
    t, frametime_ms, ft_quality = sanitize_frametimes(t, raw_ft)
    ft_quality["rows_unparseable"] = arr_stats.get("rows_dropped_time", 0)
    if ft_quality["rows_rejected"]:
        load_warnings.append(
            f"data quality: dropped {ft_quality['rows_rejected']} implausible "
            f"frametime(s) (>{MAX_PLAUSIBLE_FRAMETIME_MS:.0f} ms / non-positive / non-finite)")

    signals, logs = {}, {}
    for fname in sorted(os.listdir(path)):
        full = os.path.join(path, fname)
        if not os.path.isfile(full):
            continue
        base, ext = os.path.splitext(fname)
        if ext == ".csv" and fname not in RESERVED_CSV and fname not in _SPECIAL_CSV:
            sig = load_signal(full, base)
            if len(sig.t):
                signals[base] = sig
        elif ext == ".log":
            logs[base] = load_log(full, base)

    rd = RunDir(path=path, run_id=run_id, meta=meta, events=events,
                t=t, frametime_ms=frametime_ms, signals=signals, logs=logs,
                warnings=list(load_warnings), frametime_quality=ft_quality)
    if len(t) == 0:
        rd.warnings.append("no frames loaded")
    return rd
