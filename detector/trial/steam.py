"""Locate and safely edit Dota 2's Steam ``LaunchOptions``.

Facts about this machine (verified 2026-10):

* Steam ships **three** ``userdata/<id>/config/localconfig.vdf`` files; only one
  of them (account ``STEAMID``) actually carries a Dota ``570`` ``LaunchOptions``
  entry.  So we never assume an account: we enumerate every candidate and pick
  the one that has a ``570`` app node, preferring one that already sets
  ``LaunchOptions`` and then the most-recently-logged-in account.
* Dota 2's appid is ``570``; the key lives at
  ``<root>/Software/Valve/Steam/apps/570/LaunchOptions`` inside a wrapper that may
  or may not be named ``UserLocalConfigStore`` (we match on a path *suffix*).
* Steam rewrites ``localconfig.vdf`` on quit, so a write only sticks if Steam is
  **not running**.  Every write therefore (a) refuses unless Steam is down or
  ``--force`` is given, (b) backs the file up under ``ledger/backups/`` first,
  (c) writes atomically, and (d) re-reads to verify.

Writes touch only the ``LaunchOptions`` token/line -- see :mod:`detector.trial.vdf`.
"""

from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass, field
from typing import List, Optional

from ..collect import util
from . import vdf as vdfmod
from .vdf import VdfDocument

DOTA_APPID = "570"

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LEDGER_BACKUPS = os.path.join(REPO_ROOT, "ledger", "backups")

_STEAM_SUFFIX = ["Software", "Valve", "Steam", "apps", DOTA_APPID]


class SteamConfigError(RuntimeError):
    """No usable Dota 2 LaunchOptions file could be located."""


@dataclass
class SteamAccount:
    root: str
    userdata: str
    steamid: str
    vdf_path: str
    launch_options: Optional[str] = None
    has_app: bool = False

    @property
    def app_suffix(self) -> List[str]:
        return list(_STEAM_SUFFIX)

    @property
    def opt_suffix(self) -> List[str]:
        return list(_STEAM_SUFFIX) + ["LaunchOptions"]


# ---------------------------------------------------------------------------
# discovery
# ---------------------------------------------------------------------------

def steam_roots() -> List[str]:
    """Candidate Steam install roots, de-duplicated and only those that exist."""
    home = os.path.expanduser("~")
    cands = [
        os.environ.get("STEAM_DIR", ""),
        os.path.join(home, ".local", "share", "Steam"),
        os.path.join(home, ".steam", "steam"),
        os.path.join(home, ".steam", "root"),
        os.path.join(home, ".var", "app", "com.valvesoftware.Steam", "data", "Steam"),
    ]
    out: List[str] = []
    for c in cands:
        if c and os.path.isdir(c):
            real = os.path.realpath(c)
            if real not in out:
                out.append(real)
    return out


def userdata_dirs(root: str) -> List[str]:
    ud = os.path.join(root, "userdata")
    if not os.path.isdir(ud):
        return []
    return sorted(os.path.join(ud, d) for d in os.listdir(ud)
                  if os.path.isfile(os.path.join(ud, d, "config", "localconfig.vdf")))


def candidate_configs() -> List[SteamAccount]:
    seen = set()
    out = []
    for root in steam_roots():
        for ud in userdata_dirs(root):
            vdf = os.path.join(ud, "config", "localconfig.vdf")
            rp = os.path.realpath(vdf)
            if rp in seen:
                continue
            seen.add(rp)
            out.append(SteamAccount(root=root, userdata=ud,
                                    steamid=os.path.basename(ud), vdf_path=vdf))
    return out


def most_recent_steamid(root: str) -> str:
    """steamid with ``MostRecent "1"`` in ``<root>/config/loginusers.vdf`` (or '')."""
    path = os.path.join(root, "config", "loginusers.vdf")
    if not os.path.isfile(path):
        return ""
    try:
        doc = VdfDocument.load(path)
    except (OSError, vdfmod.VdfError):
        return ""
    for p, node in doc.iter_nodes():
        if node.get("MostRecent") == "1":
            return p[-1]
    return ""


def _load_launch_options(acc: SteamAccount) -> None:
    try:
        doc = VdfDocument.load(acc.vdf_path)
    except (OSError, vdfmod.VdfError):
        return
    acc.has_app = doc.find_path_by_suffix(acc.app_suffix) is not None
    acc.launch_options = doc.get_suffix(acc.opt_suffix)


def find_dota_config(account: Optional[str] = None, vdf_path: Optional[str] = None
                     ) -> SteamAccount:
    """Pick the account whose localconfig.vdf holds Dota 2's launch options."""
    if vdf_path:
        vdf_path = os.path.abspath(vdf_path)
        acc = SteamAccount(root=os.path.dirname(os.path.dirname(os.path.dirname(vdf_path))),
                           userdata=os.path.dirname(os.path.dirname(vdf_path)),
                           steamid=os.path.basename(os.path.dirname(os.path.dirname(vdf_path))),
                           vdf_path=vdf_path)
        _load_launch_options(acc)
        if not acc.has_app:
            raise SteamConfigError(f"no appid {DOTA_APPID} node in {vdf_path}")
        return acc

    cands = candidate_configs()
    for c in cands:
        _load_launch_options(c)
    matching = [c for c in cands if account is None or c.steamid == str(account)]
    if not matching:
        raise SteamConfigError(
            f"no localconfig.vdf found for account {account!r} (searched "
            f"{len(cands)} userdata dirs under {steam_roots()})")
    with_app = [c for c in matching if c.has_app]
    pool = with_app or matching
    # prefer a config that already sets LaunchOptions, then MostRecent, then newest.
    def rank(c: SteamAccount):
        return (
            0 if c.launch_options is not None else 1,
            0 if most_recent_steamid(c.root) == c.steamid else 1,
            -os.path.getmtime(c.vdf_path),
        )
    pool.sort(key=rank)
    return pool[0]


# ---------------------------------------------------------------------------
# read / write
# ---------------------------------------------------------------------------

def get_launch_options(acc: SteamAccount) -> Optional[str]:
    return VdfDocument.load(acc.vdf_path).get_suffix(acc.opt_suffix)


def backup(acc: SteamAccount, reason: str = "") -> str:
    """Copy the config to ``ledger/backups/`` with a timestamp; return the path."""
    os.makedirs(LEDGER_BACKUPS, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    micro = f"{time.time():.6f}".split(".")[1]
    name = f"localconfig.vdf.{acc.steamid}.{stamp}.{micro}.bak"
    dst = os.path.join(LEDGER_BACKUPS, name)
    shutil.copy2(acc.vdf_path, dst)
    if reason:
        with open(dst + ".meta", "w") as fh:
            fh.write(f"reason: {reason}\n"
                     f"source: {acc.vdf_path}\n"
                     f"steamid: {acc.steamid}\n"
                     f"t_epoch: {util.epoch():.6f}\n")
    return dst


def _atomic_write(path: str, data: bytes) -> None:
    st = os.stat(path)
    tmp = path + ".stutter-tmp"
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.chmod(tmp, st.st_mode & 0o777)
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Steam process state
# ---------------------------------------------------------------------------

def steam_pids() -> List[int]:
    """PIDs of the Steam client / its web helper (empty when Steam is not running)."""
    pids = []
    try:
        entries = os.listdir("/proc")
    except OSError:
        return pids
    for entry in entries:
        if not entry.isdigit():
            continue
        pid = int(entry)
        try:
            with open(f"/proc/{pid}/comm") as fh:
                comm = fh.read().strip()
        except OSError:
            continue
        cmd = util.proc_cmdline(pid)
        if comm == "steam" or comm == "steamwebhelper" \
                or "/ubuntu12_32/steam" in cmd or "steamwebhelper" in cmd:
            pids.append(pid)
    return pids


def is_steam_running() -> bool:
    return bool(steam_pids())


def steam_shutdown(timeout: float = 60.0, force: bool = False) -> dict:
    """Ask Steam to quit and wait for it to actually exit.

    Uses the documented ``steam -shutdown`` first; falls back to SIGTERM of the
    client pid.  With ``force`` a SIGKILL is the last resort.  Never touches a
    never-started Steam.
    """
    pids = steam_pids()
    if not pids:
        return {"was_running": False, "stopped": True, "method": "none", "remaining": []}
    method = ""
    if util.have("steam"):
        rc, _out, _err = util.run_capture(["steam", "-shutdown"], timeout=15)
        method = f"steam -shutdown (rc={rc})"
    if not method:
        for pid in pids:
            try:
                os.kill(pid, 15)
            except OSError:
                pass
        method = "SIGTERM"
    deadline = time.monotonic() + max(0.0, timeout)
    while time.monotonic() < deadline:
        if not steam_pids():
            return {"was_running": True, "stopped": True, "method": method, "remaining": []}
        time.sleep(0.5)
    if force:
        for pid in steam_pids():
            try:
                os.kill(pid, 9)
            except OSError:
                pass
        time.sleep(1.0)
        method += "+SIGKILL"
    remaining = steam_pids()
    return {"was_running": True, "stopped": not remaining, "method": method,
            "remaining": remaining}


# ---------------------------------------------------------------------------
# high-level operations
# ---------------------------------------------------------------------------

def set_launch_options(acc: SteamAccount, value: str, *, force: bool = False,
                       dry_run: bool = False) -> dict:
    """Set Dota's LaunchOptions. Refuses while Steam runs unless *force*."""
    running = is_steam_running()
    if running and not force:
        raise SteamConfigError(
            "Steam is running: it will overwrite localconfig.vdf on quit. "
            "Run `stutter launchopts --steam-shutdown` (or pass --force).")
    before = get_launch_options(acc)
    if dry_run:
        return {"ok": True, "dry_run": True, "steam_running": running,
                "before": before, "after": value, "backup": None}
    bpath = backup(acc, reason="set LaunchOptions")
    doc = VdfDocument.load(acc.vdf_path)
    doc.set_suffix(acc.opt_suffix, value)
    _atomic_write(acc.vdf_path, doc.dumps())
    after = VdfDocument.load(acc.vdf_path).get_suffix(acc.opt_suffix)
    ok = after == value
    return {"ok": ok, "dry_run": False, "steam_running": running,
            "before": before, "after": after, "backup": bpath}


def restore_launch_options(acc: SteamAccount, backup_path: str, *, force: bool = False
                           ) -> dict:
    """Restore the whole config file from a backup (with a fresh pre-restore backup)."""
    if not os.path.isfile(backup_path):
        raise SteamConfigError(f"backup not found: {backup_path}")
    running = is_steam_running()
    if running and not force:
        raise SteamConfigError("Steam is running; refusing to overwrite its config "
                               "(use --force to override).")
    # sanity: the backup must parse and contain the app node
    try:
        src = VdfDocument.load(backup_path)
    except (OSError, vdfmod.VdfError) as exc:
        raise SteamConfigError(f"backup is not a readable VDF: {exc}")
    if src.find_path_by_suffix(acc.app_suffix) is None:
        raise SteamConfigError(f"backup has no appid {DOTA_APPID} node: {backup_path}")
    pre = backup(acc, reason=f"pre-restore (restoring {os.path.basename(backup_path)})")
    shutil.copy2(backup_path, acc.vdf_path)
    after = get_launch_options(acc)
    return {"ok": True, "restored_from": backup_path, "pre_restore_backup": pre,
            "after": after, "steam_running": running}
