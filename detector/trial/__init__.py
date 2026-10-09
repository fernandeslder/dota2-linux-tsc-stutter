"""Orchestration-friendly trial tooling: `stutter preflight|launchopts|trial`.

Modules
  vdf.py         robust Valve KeyValues (VDF) reader + surgical editor
  steam.py       locate Steam's localconfig.vdf, get/set/restore LaunchOptions
  launchopts.py  build Steam launch-option strings (MangoHud + options under test)
  preflight.py   read-only PASS/WARN/FAIL environment checks
  runner.py      `stutter trial run` sequencing + `stutter trial cleanup`
  cli.py         argparse dispatch for the three subcommands
"""

__version__ = "1.0"
