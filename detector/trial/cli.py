"""CLI for the trial tooling: ``stutter preflight``, ``stutter launchopts``, ``stutter trial``.

``bin/stutter`` routes ``preflight`` and ``launchopts`` here directly, and routes
the ``trial`` group (``trial run`` / ``trial cleanup``) here too.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Optional

from . import launchopts as lo
from . import preflight as preflight_mod
from . import runner as runner_mod
from . import steam as steammod

REPO_ROOT = runner_mod.REPO_ROOT


# ---------------------------------------------------------------------------
# launchopts
# ---------------------------------------------------------------------------

def _resolve_account(args) -> steammod.SteamAccount:
    return steammod.find_dota_config(getattr(args, "account", None),
                                     getattr(args, "vdf", None))


def _print_build(args) -> int:
    out_folder = args.output_folder or os.path.join(REPO_ROOT, "runs", "mangohud-manual")
    os.makedirs(out_folder, exist_ok=True)
    built = lo.build(args.base or "", mangohud_on=args.mangohud,
                     output_folder=out_folder,
                     config_file=args.config_file or "",
                     config_mode=args.config_mode,
                     native=not args.proton_only, proton=not args.native_only)
    if args.json:
        print(json.dumps(built, indent=2, default=str))
        return 0
    print(f"# MangoHud config: {built.get('config_file') or '(inline)'}")
    print(f"# output_folder:   {out_folder}")
    print(f"# base (under test): {args.base or '(none)'}")
    if "native" in built:
        print(f"native:  {built['native']}")
    if "proton" in built:
        print(f"proton:  {built['proton']}")
    if "wrapper" in built:
        print(f"wrapper: {built['wrapper']}")
    return 0


def cmd_launchopts(args) -> int:
    if args.build:
        return _print_build(args)

    if args.steam_shutdown:
        res = steammod.steam_shutdown(timeout=args.steam_timeout, force=args.force)
        print(f"steam shutdown: {json.dumps(res, default=str)}", file=sys.stderr)
        if not res["stopped"]:
            print("steam did not stop; use --force or quit it manually", file=sys.stderr)
            return 1

    try:
        acc = _resolve_account(args)
    except steammod.SteamConfigError as exc:
        print(f"launchopts: {exc}", file=sys.stderr)
        return 1

    if args.backup:
        path = steammod.backup(acc, reason="explicit --backup")
        print(f"backup: {path}")

    if args.restore:
        try:
            res = steammod.restore_launch_options(acc, args.restore, force=args.force)
        except steammod.SteamConfigError as exc:
            print(f"launchopts: {exc}", file=sys.stderr)
            return 1
        print(f"restored from {res['restored_from']}; LaunchOptions now "
              f"{res['after']!r} (pre-restore backup {res['pre_restore_backup']})")
        return 0

    if args.set is not None:
        try:
            res = steammod.set_launch_options(acc, args.set, force=args.force,
                                              dry_run=args.dry_run)
        except steammod.SteamConfigError as exc:
            print(f"launchopts: {exc}", file=sys.stderr)
            return 3
        if not res["ok"]:
            print(f"launchopts: verification FAILED (config now {res['after']!r})",
                  file=sys.stderr)
            return 1
        tag = "would set" if res["dry_run"] else "set"
        print(f"{tag} LaunchOptions (steamid {acc.steamid})")
        print(f"  before: {res['before']!r}")
        print(f"  after:  {res['after']!r}")
        if res.get("backup"):
            print(f"  backup: {res['backup']}")
        return 0

    # default / --get
    value = steammod.get_launch_options(acc)
    if args.json:
        print(json.dumps({"steamid": acc.steamid, "vdf": acc.vdf_path,
                          "launch_options": value}, indent=2))
    else:
        print(f"steamid={acc.steamid} vdf={acc.vdf_path}", file=sys.stderr)
        print(value if value is not None else "")
    return 0


def build_launchopts_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="stutter launchopts",
                                 description="read/write Dota 2 (570) Steam LaunchOptions")
    ap.add_argument("--get", action="store_true", help="print the current LaunchOptions")
    ap.add_argument("--set", default=None, help="write this LaunchOptions string")
    ap.add_argument("--restore", default=None, metavar="BACKUP",
                    help="restore localconfig.vdf from a ledger/backups file")
    ap.add_argument("--backup", action="store_true", help="back up localconfig.vdf now")
    ap.add_argument("--force", action="store_true",
                    help="write even if Steam is running (it may overwrite on quit)")
    ap.add_argument("--dry-run", action="store_true", help="report the change without writing")
    ap.add_argument("--steam-shutdown", action="store_true",
                    help="quit Steam first (required for writes to stick)")
    ap.add_argument("--steam-timeout", type=float, default=60.0)
    ap.add_argument("--account", default=None, help="Steam account id (userdata dir name)")
    ap.add_argument("--vdf", default=None, help="explicit localconfig.vdf path")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--build", action="store_true",
                    help="build a launch-option string instead of reading/writing")
    ap.add_argument("--base", default="", help="options under test (e.g. '-threads 8 +fps_max 144')")
    ap.add_argument("--mangohud", "-m", action="store_true",
                    help="include MangoHud instrumentation in --build output")
    ap.add_argument("--output-folder", default=None,
                    help="MangoHud output_folder for --build (default runs/mangohud-manual)")
    ap.add_argument("--config-file", default=None)
    ap.add_argument("--config-mode", choices=["file", "inline"], default="file")
    ap.add_argument("--native-only", action="store_true", help="--build: only the native string")
    ap.add_argument("--proton-only", action="store_true", help="--build: only the Proton string")
    ap.set_defaults(func=cmd_launchopts)
    return ap


# ---------------------------------------------------------------------------
# top-level dispatch
# ---------------------------------------------------------------------------

TRIAL_SUBCOMMANDS = {"run", "cleanup"}


def main(argv: Optional[list] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print("usage: stutter <preflight|launchopts|trial> ...\n"
              "  preflight [--json]\n"
              "  launchopts [--get|--set S|--restore F|--build --base S [--mangohud]]\n"
              "  trial run|cleanup ...", file=sys.stderr)
        return 0 if argv else 2
    cmd, rest = argv[0], argv[1:]
    if cmd == "preflight":
        return preflight_mod.main(rest)
    if cmd == "launchopts":
        return cmd_launchopts(build_launchopts_parser().parse_args(rest))
    if cmd == "trial":
        if not rest or rest[0] in ("-h", "--help", "help"):
            runner_mod.build_parser().print_help()
            return 0
        if rest[0] in TRIAL_SUBCOMMANDS:
            return runner_mod.main(rest)
        print(f"stutter trial: unknown subcommand {rest[0]!r} (run|cleanup)", file=sys.stderr)
        return 2
    print(f"stutter: unknown trial command {cmd!r}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
