"""Unit tests for the `offcpu` sampler (decode tables + both implementations)."""

import os
import threading
import time

import pytest

from detector.collect.collectors import offcpu
from detector.collect.rundir import RunDir


def test_decode_syscall_names():
    assert offcpu.decode_syscall(202) == "futex"
    assert offcpu.decode_syscall(7) == "poll"
    assert offcpu.decode_syscall(0) == "read"
    assert offcpu.decode_syscall(1) == "write"
    assert offcpu.decode_syscall(35) == "nanosleep"
    assert offcpu.decode_syscall(230) == "clock_nanosleep"
    assert offcpu.decode_syscall(271) == "ppoll"
    assert offcpu.decode_syscall(232) == "epoll_wait"


def test_decode_ioctl_variants():
    assert offcpu.decode_syscall(16, 0xC010462E) == "ioctl_nv"
    assert offcpu.decode_syscall(16, 0xC0406400) == "ioctl_drm"
    assert offcpu.decode_syscall(16, 0x1234) == "ioctl"
    assert offcpu.decode_syscall(16) == "ioctl"


def test_decode_specials():
    assert offcpu.decode_syscall(None) == "-"        # running
    assert offcpu.decode_syscall(-1) == "nosys"      # page fault / kernel work
    assert offcpu.decode_syscall(9999) == "sys_9999"


def test_is_nvidia_ioctl():
    assert offcpu.is_nvidia_ioctl(0xC010462E)
    assert not offcpu.is_nvidia_ioctl(0xC0406400)
    assert not offcpu.is_nvidia_ioctl(None)


def test_parse_syscall_line():
    assert offcpu.parse_syscall_line(
        "202 0x7f 0x1 0x0 0x0 0x0 0x0 0x7fff 0x7f8b") == "futex"
    assert offcpu.parse_syscall_line(
        "16 0x8 0xc010462e 0x7fff 0x0 0x0 0x0 0x7fff 0x7f") == "ioctl_nv"
    assert offcpu.parse_syscall_line("running") == "-"
    assert offcpu.parse_syscall_line("-1 0x7fff 0x7f") == "nosys"
    assert offcpu.parse_syscall_line("") == "nosys"


def _validate(path):
    assert os.path.exists(path)
    with open(path) as fh:
        lines = fh.read().splitlines()
    assert lines, f"{path} empty"
    header = lines[0].split(",")
    assert header[0] == "t_epoch"
    for line in lines[1:]:
        parts = line.split(",")
        assert len(parts) == 6, line
        float(parts[0])
        int(parts[1])
        assert len(parts[3]) == 1        # one-char state
        float(parts[0])
    return len(lines) - 1


def test_python_sampler_loop(tmp_path):
    stop = threading.Event()
    blocked = str(tmp_path / "threads_blocked.csv")
    cpu = str(tmp_path / "threads_cpu.csv")
    th = threading.Thread(
        target=offcpu.python_sampler_loop,
        args=(lambda: os.getpid(), blocked, cpu, 50.0, 200.0, stop, 0.4),
        daemon=True)
    th.start()
    th.join(timeout=8)
    stop.set()
    th.join(timeout=2)
    assert _validate(blocked) >= 1
    with open(blocked) as fh:
        tids = {int(l.split(",")[1]) for l in fh.read().splitlines()[1:]}
    assert os.getpid() in tids   # the main thread of this process


def test_snapshot_threads():
    rows = offcpu.snapshot_threads(os.getpid())
    assert rows
    assert any(r["tid"] == os.getpid() for r in rows)
    for r in rows:
        assert r["state"]
        assert r["comm"]


def test_native_helper(tmp_path):
    binary = offcpu.native_binary()
    if not binary:
        pytest.skip("no C compiler available")
    rd = RunDir(str(tmp_path))
    s = offcpu.OffCpuSampler(rd, pid=os.getpid(), hz=50.0, duration=0.4)
    s.start()
    time.sleep(1.0)
    s.stop()
    assert s.mode == "native"
    assert _validate(s.blocked_path) >= 1
    assert _validate(s.cpu_path) >= 0
    info = s.info()
    assert info["mode"] == "native"
    assert info["blocked_rows"] >= 1
