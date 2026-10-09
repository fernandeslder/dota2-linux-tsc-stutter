"""Quiesce state-machine tests (no real system mutation)."""

import argparse
import json
import os

import pytest

from detector.collect import quiesce


def _args(**kw):
    base = {"run_dir": "", "state": "", "rewarm": False, "pause_containers": False,
            "dry_run": False}
    base.update(kw)
    return argparse.Namespace(**base)


def test_state_default_location_under_runs():
    assert os.path.basename(quiesce.STATE_PATH) == ".quiesce-state.json"
    assert os.path.basename(os.path.dirname(quiesce.STATE_PATH)) == "runs"


def test_write_and_status_roundtrip(tmp_path, monkeypatch, capsys):
    st = str(tmp_path / "state.json")
    monkeypatch.setattr(quiesce, "STATE_PATH", st)
    state = {"version": 1, "restored": False, "t_on_epoch": 1.0,
             "ollama": {"action": "stopped_service", "system_active": True},
             "containers": []}
    quiesce._write_state(state, None, state_path=st)
    assert quiesce.quiesce_status(_args(state=st)) == 0
    out = capsys.readouterr().out
    assert '"active": true' in out


def test_off_without_state_is_noop(tmp_path, capsys):
    st = str(tmp_path / "missing.json")
    assert quiesce.quiesce_off(_args(state=st)) == 0
    assert "not on" in capsys.readouterr().out


def test_on_is_idempotent_when_already_active(tmp_path, monkeypatch, capsys):
    st = str(tmp_path / "state.json")
    monkeypatch.setattr(quiesce, "STATE_PATH", st)
    with open(st, "w") as fh:
        json.dump({"restored": False, "ollama": {}}, fh)
    # must NOT probe or touch the system; returns early
    assert quiesce.quiesce_on(_args()) == 0
    assert "already on" in capsys.readouterr().out


def test_off_restores_only_recorded_state(tmp_path, capsys):
    st = str(tmp_path / "state.json")
    state = {
        "version": 1, "restored": False,
        "ollama": {"installed": False, "action": "none"},
        "containers": [], "containers_action": "recorded",
    }
    with open(st, "w") as fh:
        json.dump(state, fh)
    assert quiesce.quiesce_off(_args(state=st)) == 0
    out = capsys.readouterr().out
    assert "restored" in out
    with open(st) as fh:
        assert json.load(fh)["restored"] is True
