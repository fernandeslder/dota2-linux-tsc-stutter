"""Run-directory contract (docs/SPEC-detector.md) implementation.

`runs/<run-id>/` layout produced/consumed here:

  meta.json        run metadata (single JSON object)
  events.csv       t_epoch,label,detail   (marks; also written by `collect mark`)
  frametimes.csv   t_epoch,frametime_ms   (one row per frame, derived from MangoHud)
  <name>.csv       t_epoch,<numeric cols...>  (one row per sample)
  <name>.log       <t_epoch> <text>           (text event streams)
  raw/             untouched upstream logs (MangoHud csv, ss dumps, ...)
  out/             derived outputs (hitches.csv, stats.json, verdict.json, *.png)
  collector.json   runtime state of the running collector (pid, profile, ...)
"""

from __future__ import annotations

import json
import os
import time
from typing import Iterable, Optional

from . import util


class RunDir:
    def __init__(self, root: str):
        self.root = os.path.abspath(root)

    # -- paths -------------------------------------------------------------
    @property
    def raw(self) -> str:
        return os.path.join(self.root, "raw")

    @property
    def out(self) -> str:
        return os.path.join(self.root, "out")

    @property
    def meta_path(self) -> str:
        return os.path.join(self.root, "meta.json")

    @property
    def events_path(self) -> str:
        return os.path.join(self.root, "events.csv")

    @property
    def collector_state_path(self) -> str:
        return os.path.join(self.root, "collector.json")

    @property
    def frametimes_path(self) -> str:
        return os.path.join(self.root, "frametimes.csv")

    @property
    def run_id(self) -> str:
        return os.path.basename(self.root.rstrip("/"))

    def signal_path(self, name: str) -> str:
        return os.path.join(self.root, f"{name}.csv")

    def log_path(self, name: str) -> str:
        return os.path.join(self.root, f"{name}.log")

    # -- creation ----------------------------------------------------------
    def create(self, label: str = "", launch_opts: str = "") -> None:
        os.makedirs(self.raw, exist_ok=True)
        os.makedirs(self.out, exist_ok=True)
        os.makedirs(self.root, exist_ok=True)
        if not os.path.exists(self.events_path):
            _write_header(self.events_path, "t_epoch,label,detail")

    def exists(self) -> bool:
        return os.path.isdir(self.root)

    # -- meta --------------------------------------------------------------
    def read_meta(self) -> dict:
        try:
            with open(self.meta_path, "r") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return {}

    def write_meta(self, meta: dict) -> None:
        tmp = self.meta_path + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(meta, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp, self.meta_path)

    def update_meta(self, **kwargs) -> dict:
        meta = self.read_meta()
        meta.update(kwargs)
        self.write_meta(meta)
        return meta

    # -- events ------------------------------------------------------------
    def append_event(self, label: str, detail: str = "", t: Optional[float] = None) -> float:
        """Append one mark. Safe to call from another process (O_APPEND)."""
        if t is None:
            t = util.epoch()
        line = f"{t:.6f},{_csv_escape(label)},{_csv_escape(detail)}\n"
        os.makedirs(self.root, exist_ok=True)
        fd = os.open(self.events_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        try:
            os.write(fd, line.encode("utf-8"))
        finally:
            os.close(fd)
        return t

    def read_events(self) -> list:
        out = []
        try:
            with open(self.events_path, "r") as fh:
                next(fh, None)
                for line in fh:
                    parts = _csv_split(line.rstrip("\n"))
                    if len(parts) >= 2:
                        try:
                            out.append((float(parts[0]), parts[1], parts[2] if len(parts) > 2 else ""))
                        except ValueError:
                            continue
        except OSError:
            pass
        return out

    # -- collector runtime state ------------------------------------------
    def write_collector_state(self, state: dict) -> None:
        tmp = self.collector_state_path + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(state, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp, self.collector_state_path)

    def read_collector_state(self) -> dict:
        try:
            with open(self.collector_state_path, "r") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return {}

    def clear_collector_state(self) -> None:
        try:
            os.unlink(self.collector_state_path)
        except OSError:
            pass


class CsvWriter:
    """Single-writer CSV signal file: `t_epoch,<cols...>`."""

    def __init__(self, path: str, columns: Iterable[str], flush_interval: float = 0.5):
        self.path = path
        self.columns = list(columns)
        self.flush_interval = flush_interval
        self._fh = None
        self._last_flush = 0.0

    def open(self, append: bool = False) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        exists = os.path.exists(self.path) and os.path.getsize(self.path) > 0
        mode = "a" if (append and exists) else "w"
        self._fh = open(self.path, mode, buffering=1)
        if mode == "w":
            self._fh.write("t_epoch," + ",".join(self.columns) + "\n")

    def write(self, t: float, values: Iterable) -> None:
        if self._fh is None:
            self.open()
        row = [f"{t:.6f}"]
        for v in values:
            row.append(_num(v))
        self._fh.write(",".join(row) + "\n")
        now = time.monotonic()
        if now - self._last_flush >= self.flush_interval:
            self._fh.flush()
            self._last_flush = now

    def flush(self) -> None:
        if self._fh is not None:
            self._fh.flush()
            self._last_flush = time.monotonic()

    def close(self) -> None:
        if self._fh is not None:
            try:
                self._fh.flush()
                self._fh.close()
            finally:
                self._fh = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *exc):
        self.close()


class LogWriter:
    """Single-writer text stream: `<t_epoch> <text>` per line."""

    def __init__(self, path: str, flush_interval: float = 1.0):
        self.path = path
        self.flush_interval = flush_interval
        self._fh = None
        self._last_flush = 0.0

    def open(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._fh = open(self.path, "w", buffering=1)

    def write(self, t: float, text: str) -> None:
        if self._fh is None:
            self.open()
        text = text.rstrip("\n")
        self._fh.write(f"{t:.6f} {text}\n")
        now = time.monotonic()
        if now - self._last_flush >= self.flush_interval:
            self._fh.flush()
            self._last_flush = now

    def flush(self) -> None:
        if self._fh is not None:
            self._fh.flush()

    def close(self) -> None:
        if self._fh is not None:
            try:
                self._fh.flush()
                self._fh.close()
            finally:
                self._fh = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *exc):
        self.close()


# ---------------------------------------------------------------------------
# small csv helpers (avoid depending on csv module quirks in hot paths)
# ---------------------------------------------------------------------------


def _write_header(path: str, header: str) -> None:
    with open(path, "w") as fh:
        fh.write(header + "\n")


def _num(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.6g}"
    if isinstance(v, bool):
        return "1" if v else "0"
    return str(v)


def _csv_escape(s: str) -> str:
    if s is None:
        return ""
    s = str(s)
    if any(c in s for c in ',"\n'):
        return '"' + s.replace('"', '""') + '"'
    return s


def _csv_split(line: str) -> list:
    out = []
    cur = ""
    in_q = False
    i = 0
    while i < len(line):
        c = line[i]
        if in_q:
            if c == '"':
                if i + 1 < len(line) and line[i + 1] == '"':
                    cur += '"'
                    i += 1
                else:
                    in_q = False
            else:
                cur += c
        else:
            if c == '"':
                in_q = True
            elif c == ",":
                out.append(cur)
                cur = ""
            else:
                cur += c
        i += 1
    out.append(cur)
    return out
