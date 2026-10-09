"""`offcpu` sampler -- what the game's threads are *blocked on*.

For the game PID (all threads) this samples, at `>=100 Hz`:

* thread state from ``/proc/<pid>/task/<tid>/stat`` (R/S/D/...),
* the kernel wait channel from ``/proc/<pid>/task/<tid>/wchan``,
* the syscall number + arg0 from ``/proc/<pid>/task/<tid>/syscall`` (decoded to a
  name via a table; ioctls are told apart as nvidia vs DRM vs other),
* the thread name (``comm``).

Output (run-dir contract):

  ``threads_blocked.csv``  ``t_epoch,tid,comm,state,syscall,wchan``
  ``threads_cpu.csv``      ``t_epoch,tid,comm,cpu_pct``  (1 Hz, per thread)
  ``dstate_stacks.log``    ``<t_epoch> tid=<tid> comm=.. wchan=.. | <frames>``
                           (optional; only D-state threads, rate-limited, needs
                           ``sudo -n`` to read ``/proc/<tid>/stack``)

``threads_blocked.csv`` is deliberately **compact**: a row is written only when a
thread's ``(state, syscall, wchan)`` changes, plus a keepalive row every
``keepalive_ms``.  A row therefore means "this thread entered this bucket at
``t_epoch`` and stayed until its next row (or the run end)"; the analysis
(:mod:`detector.analyze.blocked`) rebuilds interval coverage from that, which is
all a per-hitch "blocked-on" ranking needs -- while keeping the file ~50x smaller
than a full 100 Hz dump.

Low overhead is the point: sampling ~75 threads needs ~225 ``/proc`` reads per
tick.  In Python that is ~3.3 ms/tick (>30% of a core) so a tiny C helper
(``offcpu_sampler.c``) is built with ``cc`` on first use and used instead; the
Python implementation is the fallback when no compiler exists.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import threading
import time
from typing import Callable, List, Optional

from .. import util

_HERE = os.path.dirname(os.path.abspath(__file__))
C_SRC = os.path.join(_HERE, "offcpu_sampler.c")
C_BIN = os.path.join(_HERE, "offcpu_sampler")

BLOCKED_COLUMNS = ["tid", "comm", "state", "syscall", "wchan"]
CPU_COLUMNS = ["tid", "comm", "cpu_pct"]

# x86_64 syscall number -> name (mirrors SYS_TABLE in offcpu_sampler.c).
SYSCALL_NAMES = {
    0: "read", 1: "write", 2: "open", 3: "close", 4: "stat", 5: "fstat",
    6: "lstat", 7: "poll", 8: "lseek", 9: "mmap", 10: "mprotect", 11: "munmap",
    12: "brk", 13: "rt_sigaction", 14: "rt_sigprocmask", 15: "rt_sigreturn",
    16: "ioctl", 17: "pread64", 18: "pwrite64", 19: "readv", 20: "writev",
    21: "access", 22: "pipe", 23: "select", 24: "sched_yield", 25: "mremap",
    26: "msync", 27: "mincore", 28: "madvise", 32: "dup", 33: "dup2",
    34: "pause", 35: "nanosleep", 36: "getitimer", 37: "alarm", 38: "setitimer",
    39: "getpid", 41: "socket", 42: "connect", 43: "accept", 44: "sendto",
    45: "recvfrom", 46: "sendmsg", 47: "recvmsg", 48: "shutdown", 49: "bind",
    50: "listen", 55: "getsockopt", 56: "clone", 57: "fork", 59: "execve",
    60: "exit", 61: "wait4", 62: "kill", 72: "fcntl", 73: "flock", 74: "fsync",
    75: "fdatasync", 76: "truncate", 77: "ftruncate", 78: "getdents",
    89: "readlink", 95: "umask", 96: "gettimeofday", 97: "getrlimit",
    98: "getrusage", 99: "sysinfo", 100: "times", 102: "getuid", 104: "getgid",
    107: "geteuid", 108: "getegid", 131: "sigaltstack", 137: "statfs",
    157: "prctl", 158: "arch_prctl", 186: "gettid", 247: "waitid",
    202: "futex", 203: "sched_setaffinity", 204: "sched_getaffinity",
    217: "getdents64", 218: "set_tid_address", 219: "restart_syscall",
    228: "clock_gettime", 229: "clock_getres", 230: "clock_nanosleep",
    231: "exit_group", 232: "epoll_wait", 233: "epoll_ctl", 234: "tgkill",
    257: "openat", 262: "newfstatat", 269: "futimesat", 270: "pselect6",
    271: "ppoll", 273: "set_robust_list", 281: "epoll_pwait", 288: "accept4",
    290: "eventfd2", 291: "epoll_create1", 293: "pipe2", 302: "prlimit64",
    318: "getrandom", 319: "memfd_create", 332: "statx", 334: "rseq",
    424: "pidfd_send_signal", 425: "io_uring_setup", 426: "io_uring_enter",
    441: "epoll_pwait2", 449: "futex_waitv", 452: "fchmodat2",
}

NV_IOCTL_MAGIC = 0x46   # 'F'
DRM_IOCTL_MAGIC = 0x64  # 'd'


def _sanitize(s: str) -> str:
    return s.replace(",", ".").replace("\n", " ").replace("\r", " ").strip()


def decode_syscall(nr: Optional[int], arg1: Optional[int] = None) -> str:
    """Decode a syscall number (and for ioctl, its request arg1) to a short name.

    ``None`` nr means "running"; a negative nr means "no syscall" (kernel work,
    e.g. a page fault) and is reported as ``nosys``.
    """
    if nr is None:
        return "-"
    if nr < 0:
        return "nosys"
    name = SYSCALL_NAMES.get(nr)
    if name == "ioctl":
        if arg1 is None:
            return "ioctl"
        typ = (arg1 >> 8) & 0xFF
        if typ == NV_IOCTL_MAGIC:
            return "ioctl_nv"
        if typ == DRM_IOCTL_MAGIC:
            return "ioctl_drm"
        return "ioctl"
    if name is not None:
        return name
    return f"sys_{nr}"


def is_nvidia_ioctl(request: Optional[int]) -> bool:
    return request is not None and ((request >> 8) & 0xFF) == NV_IOCTL_MAGIC


def parse_syscall_line(text: str) -> str:
    """Turn the raw contents of ``/proc/<tid>/syscall`` into a decoded name."""
    text = text.strip()
    if not text:
        return "nosys"
    if text.startswith("running"):
        return "-"
    parts = text.split()
    if not parts or parts[0].startswith("-"):
        return "nosys"
    try:
        nr = int(parts[0], 10)
    except ValueError:
        return "nosys"
    arg1 = None
    if len(parts) >= 3 and nr == 16:  # ioctl: arg0=fd, arg1=request
        try:
            arg1 = int(parts[2], 0)
        except ValueError:
            arg1 = None
    return decode_syscall(nr, arg1)


# ---------------------------------------------------------------------------
# native helper build
# ---------------------------------------------------------------------------

def native_binary(rebuild: bool = False) -> Optional[str]:
    """Return a path to the compiled C sampler, building it on first use.

    Returns None when no C compiler is available (the caller falls back to the
    Python implementation).
    """
    cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    if not cc:
        return None
    try:
        if (not rebuild and os.path.exists(C_BIN)
                and os.path.getmtime(C_BIN) >= os.path.getmtime(C_SRC)):
            return C_BIN
        tmp = C_BIN + ".tmp"
        p = subprocess.run([cc, "-O2", "-o", tmp, C_SRC],
                           capture_output=True, text=True, timeout=120)
        if p.returncode != 0:
            return None
        os.replace(tmp, C_BIN)
        os.chmod(C_BIN, 0o755)
        return C_BIN
    except Exception:
        return None


# ---------------------------------------------------------------------------
# snapshot parsing (shared by the Python fallback and the unit tests)
# ---------------------------------------------------------------------------

def _read(path: str) -> Optional[str]:
    try:
        with open(path, "r") as fh:
            return fh.read()
    except OSError:
        return None


def _parse_stat_comm_state_ticks(text: str):
    lp = text.find("(")
    rp = text.rfind(")")
    if lp < 0 or rp < 0 or rp < lp:
        return None
    comm = text[lp + 1:rp]
    rest = text[rp + 2:].split()
    if len(rest) < 13:
        return None
    try:
        ticks = int(rest[11]) + int(rest[12])
    except ValueError:
        return None
    return _sanitize(comm), rest[0], ticks


def snapshot_threads(pid: int) -> List[dict]:
    """One pass over every thread of ``pid`` (the Python fallback's inner loop)."""
    taskdir = f"/proc/{pid}/task"
    try:
        tids = os.listdir(taskdir)
    except OSError:
        return []
    rows = []
    for name in tids:
        if not name.isdigit():
            continue
        tid = int(name)
        base = f"{taskdir}/{tid}"
        stat = _read(os.path.join(base, "stat"))
        if stat is None:
            continue
        parsed = _parse_stat_comm_state_ticks(stat)
        if parsed is None:
            continue
        comm, state, ticks = parsed
        wchan = (_read(os.path.join(base, "wchan")) or "").strip() or "-"
        wchan = _sanitize(wchan)
        sc = parse_syscall_line(_read(os.path.join(base, "syscall")) or "")
        rows.append({"tid": tid, "comm": comm, "state": state,
                     "syscall": sc, "wchan": wchan, "ticks": ticks})
    return rows


def python_sampler_loop(get_pid: Callable[[], Optional[int]], blocked_path: str,
                        cpu_path: Optional[str], hz: float, keepalive_ms: float,
                        stop_event: threading.Event, duration: float = 0.0,
                        stats: Optional[dict] = None) -> None:
    """Pure-Python equivalent of ``offcpu_sampler.c`` (fallback / tests)."""
    interval = 1.0 / max(1.0, float(hz))
    clk = float(os.sysconf("SC_CLK_TCK")) or 100.0
    last: dict = {}          # tid -> (state, syscall, wchan, last_write)
    prev_ticks: dict = {}    # tid -> last flushed cpu ticks
    comm_of: dict = {}       # tid -> comm
    t_start = util.epoch()
    next_t = time.monotonic()
    next_cpu = t_start + 1.0

    with open(blocked_path, "w") as bf:
        bf.write("t_epoch," + ",".join(BLOCKED_COLUMNS) + "\n")
        cf = open(cpu_path, "w") if cpu_path else None
        if cf:
            cf.write("t_epoch," + ",".join(CPU_COLUMNS) + "\n")
        while not stop_event.is_set():
            t = util.epoch()
            if duration and (t - t_start) >= duration:
                break
            pid = get_pid()
            if pid:
                cur_ticks: dict = {}
                for r in snapshot_threads(pid):
                    tid = r["tid"]
                    comm_of[tid] = r["comm"]
                    cur_ticks[tid] = r["ticks"]
                    prev = last.get(tid)
                    changed = (prev is None or prev[0] != r["state"]
                               or prev[1] != r["syscall"] or prev[2] != r["wchan"])
                    if changed or (t - (prev[3] if prev else 0.0)) * 1000.0 >= keepalive_ms:
                        bf.write(f"{t:.6f},{tid},{r['comm']},{r['state']},"
                                 f"{r['syscall']},{r['wchan']}\n")
                        last[tid] = (r["state"], r["syscall"], r["wchan"], t)
                        prev_ticks.setdefault(tid, r["ticks"])
                if cf and t >= next_cpu:
                    dt = max(1e-3, 1.0)
                    for tid, ticks in cur_ticks.items():
                        p0 = prev_ticks.get(tid, ticks)
                        prev_ticks[tid] = ticks
                        d = ticks - p0
                        if d <= 0:
                            continue
                        cf.write(f"{t:.6f},{tid},{comm_of.get(tid, '')},"
                                 f"{d / (clk * dt) * 100.0:.3f}\n")
                    cf.flush()
                    next_cpu = t + 1.0
                bf.flush()
            next_t += interval
            delay = next_t - time.monotonic()
            if delay > 0:
                stop_event.wait(delay)
            else:
                next_t = time.monotonic()
        if cf:
            cf.flush()
            cf.close()
        bf.flush()
    if stats is not None:
        stats["mode"] = "python"


# ---------------------------------------------------------------------------
# D-state kernel stacks (optional; needs sudo -n)
# ---------------------------------------------------------------------------

class DStateStackCapture:
    """Rate-limited ``/proc/<tid>/stack`` capture for threads in ``D`` state.

    Reading ``/proc/<tid>/stack`` needs CAP_SYS_ADMIN, so each read shells out to
    ``sudo -n cat``.  If passwordless sudo is unavailable the capture disables
    itself after the first failure.  Only ``D`` (uninterruptible sleep) threads
    are captured, one every ``min_interval_ms`` at most, and the same
    ``(tid, wchan)`` pair is not re-read more than once per ``cache_s`` seconds.
    """

    def __init__(self, run_dir, log_path: str, get_pid, min_interval_ms: float = 250.0,
                 max_per_s: float = 2.0, cache_s: float = 5.0, on_event=None):
        self.run_dir = run_dir
        self.log_path = log_path
        self.get_pid = get_pid
        self.min_interval_ms = min_interval_ms
        self.max_per_s = max_per_s
        self.cache_s = cache_s
        self.on_event = on_event
        self.stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._seen: dict = {}
        self.enabled = True
        self.n_stacks = 0

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="offcpu-stacks", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=3)

    def _loop(self) -> None:
        last_read = 0.0
        with open(self.log_path, "w") as lf:
            lf.write("# t_epoch tid=.. comm=.. wchan=.. | kernel-stack frames\n")
            while not self.stop_event.wait(max(0.05, self.min_interval_ms / 1000.0)):
                if not self.enabled:
                    continue
                pid = self.get_pid()
                if not pid:
                    continue
                now = util.epoch()
                if now - last_read < 1.0 / max(0.01, self.max_per_s):
                    continue
                try:
                    tids = [int(x) for x in os.listdir(f"/proc/{pid}/task") if x.isdigit()]
                except OSError:
                    continue
                for tid in tids:
                    st = _read(f"/proc/{pid}/task/{tid}/stat")
                    if st is None:
                        continue
                    parsed = _parse_stat_comm_state_ticks(st)
                    if parsed is None:
                        continue
                    comm, state, _ = parsed
                    if state != "D":
                        continue
                    wchan = (_read(f"/proc/{pid}/task/{tid}/wchan") or "").strip()
                    key = (tid, wchan)
                    if now - self._seen.get(key, 0.0) < self.cache_s:
                        continue
                    self._seen[key] = now
                    p = subprocess.run(["sudo", "-n", "cat", f"/proc/{pid}/task/{tid}/stack"],
                                       capture_output=True, text=True, timeout=5)
                    if p.returncode != 0:
                        self.enabled = False
                        if self.on_event:
                            self.on_event("offcpu_stacks_disabled",
                                          (p.stderr or "sudo -n failed").strip()[:160])
                        return
                    frames = " ; ".join(l.strip() for l in p.stdout.splitlines() if l.strip())
                    lf.write(f"{now:.6f} tid={tid} comm={comm} wchan={wchan or '-'} | {frames}\n")
                    lf.flush()
                    self.n_stacks += 1
                    last_read = now
                    break


# ---------------------------------------------------------------------------
# the component the supervisor owns
# ---------------------------------------------------------------------------

class OffCpuSampler:
    """Owns the off-CPU sampling (native helper or Python fallback) + D stacks."""

    def __init__(self, run_dir, pid: Optional[int] = None, hz: float = 100.0,
                 keepalive_ms: float = 1000.0, duration: float = 0.0,
                 native: bool = True, capture_stacks: bool = False,
                 stack_min_interval_ms: float = 250.0, stack_max_per_s: float = 2.0,
                 stack_cache_s: float = 5.0):
        self.run_dir = run_dir
        self.pid = pid
        self.hz = float(hz)
        self.keepalive_ms = float(keepalive_ms)
        self.duration = float(duration)
        self.use_native = bool(native)
        self.capture_stacks = bool(capture_stacks)
        self.stack_min_interval_ms = stack_min_interval_ms
        self.stack_max_per_s = stack_max_per_s
        self.stack_cache_s = stack_cache_s

        self.blocked_path = run_dir.signal_path("threads_blocked")
        self.cpu_path = run_dir.signal_path("threads_cpu")
        self.stack_log = run_dir.log_path("dstate_stacks")

        self.stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._proc: Optional[subprocess.Popen] = None
        self.stacks: Optional[DStateStackCapture] = None
        self.mode = "off"
        self.binary: Optional[str] = None
        self.start_epoch = util.epoch()

    # -- lifecycle --------------------------------------------------------
    def start(self) -> None:
        self.start_epoch = util.epoch()
        if self.use_native:
            self.binary = native_binary()
        if self.binary:
            self.mode = "native"
            self._thread = threading.Thread(target=self._native_loop,
                                            name="offcpu-native", daemon=True)
        else:
            self.mode = "python"
            self._thread = threading.Thread(target=self._python_loop,
                                            name="offcpu-python", daemon=True)
        self._thread.start()
        if self.capture_stacks:
            self.stacks = DStateStackCapture(
                self.run_dir, self.stack_log, lambda: self.pid,
                min_interval_ms=self.stack_min_interval_ms,
                max_per_s=self.stack_max_per_s, cache_s=self.stack_cache_s,
                on_event=lambda label, detail: self.run_dir.append_event(label, detail))
            self.stacks.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self._proc is not None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
        if self._thread is not None:
            self._thread.join(timeout=8)
        if self.stacks is not None:
            self.stacks.stop()

    def info(self) -> dict:
        out = {
            "mode": self.mode,
            "hz": self.hz,
            "keepalive_ms": self.keepalive_ms,
            "pid": self.pid,
            "blocked_csv": os.path.basename(self.blocked_path),
            "cpu_csv": os.path.basename(self.cpu_path),
            "binary": self.binary,
            "stacks": bool(self.stacks and self.stacks.enabled),
            "n_stacks": (self.stacks.n_stacks if self.stacks else 0),
        }
        for key, path in (("blocked_rows", self.blocked_path),
                          ("cpu_rows", self.cpu_path)):
            try:
                with open(path) as fh:
                    out[key] = max(0, sum(1 for _ in fh) - 1)
            except OSError:
                out[key] = 0
        return out

    # -- loops ------------------------------------------------------------
    def _native_loop(self) -> None:
        # `collect start` normally runs *before* the game is launched, so wait
        # for the pid (set by the supervisor's game monitor) before spawning the
        # helper -- otherwise it would opendir /proc/0/task and exit at once.
        while not self.stop_event.is_set() and not self.pid:
            self.stop_event.wait(0.3)
        if self.stop_event.is_set() or not self.pid:
            return
        cmd = [self.binary, "--pid", str(self.pid),
               "--blocked-out", self.blocked_path, "--cpu-out", self.cpu_path,
               "--hz", str(int(round(self.hz))),
               "--keepalive-ms", str(self.keepalive_ms)]
        if self.duration:
            cmd += ["--duration", str(self.duration)]
        try:
            self._proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL,
                                          stdout=subprocess.DEVNULL,
                                          stderr=subprocess.DEVNULL)
            self._proc.wait()
        except Exception:
            # fall back to Python for the remainder of the run
            self.mode = "python"
            self._python_loop()

    def _python_loop(self) -> None:
        python_sampler_loop(lambda: self.pid, self.blocked_path, self.cpu_path,
                            self.hz, self.keepalive_ms, self.stop_event,
                            duration=self.duration)


def main(argv: Optional[list] = None) -> int:
    """Dev/test entry: sample an existing PID for N seconds (no collector)."""
    import argparse
    ap = argparse.ArgumentParser(prog="offcpu")
    ap.add_argument("--pid", type=int, required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--hz", type=float, default=100.0)
    ap.add_argument("--seconds", type=float, default=5.0)
    ap.add_argument("--python", action="store_true", help="force the fallback")
    args = ap.parse_args(argv)
    os.makedirs(args.out_dir, exist_ok=True)
    from ..rundir import RunDir
    rd = RunDir(args.out_dir)
    s = OffCpuSampler(rd, pid=args.pid, hz=args.hz, duration=args.seconds,
                      native=not args.python)
    s.start()
    time.sleep(args.seconds + 0.5)
    s.stop()
    import json
    print(json.dumps(s.info(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
