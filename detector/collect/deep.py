"""Optional deep off-CPU mode: a bpftrace sched-switch profile of the game PID.

Enabled with ``stutter collect start --deep``.  It is **opt-in** because it needs
root (``sudo -n``) and a kernel-space tracer; the always-on, unprivileged sampler
in :mod:`detector.collect.collectors.offcpu` is the primary source.

The tracepoint probe fires in the context of the task being switched *out*, so
``pid`` there is that task's ``tgid``.  Guarding on ``pid == <game tgid>`` records
the moment every thread of the process leaves the CPU; the interval is closed on
the matching ``sched:sched_switch`` whose ``next_pid`` is that thread, which is why
the probe is *not* started with ``-p`` (that would filter out the switch-*in*
half).  Intervals longer than ``min_us`` are printed as timestamped
``offcpu tid=.. dur_ms=.. comm=..`` lines, and their kernel + user **stacks are
aggregated** by stack (a stack map value used as an aggregation key, exactly as
bpftrace's shipped ``biostacks.bt`` does) plus off-CPU ms/count by thread name.

bpftrace's ``nsecs`` is CLOCK_MONOTONIC, so the reader thread converts it to epoch
seconds with ``time.time() - time.monotonic()`` captured at start; every line in
``deep_offcpu.log`` is written as ``<t_epoch> <payload>`` to match the run-dir
``<name>.log`` contract.
"""

from __future__ import annotations

import os
import re
import signal
import subprocess
import threading
import time
from typing import Optional

PROGRAM = r"""
tracepoint:sched:sched_switch
{
  if (pid == %(pid)d) {
    @start[args.prev_pid] = nsecs;
    @kstk[args.prev_pid] = kstack;
    @ustk[args.prev_pid] = ustack;
  }
  if (@start[args.next_pid] != 0) {
    $d = (uint64)(nsecs - @start[args.next_pid]);
    if ($d > %(min_ns)d) {
      $ms = $d / 1000000;
      printf("offcpu tid=%%d dur_ms=%%llu comm=%%s\n",
             args.next_pid, $ms, args.next_comm);
      @offcpu_ms[args.next_comm] = sum($ms);
      @offcpu_count[args.next_comm] = count();
      @kstack_count[@kstk[args.next_pid]] = count();
      @ustack_count[@ustk[args.next_pid]] = count();
    }
    delete(@start[args.next_pid]);
    delete(@kstk[args.next_pid]);
    delete(@ustk[args.next_pid]);
  }
}
interval:s:60
{
  print(@offcpu_ms);
}
END
{
  print(@offcpu_ms);
  print(@offcpu_count);
  print(@kstack_count);
  print(@ustack_count);
}
"""  # noqa: E501


def convert_line(offset: float, line: str):
    """Map one bpftrace output line to ``(t_epoch, payload)``.

    bpftrace ``nsecs`` is CLOCK_MONOTONIC, so ``offset = time.time() -
    time.monotonic()`` captured at start turns it into epoch seconds.  Returns
    ``None`` when the line does not start with a monotonic-ns token (e.g. an
    aggregate ``print()`` line), so the caller can label it with the current time.
    """
    m = re.match(r"^(\d+)\s+(.*)$", line)
    if not m:
        return None
    return offset + int(m.group(1)) / 1e9, m.group(2)


class DeepOffCpu:
    def __init__(self, run_dir, get_pid, min_us: int = 5000, timeout_s: float = 30.0):
        self.run_dir = run_dir
        self.get_pid = get_pid
        self.min_us = int(min_us)
        self.timeout_s = timeout_s
        self.log_path = run_dir.log_path("deep_offcpu")
        self.binary = None
        self.error = None
        self.n_lines = 0
        self.started_epoch = None
        self.stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._proc: Optional[subprocess.Popen] = None

    # -- lifecycle --------------------------------------------------------
    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="deep-offcpu", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self._proc is not None:
            try:
                os.killpg(os.getpgid(self._proc.pid), signal.SIGTERM)
            except Exception:
                try:
                    self._proc.terminate()
                except Exception:
                    pass
            try:
                self._proc.wait(timeout=5)
            except Exception:
                try:
                    os.killpg(os.getpgid(self._proc.pid), signal.SIGKILL)
                except Exception:
                    pass
        if self._thread is not None:
            self._thread.join(timeout=8)

    def info(self) -> dict:
        return {
            "active": self._proc is not None and self._proc.poll() is None,
            "binary": self.binary,
            "log": os.path.basename(self.log_path),
            "min_us": self.min_us,
            "n_lines": self.n_lines,
            "started_epoch": self.started_epoch,
            "error": self.error,
        }

    # -- loop -------------------------------------------------------------
    def _wait_for_pid(self) -> Optional[int]:
        deadline = time.monotonic() + self.timeout_s
        while not self.stop_event.is_set() and time.monotonic() < deadline:
            pid = self.get_pid()
            if pid:
                return pid
            self.stop_event.wait(0.5)
        return None

    def _loop(self) -> None:
        import shutil
        self.binary = shutil.which("bpftrace")
        if not self.binary:
            self.error = "bpftrace not installed (sudo pacman -S bpftrace)"
            self.run_dir.append_event("deep_unavailable", self.error)
            return
        pid = self._wait_for_pid()
        if not pid or self.stop_event.is_set():
            self.error = "no game pid before deep start"
            self.run_dir.append_event("deep_unavailable", self.error)
            return
        prog = PROGRAM % {"pid": pid, "min_ns": self.min_us * 1000}
        cmd = [self.binary, "-e", prog]
        try:
            self._proc = subprocess.Popen(["sudo", "-n"] + cmd,
                                          stdout=subprocess.PIPE,
                                          stderr=subprocess.PIPE, text=True,
                                          bufsize=1, start_new_session=True)
        except Exception as exc:
            self.error = f"spawn failed: {exc}"
            self.run_dir.append_event("deep_unavailable", self.error)
            return

        offset = time.time() - time.monotonic()
        self.started_epoch = time.time()
        self.run_dir.append_event("deep_start", f"bpftrace pid={pid} min_us={self.min_us}")
        with open(self.log_path, "w") as lf:
            lf.write(f"# bpftrace off-CPU profile: game_pid={pid} min_us={self.min_us}\n")
            lf.write("# <t_epoch> offcpu tid=.. dur_ms=.. comm=.. ; plus periodic "
                     "aggregates (@offcpu_ms, @kstack_count, @ustack_count)\n")
            for line in self._proc.stdout:
                if self.stop_event.is_set():
                    break
                line = line.rstrip("\n")
                conv = convert_line(offset, line)
                if conv is not None:
                    epoch, payload = conv
                    lf.write(f"{epoch:.6f} {payload}\n")
                else:
                    lf.write(f"{time.time():.6f} {line}\n")
                self.n_lines += 1
                lf.flush()
            # drain stderr (permission / verifier errors)
            try:
                err = self._proc.stderr.read()
            except Exception:
                err = ""
        rc = self._proc.wait()
        if rc != 0 and not self.stop_event.is_set():
            self.error = (err or f"bpftrace exited rc={rc}").strip()[:400]
            self.run_dir.append_event("deep_error", self.error.replace("\n", " ")[:200])
        self.run_dir.append_event("deep_stop", f"rc={rc} lines={self.n_lines}")
