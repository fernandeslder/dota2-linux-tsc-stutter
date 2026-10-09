"""Unit tests for the optional `--deep` bpftrace module (no tracing attached)."""

import os
import threading
import time

from detector.collect.deep import PROGRAM, DeepOffCpu, convert_line
from detector.collect.rundir import RunDir


def test_convert_line_monotonic_to_epoch():
    offset = 1_791_395_966.0          # time.time() - time.monotonic()
    line = "104742943715518 offcpu tid=4321 dur_ms=12 comm=dota2 kstack=[a;b] ustack=[c]"
    epoch, payload = convert_line(offset, line)
    assert epoch == offset + 104742943715518 / 1e9
    assert payload.startswith("offcpu tid=4321 dur_ms=12")
    assert "dota2" in payload


def test_convert_line_non_nsecs():
    assert convert_line(0.0, "@offcpu_ms[render]: 123") is None
    assert convert_line(0.0, "") is None


def test_program_renders():
    prog = PROGRAM % {"pid": 4242, "min_ns": 5_000_000}
    assert "tracepoint:sched:sched_switch" in prog
    assert "pid == 4242" in prog
    assert "$d > 5000000" in prog
    assert "kstack" in prog and "ustack" in prog
    assert "offcpu tid=" in prog
    assert "(uint64)(nsecs - @start[args.next_pid])" in prog   # unsigned duration
    assert "@kstack_count[" in prog and "@ustack_count[" in prog
    assert "print(@offcpu_ms)" in prog


def test_deep_no_pid_disables(tmp_path):
    rd = RunDir(str(tmp_path))
    d = DeepOffCpu(rd, get_pid=lambda: None, timeout_s=0.4)
    d.start()
    d.stop()
    info = d.info()
    assert info["active"] is False
    assert "no game pid" in (info["error"] or "")
    assert not os.path.exists(d.log_path)


def test_deep_stop_without_start_is_safe(tmp_path):
    d = DeepOffCpu(RunDir(str(tmp_path)), get_pid=lambda: 1, timeout_s=0.1)
    d.stop()  # no thread, no proc
    assert d.info()["active"] is False
