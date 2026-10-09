"""Arg-handling tests for `stutter preflight|launchopts|trial` (detector/trial/cli.py)."""

import json
import os

from detector.trial import cli
from detector.trial import steam as steammod


def test_no_args_prints_usage(capsys):
    assert cli.main([]) == 2
    assert "usage:" in capsys.readouterr().err


def test_help_returns_zero(capsys):
    assert cli.main(["--help"]) == 0


def test_unknown_command_is_error(capsys):
    assert cli.main(["bogus"]) == 2
    assert "unknown" in capsys.readouterr().err


def test_preflight_dispatch(monkeypatch):
    seen = {}

    def fake(argv):
        seen["argv"] = argv
        return 0

    monkeypatch.setattr(cli.preflight_mod, "main", fake)
    assert cli.main(["preflight", "--json"]) == 0
    assert seen["argv"] == ["--json"]


def test_trial_unknown_subcommand(capsys):
    assert cli.main(["trial", "bogus"]) == 2
    assert "unknown subcommand" in capsys.readouterr().err


def test_trial_dispatch_to_runner(monkeypatch):
    seen = {}

    def fake(argv):
        seen["argv"] = argv
        return 7

    monkeypatch.setattr(cli.runner_mod, "main", fake)
    assert cli.main(["trial", "run", "--minutes", "0.5"]) == 7
    assert seen["argv"] == ["run", "--minutes", "0.5"]


def test_launchopts_build_json(tmp_path, capsys):
    rc = cli.main(["launchopts", "--build", "--json", "--mangohud",
                   "--base", "-threads 8",
                   "--output-folder", str(tmp_path)])
    assert rc == 0
    built = json.loads(capsys.readouterr().out)
    assert "native" in built and "proton" in built
    assert "MANGOHUD_CONFIGFILE=" in built["native"]
    assert os.path.isfile(built["config_file"])


def test_launchopts_get_uses_account(monkeypatch, capsys):
    acc = steammod.SteamAccount(root="/x", userdata="/x/userdata/1", steamid="1",
                               vdf_path="/x/localconfig.vdf", launch_options="CUR")
    monkeypatch.setattr(steammod, "find_dota_config", lambda a, v: acc)
    monkeypatch.setattr(steammod, "get_launch_options", lambda a: a.launch_options)
    rc = cli.main(["launchopts", "--get"])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "CUR"


def test_launchopts_set_refused_exit_code(monkeypatch, capsys):
    acc = steammod.SteamAccount(root="/x", userdata="/x/userdata/1", steamid="1",
                               vdf_path="/x/localconfig.vdf")

    def boom(*a, **k):
        raise steammod.SteamConfigError("steam running")

    monkeypatch.setattr(steammod, "find_dota_config", lambda a, v: acc)
    monkeypatch.setattr(steammod, "set_launch_options", boom)
    assert cli.main(["launchopts", "--set", "X"]) == 3
    assert "steam running" in capsys.readouterr().err
