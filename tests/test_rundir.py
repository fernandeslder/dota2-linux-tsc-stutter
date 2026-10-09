"""Unit tests for the run-dir contract writers."""

import os

import pytest

from detector.collect.rundir import CsvWriter, LogWriter, RunDir


def test_rundir_create_and_events(tmp_path):
    rd = RunDir(str(tmp_path / "run1"))
    rd.create(label="x")
    assert os.path.isdir(rd.raw)
    assert os.path.isdir(rd.out)
    t = rd.append_event("run_start", "label=x")
    rd.append_event("mark,with,commas", 'a "quoted" detail')
    ev = rd.read_events()
    assert ev[0][1] == "run_start"
    assert ev[1][1] == "mark,with,commas"
    assert ev[1][2] == 'a "quoted" detail'
    assert ev[0][0] == pytest.approx(t, abs=1e-5)


def test_rundir_meta_roundtrip(tmp_path):
    rd = RunDir(str(tmp_path / "run2"))
    rd.create()
    rd.write_meta({"a": 1, "nested": {"b": 2}})
    rd.update_meta(c=3)
    m = rd.read_meta()
    assert m == {"a": 1, "nested": {"b": 2}, "c": 3}


def test_csv_writer_header_and_rows(tmp_path):
    p = str(tmp_path / "sig.csv")
    w = CsvWriter(p, ["a", "b", "c"])
    w.open()
    w.write(1.5, [1, 2.5, None])
    w.write(2.5, [3, 4, 5])
    w.close()
    with open(p) as fh:
        lines = fh.read().strip().splitlines()
    assert lines[0] == "t_epoch,a,b,c"
    assert lines[1].startswith("1.500000,1,2.5,")
    assert lines[2] == "2.500000,3,4,5"


def test_csv_writer_nan_and_bools(tmp_path):
    p = str(tmp_path / "sig2.csv")
    w = CsvWriter(p, ["x", "y"])
    w.open()
    w.write(0.0, [True, False])
    w.close()
    with open(p) as fh:
        assert fh.read().strip().splitlines()[-1] == "0.000000,1,0"


def test_log_writer_prefixes_epoch(tmp_path):
    p = str(tmp_path / "s.log")
    lw = LogWriter(p)
    lw.open()
    lw.write(1234.5, "hello\n")
    lw.close()
    with open(p) as fh:
        assert fh.read().strip() == "1234.500000 hello"


def test_collector_state(tmp_path):
    rd = RunDir(str(tmp_path / "run3"))
    rd.create()
    rd.write_collector_state({"pid": 1, "state": "running"})
    assert rd.read_collector_state()["pid"] == 1
    rd.clear_collector_state()
    assert rd.read_collector_state() == {}
