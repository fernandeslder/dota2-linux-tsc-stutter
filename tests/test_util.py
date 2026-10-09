"""Unit tests for the pure-python parsing / helper layer."""

import os

import pytest

from detector.collect import util


def test_parse_cpu_list():
    assert util.parse_cpu_list("0-7,16-23") == set(range(0, 8)) | set(range(16, 24))
    assert util.parse_cpu_list("3") == {3}
    assert util.parse_cpu_list("") == set()
    assert util.parse_cpu_list(" 1 , 2 ") == {1, 2}


def test_ccd_map_matches_l3_groups():
    m = util.ccd_map_for_cpus()
    # On this machine L3 groups are {0-15} and {16-31}; the map must be consistent.
    assert m.get(0) == m.get(15)
    if 16 in m:
        assert m.get(16) != m.get(0)


def test_parse_proc_stat_minimal():
    text = (
        "cpu  100 0 50 1000 10 0 5 0 0 0\n"
        "cpu0 50 0 25 500 5 0 2 0 0 0\n"
        "cpu1 50 0 25 500 5 0 3 0 0 0\n"
        "ctxt 12345\n"
        "btime 1700000000\n"
        "processes 777\n"
        "procs_running 3\n"
        "procs_blocked 1\n"
        "intr 99999 1 2 3\n"
    )
    per_cpu, agg, extras = util.parse_proc_stat(text)
    assert [i for i, _ in per_cpu] == [0, 1]
    assert agg[0] == 100
    assert extras["ctxt"] == 12345
    assert extras["procs_running"] == 3
    assert extras["intr"] == 99999


def test_parse_pressure():
    text = "some avg10=0.42 avg60=0.27 avg300=0.15 total=328064220\nfull avg10=0.00 avg60=0.00 avg300=0.00 total=0\n"
    p = util.parse_pressure(text)
    assert p["some_avg10"] == 0.42
    assert p["some_total"] == 328064220
    assert p["full_avg10"] == 0.0


def test_parse_meminfo_and_vmstat():
    mi = util.parse_meminfo("MemTotal:       32521804 kB\nSwapTotal: 100 kB\nDirty: 0 kB\n")
    assert mi["MemTotal"] == 32521804 * 1024
    assert mi["Dirty"] == 0
    vm = util.parse_vmstat("pgmajfault 5\npswpout 7\n")
    assert vm["pgmajfault"] == 5 and vm["pswpout"] == 7


def test_parse_diskstats_and_netdev():
    ds = util.parse_diskstats(
        " 259 0 nvme1n1 541 0 83784 145 0 0 0 0 0 34 145 0 0 0 0 0 0\n")
    assert "nvme1n1" in ds
    assert ds["nvme1n1"]["reads"] == 541
    assert ds["nvme1n1"]["io_ms"] == 34
    nd = util.parse_netdev(
        "Inter-|   Receive\n face |bytes\n    lo: 100 2 0 0 0 0 0 0 100 2 0 0 0 0 0 0\n")
    assert nd["lo"]["rx_bytes"] == 100


def test_parse_pid_stat_comm_with_spaces():
    text = "123 (dota2 (test)) S 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 " \
           "21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39\n"
    # rest index: state=0, then ppid=1.. ; utime is overall field 14 -> rest[11]
    d = util.parse_pid_stat(text)
    assert d is not None
    assert d["comm"] == "dota2 (test)"
    assert d["state"] == "S"
    assert d["utime"] == 11
    assert d["stime"] == 12


def test_birthtime_available_on_repo_fs():
    here = os.path.abspath(__file__)
    bt = util.birthtime_ns(here)
    # btrfs/ext4 support statx btime; if a filesystem doesn't, the API returns None
    assert bt is None or bt > 1_500_000_000_000_000_000


def test_file_times_ns():
    here = os.path.abspath(__file__)
    ft = util.file_times_ns(here)
    assert ft["size"] > 0
    assert ft["mtime"] > 0
