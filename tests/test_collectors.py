"""Sampler-level tests: every sampler must produce a row of the right width."""

import ctypes
import os
import sys

import pytest

from detector.collect.collectors import hwmon, nvidia, procfs, subproc, threads


def _check(sampler, n=2):
    sampler.prepare()
    for _ in range(n):
        row = sampler.sample(1_700_000_000.0)
        assert row is not None
        assert len(row) == len(sampler.columns), (
            f"{sampler.name}: row {len(row)} != cols {len(sampler.columns)}")
    sampler.teardown()


def test_cpu_and_freq():
    _check(procfs.CpuUtil())
    _check(procfs.CpuFreq())


def test_sys_mem_disk_net():
    _check(procfs.SysStats())
    _check(procfs.MemStats())
    _check(procfs.DiskStats())
    _check(procfs.NetDev())


def test_hwmon():
    _check(hwmon.HwmonSampler())


def test_threads_current_process():
    s = threads.ThreadSampler(pid=os.getpid())
    s.prepare()
    row = s.sample(1_700_000_000.0)
    assert len(row) == len(s.columns)
    assert row[1] >= 1  # nthreads


@pytest.mark.skipif(not nvidia.available(), reason="NVML not available")
def test_gpu_nvml():
    _check(nvidia.GpuSampler(), n=3)


def test_find_game_pid_comm_override(monkeypatch):
    """STUTTER_GAME_COMM lets the collector target a non-Dota app by name."""
    libc = ctypes.CDLL(None, use_errno=True)
    with open("/proc/self/comm") as fh:
        original = fh.read().strip()
    assert libc.prctl(15, ctypes.c_char_p(b"stuttertst"), 0, 0, 0) == 0  # PR_SET_NAME
    try:
        monkeypatch.setenv("STUTTER_GAME_COMM", "stuttertst")
        assert threads.find_game_pid() == os.getpid()   # exact-comm match
    finally:
        libc.prctl(15, ctypes.c_char_p(original.encode()), 0, 0, 0)
    # an unknown override must not invent a pid
    monkeypatch.setenv("STUTTER_GAME_COMM", "definitely-not-a-real-comm-xyz")
    assert threads.find_game_pid() != os.getpid()


def test_ss_parser():
    text = (
        "State Recv-Q Send-Q Local Address:Port Peer Address:Port\n"
        "ESTAB 0 0 192.0.2.20:52228 198.51.100.11:443\n"
        "\tcubic wscale:8,10 rto:230 rtt:29.085/0.531 ato:40 cwnd:10 "
        "bytes_sent:29000 retrans:2/70 bytes_retrans:100\n"
        "ESTAB 0 0 127.0.0.1:27015 127.0.0.1:40000\n"
        "\tcubic rtt:0.5/0.1 cwnd:20 retrans:0/9\n")
    agg = subproc.parse_ss_tin(text)
    assert agg["n_estab"] == 2
    assert agg["retrans_segs"] == 2
    assert agg["n_sock_retrans"] == 1
    assert agg["rtt_max_ms"] == 29.085
    assert agg["game_socks"] == 1  # port 27015 is in the Dota range


def test_is_game_port():
    assert subproc._is_game_port("1.2.3.4:27015")
    assert subproc._is_game_port("1.2.3.4:27050")
    assert not subproc._is_game_port("1.2.3.4:443")
    assert not subproc._is_game_port("garbage")


def test_pw_top_parser():
    text = (
        "S  ID QUANT RATE WAIT BUSY W/Q B/Q ERR FORMAT NAME\n"
        "C  29   0    0    ---  ---  --- ---  0  \n"
        "I  41 1024 48000 0.1 0.05 0.1 0.0  3  \n"
    )
    total, nodes, busy = subproc._parse_pw_top(text)
    assert total == 3
    assert nodes == 2
    assert busy is not None
