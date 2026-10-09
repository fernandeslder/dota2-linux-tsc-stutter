"""Unit tests for Steam LaunchOptions handling (detector/trial/steam.py).

Everything runs against a synthetic Steam tree in tmp_path; the real
``~/.local/share/Steam`` and ``ledger/backups`` are never touched.
"""

import os

import pytest

from detector.trial import steam
from detector.trial.vdf import quote


def _localconfig(launch=None, with_app=True):
    launch_line = f'\t\t\t\t\t\t"LaunchOptions"\t\t{quote(launch)}\n' if launch is not None else ""
    app = (f'\t\t\t\t\t"570"\n\t\t\t\t\t{{\n'
           f'\t\t\t\t\t\t"LastPlayed"\t\t"1790896190"\n{launch_line}'
           f'\t\t\t\t\t}}\n') if with_app else ""
    return ('"UserLocalConfigStore"\n{\n'
            '\t"Software"\n\t{\n\t\t"Valve"\n\t\t{\n\t\t\t"Steam"\n\t\t\t{\n'
            '\t\t\t\t"apps"\n\t\t\t\t{\n' + app +
            '\t\t\t\t}\n\t\t\t}\n\t\t}\n\t}\n}\n')


def _mk_account(root, steamid, launch=None, with_app=True):
    cfg = os.path.join(root, "userdata", steamid, "config")
    os.makedirs(cfg, exist_ok=True)
    path = os.path.join(cfg, "localconfig.vdf")
    with open(path, "w") as fh:
        fh.write(_localconfig(launch, with_app))
    return path


def _loginusers(root, recent_id):
    cfg = os.path.join(root, "config")
    os.makedirs(cfg, exist_ok=True)
    with open(os.path.join(cfg, "loginusers.vdf"), "w") as fh:
        fh.write(f'"users"\n{{\n\t"{recent_id}"\n\t{{\n\t\t"MostRecent"\t\t"1"\n\t}}\n'
                 f'\t"STEAMID64"\n\t{{\n\t\t"MostRecent"\t\t"0"\n\t}}\n}}\n')


@pytest.fixture
def steam_env(tmp_path, monkeypatch):
    root = tmp_path / "Steam"
    backups = tmp_path / "backups"
    monkeypatch.setattr(steam, "steam_roots", lambda: [str(root)])
    monkeypatch.setattr(steam, "LEDGER_BACKUPS", str(backups))
    monkeypatch.setattr(steam, "steam_pids", lambda: [])
    return root


def test_most_recent_steamid(steam_env):
    _loginusers(str(steam_env), "STEAMID64")
    assert steam.most_recent_steamid(str(steam_env)) == "STEAMID64"


def test_find_prefers_account_with_launch_options(steam_env, monkeypatch):
    _mk_account(str(steam_env), "111", launch=None)
    _mk_account(str(steam_env), "222", launch="-vulkan -threads 8")
    _loginusers(str(steam_env), "111")  # most-recent but no LaunchOptions
    acc = steam.find_dota_config()
    assert acc.steamid == "222"
    assert steam.get_launch_options(acc) == "-vulkan -threads 8"


def test_find_by_explicit_account(steam_env):
    _mk_account(str(steam_env), "111", launch="A")
    _mk_account(str(steam_env), "222", launch="B")
    acc = steam.find_dota_config(account="111")
    assert acc.steamid == "111"
    assert steam.get_launch_options(acc) == "A"


def test_find_by_explicit_vdf(steam_env):
    p = _mk_account(str(steam_env), "111", launch="A")
    acc = steam.find_dota_config(vdf_path=p)
    assert acc.vdf_path == os.path.abspath(p)
    assert steam.get_launch_options(acc) == "A"


def test_find_errors_when_missing(steam_env):
    with pytest.raises(steam.SteamConfigError):
        steam.find_dota_config()


def test_set_writes_verifies_and_backs_up(steam_env):
    _mk_account(str(steam_env), "222", launch="OLD %command% -vulkan")
    acc = steam.find_dota_config()
    res = steam.set_launch_options(acc, "NEW %command% -threads 8")
    assert res["ok"] is True
    assert res["before"] == "OLD %command% -vulkan"
    assert res["after"] == "NEW %command% -threads 8"
    assert steam.get_launch_options(acc) == "NEW %command% -threads 8"
    assert os.path.isfile(res["backup"])
    # the rest of the file is intact and still parses
    from detector.trial.vdf import VdfDocument
    doc = VdfDocument.load(acc.vdf_path)
    assert doc.get_suffix(["Software", "Valve", "Steam", "apps", "570", "LastPlayed"]) == "1790896190"


def test_set_refuses_when_steam_running(steam_env, monkeypatch):
    _mk_account(str(steam_env), "222", launch="OLD")
    monkeypatch.setattr(steam, "steam_pids", lambda: [4242])
    acc = steam.find_dota_config()
    with pytest.raises(steam.SteamConfigError):
        steam.set_launch_options(acc, "NEW")
    # unchanged
    assert steam.get_launch_options(acc) == "OLD"
    # --force is allowed
    res = steam.set_launch_options(acc, "NEW", force=True)
    assert res["ok"] and res["steam_running"] is True


def test_set_dry_run_touches_nothing(steam_env):
    _mk_account(str(steam_env), "222", launch="OLD")
    acc = steam.find_dota_config()
    res = steam.set_launch_options(acc, "NEW", dry_run=True)
    assert res["dry_run"] is True
    assert steam.get_launch_options(acc) == "OLD"


def test_restore_from_backup(steam_env):
    _mk_account(str(steam_env), "222", launch="ORIGINAL")
    acc = steam.find_dota_config()
    bak = steam.backup(acc, reason="test")
    steam.set_launch_options(acc, "CHANGED")
    assert steam.get_launch_options(acc) == "CHANGED"
    res = steam.restore_launch_options(acc, bak)
    assert steam.get_launch_options(acc) == "ORIGINAL"
    assert os.path.isfile(res["pre_restore_backup"])


def test_restore_rejects_non_vdf(steam_env, tmp_path):
    _mk_account(str(steam_env), "222", launch="ORIGINAL")
    acc = steam.find_dota_config()
    junk = tmp_path / "junk.bak"
    junk.write_text("not a vdf at all")
    with pytest.raises(steam.SteamConfigError):
        steam.restore_launch_options(acc, str(junk))


def test_steam_shutdown_noop_when_not_running(steam_env):
    res = steam.steam_shutdown(timeout=1)
    assert res["was_running"] is False and res["stopped"] is True
