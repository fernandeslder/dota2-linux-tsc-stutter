"""Build Steam launch-option strings: MangoHud instrumentation + options under test.

A Steam launch-option string is a shell-ish prefix assignment list followed by
``%command%`` and the game's own arguments, e.g.::

    LD_PRELOAD="" MANGOHUD=1 MANGOHUD_CONFIGFILE=/path/mangohud.conf %command% -vulkan

* **native** — Dota's native Vulkan build.  MangoHud is activated through its
  Vulkan implicit layer (``MANGOHUD=1``), which adds no LD_PRELOAD back;
  ``-vulkan`` is forced so the same string is unambiguous.
* **proton** — MangoHud's LD_PRELOAD wrapper (``mangohud %command%``), which works
  for both native and Proton; no ``-vulkan`` is forced.

The MangoHud config we emit always enables per-frame frametime logging::

    output_folder=<dir>  autostart_log=1  log_duration=0  log_interval=0  fps_only=0

``fps_only=0`` is required to keep the ``frametime`` column, and ``log_duration=0``
means "log for as long as the app runs".  See ``detector/collect/mangohud.py``.
"""

from __future__ import annotations

import os
from typing import Optional

from ..collect import mangohud

NATIVE = "native"
PROTON = "proton"


def mangohud_config(output_folder: str, extra: Optional[dict] = None) -> dict:
    """The MangoHud config used for every trial (frametime logging on)."""
    return mangohud.default_config(output_folder, extra=extra)


def write_mangohud_config(path: str, output_folder: str,
                          extra: Optional[dict] = None) -> dict:
    cfg = mangohud_config(output_folder, extra=extra)
    mangohud.write_config_file(path, cfg)
    return cfg


def _has_vulkan(opts: str) -> bool:
    return "-vulkan" in opts.split()


def build(base: str = "", *, mangohud_on: bool = True, output_folder: str = "",
          config_file: str = "", config_mode: str = "file", native: bool = True,
          proton: bool = True, keep_ld_preload_empty: bool = True) -> dict:
    """Return launch-option strings for the native and Proton cases.

    ``base`` is the option string *under test* (it may already contain
    ``-vulkan``).  When ``mangohud_on`` is false the MangoHud environment is
    omitted and only the ``%command% <base>`` skeleton is returned.
    """
    base = (base or "").strip()
    out = {"base": base, "config": None, "mangohud_env": "", "output_folder": output_folder}

    env_prefix = ""
    if mangohud_on:
        if config_mode == "inline":
            cfg = mangohud_config(output_folder)
            env_prefix = "MANGOHUD=1 MANGOHUD_CONFIG=" + mangohud.config_env(cfg)
            out["config"] = cfg
        else:
            conf = config_file or os.path.join(output_folder, "mangohud.conf")
            out["config"] = write_mangohud_config(conf, output_folder)
            out["config_file"] = conf
            env_prefix = f"MANGOHUD=1 MANGOHUD_CONFIGFILE={conf}"
        if keep_ld_preload_empty:
            env_prefix = 'LD_PRELOAD="" ' + env_prefix

    def join(args: str) -> str:
        args = args.strip()
        middle = f"{env_prefix} %command%" if env_prefix else "%command%"
        return f"{middle} {args}".strip()

    if native:
        nat = base if _has_vulkan(base) else (base + " -vulkan").strip()
        out[NATIVE] = join(nat)
    if proton:
        out[PROTON] = join(base)

    if mangohud_on and config_mode == "file" and keep_ld_preload_empty:
        # wrapper form: mangohud LD_PRELOADs the app itself
        wbase = base if not native else (base if _has_vulkan(base) else base + " -vulkan")
        conf = out.get("config_file", "")
        prefix = f"MANGOHUD_CONFIGFILE={conf} " if conf else ""
        out["wrapper"] = f"{prefix}mangohud %command% {wbase}".strip()
    return out
