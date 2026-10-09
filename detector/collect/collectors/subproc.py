"""Samplers and tailers that need an external command or a live file.

- TcpInfo    : `ss -tin` retrans/loss/rtt for the spectate stream (+ raw dump)
- PipeWire   : `pw-top -b -n 1` xrun counters
- KWinState  : `qdbus6` compositing state (frame stats come from the journal)
- JournalTailer : `journalctl -f -o short-unix` -> <t_epoch> <line> log files
- FileTailer : follow a growing text file (Dota `console.log`)

All external commands are spawned as children of the supervisor; the
supervisor tears them down on stop so no orphans survive.
"""

from __future__ import annotations

import os
import subprocess
import threading
from typing import List, Optional

from .. import util
from . import Sampler


def _socket_retrans(info: str):
    """Extract (retrans_segs, total_segs, rtt_ms, cwnd, bytes_retrans) from ss -i info."""
    retrans = total = rtt = cwnd = bytes_retrans = None
    for tok in info.split():
        if ":" not in tok:
            continue
        k, v = tok.split(":", 1)
        if k == "retrans" and "/" in v:
            a, b = v.split("/", 1)
            try:
                retrans = int(a)
                total = int(b)
            except ValueError:
                pass
        elif k == "rtt":
            try:
                rtt = float(v.split("/")[0])
            except ValueError:
                pass
        elif k == "cwnd":
            try:
                cwnd = int(v)
            except ValueError:
                pass
        elif k == "bytes_retrans":
            try:
                bytes_retrans = int(v)
            except ValueError:
                pass
    return retrans, total, rtt, cwnd, bytes_retrans


def parse_ss_tin(text: str) -> dict:
    """Parse `ss -tin` output into an aggregate dict."""
    sockets = []
    cur = None
    for line in text.splitlines()[1:]:
        if not line.strip():
            continue
        if line[0].isspace():
            if cur is not None:
                r, tot, rtt, cwnd, br = _socket_retrans(line.strip())
                cur.update(retrans=r, total_segs=tot, rtt=rtt, cwnd=cwnd, bytes_retrans=br)
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        cur = {"state": parts[0], "local": parts[3], "peer": parts[4],
               "retrans": None, "total_segs": None, "rtt": None, "cwnd": None,
               "bytes_retrans": None}
        sockets.append(cur)
    estab = [s for s in sockets if s["state"] == "ESTAB"]
    retrans = sum(s["retrans"] or 0 for s in estab)
    total = sum(s["total_segs"] or 0 for s in estab)
    n_retrans = sum(1 for s in estab if (s["retrans"] or 0) > 0)
    rtts = sorted(s["rtt"] for s in estab if s["rtt"] is not None)
    cwnds = [s["cwnd"] for s in estab if s["cwnd"] is not None]
    game = [s for s in estab if _is_game_port(s["local"]) or _is_game_port(s["peer"])]
    return {
        "n_tcp": len(sockets),
        "n_estab": len(estab),
        "retrans_segs": retrans,
        "retrans_total_segs": total,
        "n_sock_retrans": n_retrans,
        "rtt_max_ms": max(rtts) if rtts else None,
        "rtt_p50_ms": rtts[len(rtts) // 2] if rtts else None,
        "cwnd_min": min(cwnds) if cwnds else None,
        "game_socks": len(game),
        "game_retrans_segs": sum(s["retrans"] or 0 for s in game),
        "game_rtt_ms": max((s["rtt"] for s in game if s["rtt"] is not None), default=None),
    }


def _is_game_port(addr: str) -> bool:
    if ":" not in addr:
        return False
    try:
        port = int(addr.rsplit(":", 1)[1])
    except ValueError:
        return False
    # Dota 2 / Steam datagram + GC ranges
    return 27000 <= port <= 27100 or 3478 <= port <= 3480 or port in (27015, 27016)


class TcpInfo(Sampler):
    name = "net_tcp"
    columns = ["n_tcp", "n_estab", "retrans_segs", "retrans_total_segs",
               "n_sock_retrans", "rtt_max_ms", "rtt_p50_ms", "cwnd_min",
               "game_socks", "game_retrans_segs", "game_rtt_ms"]

    def __init__(self, raw_path: Optional[str] = None):
        self.raw_path = raw_path
        self._prev = None

    def sample(self, t: float) -> Optional[list]:
        if not util.have("ss"):
            return [None] * len(self.columns)
        rc, out, _ = util.run_capture(["ss", "-tin"], timeout=4.0)
        if rc != 0:
            return [None] * len(self.columns)
        if self.raw_path:
            try:
                with open(self.raw_path, "a") as fh:
                    fh.write(f"# t={t:.6f}\n")
                    fh.write(out)
                    if not out.endswith("\n"):
                        fh.write("\n")
            except OSError:
                pass
        agg = parse_ss_tin(out)
        row = [agg.get(c) for c in self.columns]
        return row


class PipeWire(Sampler):
    name = "pipewire"
    columns = ["xruns_total", "xruns_delta", "n_nodes", "max_busy"]

    def __init__(self):
        self._prev_total = None

    def sample(self, t: float) -> Optional[list]:
        if not util.have("pw-top"):
            return [None] * len(self.columns)
        rc, out, _ = util.run_capture(["pw-top", "-b", "-n", "1"], timeout=4.0)
        total, nodes, busy = _parse_pw_top(out)
        delta = None
        if total is not None and self._prev_total is not None:
            delta = total - self._prev_total
        if total is not None:
            self._prev_total = total
        return [total, delta, nodes, busy]


def _parse_pw_top(text: str):
    total = None
    nodes = 0
    busy = None
    err_idx = None
    for line in text.splitlines():
        parts = line.split()
        if "ERR" in parts:
            err_idx = parts.index("ERR")
            continue
        if err_idx is None or not parts:
            continue
        if len(parts) <= err_idx:
            continue
        try:
            total = (total or 0) + int(parts[err_idx])
            nodes += 1
        except ValueError:
            continue
        # last numeric column is the load ratio
        for tok in reversed(parts):
            try:
                v = float(tok)
                busy = v if busy is None else max(busy, v)
                break
            except ValueError:
                continue
    return total, nodes, busy


class KWinState(Sampler):
    name = "kwin"
    columns = ["compositing_active"]

    def sample(self, t: float) -> Optional[list]:
        if not util.have("qdbus6"):
            return [None]
        rc, out, _ = util.run_capture(
            ["qdbus6", "org.kde.KWin", "/Compositor", "org.kde.kwin.Compositing.active"],
            timeout=3.0)
        if rc != 0:
            return [None]
        return [1 if out.strip().lower() == "true" else 0]


class JournalTailer:
    """`journalctl -f -o short-unix` -> LogWriter with epoch-prefixed lines."""

    def __init__(self, name: str, log_writer, filters: List[str]):
        self.name = name
        self.log_writer = log_writer
        self.filters = filters
        self.proc = None
        self._thread = None
        self._stop = threading.Event()

    def start(self) -> None:
        if not util.have("journalctl"):
            return
        cmd = ["journalctl", "-f", "-n", "0", "-o", "short-unix"] + self.filters
        try:
            self.proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, bufsize=1, start_new_session=False,
                preexec_fn=util.preexec_pdeathsig())
        except OSError:
            self.proc = None
            return
        self._thread = threading.Thread(target=self._run, name=f"log-{self.name}", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        assert self.proc is not None and self.proc.stdout is not None
        for line in self.proc.stdout:
            if self._stop.is_set():
                break
            line = line.rstrip("\n")
            if not line:
                continue
            tok, _, rest = line.partition(" ")
            try:
                t = float(tok)
            except ValueError:
                t = util.epoch()
                rest = line
            self.log_writer.write(t, rest)

    def stop(self) -> None:
        self._stop.set()
        if self.proc is not None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=3)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
            finally:
                self.proc = None
        if self._thread is not None:
            self._thread.join(timeout=3)
            self._thread = None


class FileTailer:
    """Follow a growing text file, prefixing each new line with the epoch."""

    def __init__(self, name: str, path: str, log_writer, poll: float = 0.5):
        self.name = name
        self.path = path
        self.log_writer = log_writer
        self.poll = poll
        self._thread = None
        self._stop = threading.Event()
        self._offset = 0

    def start(self) -> None:
        if not self.path or not os.path.exists(self.path):
            return
        try:
            self._offset = os.path.getsize(self.path)
        except OSError:
            self._offset = 0
        self._thread = threading.Thread(target=self._run, name=f"tail-{self.name}", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.wait(self.poll):
            try:
                size = os.path.getsize(self.path)
                if size < self._offset:
                    self._offset = 0  # rotated
                if size == self._offset:
                    continue
                with open(self.path, "r", errors="replace") as fh:
                    fh.seek(self._offset)
                    data = fh.read()
                    self._offset = fh.tell()
                for line in data.splitlines():
                    if line.strip():
                        self.log_writer.write(util.epoch(), line)
            except OSError:
                continue

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3)
            self._thread = None
