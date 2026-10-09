"""Focused tests for the trial runner helpers (detector/trial/runner.py)."""

import json
import os
import time

import pytest

from detector.trial import runner


def test_find_processes_self_excluded_and_missing():
    assert runner.find_processes("definitely-not-a-real-proc-xyz") == []
    # our own python is running but is excluded by pid; the name won't match anyway
    assert isinstance(runner.find_processes("python3"), list)


def test_frame_counter_incremental(tmp_path):
    p = tmp_path / "frametimes.csv"
    p.write_text("t_epoch,frametime_ms\n1,7\n2,7\n")
    fc = runner.FrameCounter(str(p))
    assert fc.poll() == 2
    with open(p, "a") as fh:
        fh.write("3,7\n4,7\n5,7\n")
    assert fc.poll() == 5
    assert fc.frames == 5


def test_frame_counter_handles_missing_file(tmp_path):
    fc = runner.FrameCounter(str(tmp_path / "nope.csv"))
    assert fc.poll() == 0


def test_wait_for_game_times_out(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "find_processes", lambda name: [])
    with pytest.raises(runner.TrialAbort) as ei:
        runner._wait_for_game("nope", str(tmp_path), deadline=time.time() - 1, timeout=0)
    assert "timeout" in ei.value.reason


def test_wait_for_game_returns_when_up(tmp_path, monkeypatch):
    p = tmp_path / "frametimes.csv"
    p.write_text("t_epoch,frametime_ms\n" + "".join(f"{i},7\n" for i in range(10)))
    monkeypatch.setattr(runner, "find_processes", lambda name: [4242])
    pids, frames = runner._wait_for_game("x", str(tmp_path), deadline=time.time() + 5, timeout=5)
    assert pids == [4242] and frames >= runner.MIN_FRAMES


def test_record_window_aborts_on_process_death(tmp_path, monkeypatch):
    (tmp_path / "frametimes.csv").write_text("t_epoch,frametime_ms\n" + "1,7\n" * 20)
    monkeypatch.setattr(runner, "find_processes", lambda name: [])
    with pytest.raises(runner.TrialAbort) as ei:
        runner._record_window(str(tmp_path), "game", minutes=5)
    assert "died" in ei.value.reason


def test_record_window_aborts_on_frame_stall(tmp_path, monkeypatch):
    (tmp_path / "frametimes.csv").write_text("t_epoch,frametime_ms\n" + "1,7\n" * 20)
    monkeypatch.setattr(runner, "find_processes", lambda name: [4242])
    monkeypatch.setattr(runner, "FRAMES_STALL_S", -1.0)  # already exceeded
    with pytest.raises(runner.TrialAbort) as ei:
        runner._record_window(str(tmp_path), "game", minutes=5)
    assert "frames stopped" in ei.value.reason


def test_cleanup_is_clean_with_no_state(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(runner.collect_cli, "RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setattr(runner.quiesce_mod, "STATE_PATH", str(tmp_path / "runs" / ".quiesce-state.json"))
    rc = runner.cleanup()
    out = capsys.readouterr().out
    assert rc == 0
    assert "clean" in out


def test_scan_argv_matches_exact_token_not_substring():
    import subprocess
    # a shell whose command *string mentions* the marker must NOT be matched
    proc = subprocess.Popen(
        ["python3", "-c", "import time; time.sleep(15)  # detector.collect.supervisor"])
    try:
        time.sleep(0.3)
        assert proc.pid not in runner.scan_argv("detector.collect.supervisor")
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_is_ours_scopes_to_repo():
    # our own pytest process runs with cwd == repo root
    assert runner._is_ours(os.getpid()) is True
    assert runner._under_repo(runner.REPO_ROOT) is True
    assert runner._under_repo("/tmp") is False


def test_ns_and_mark_helpers(tmp_path):
    # _ns builds an argparse namespace with the given fields
    ns = runner._ns(a=1, b=2)
    assert ns.a == 1 and ns.b == 2
