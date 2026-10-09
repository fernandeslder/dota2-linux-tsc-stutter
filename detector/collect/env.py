"""Host / environment metadata for meta.json and docs."""

from __future__ import annotations

import os
import platform

from . import util


def _first(path: str, default: str = "") -> str:
    return util.read_text(path).strip() or default


def _git_commit(root: str) -> str:
    rc, out, _ = util.run_capture(["git", "-C", root, "rev-parse", "--short", "HEAD"], timeout=3)
    return out.strip() if rc == 0 else ""


def mangohud_version() -> str:
    rc, out, _ = util.run_capture(["mangohud", "--version"], timeout=3)
    if rc == 0 and out.strip():
        return out.strip().splitlines()[0]
    return ""


def host_info(root: str = "") -> dict:
    try:
        import pynvml  # noqa: F401
        pynvml_ver = "present"
    except Exception:
        pynvml_ver = "missing"
    lscpu = ""
    rc, out, _ = util.run_capture(["lscpu"], timeout=4)
    if rc == 0:
        for line in out.splitlines():
            if line.startswith("Model name:"):
                lscpu = line.split(":", 1)[1].strip()
                break
    return {
        "hostname": platform.node(),
        "kernel": platform.release(),
        "os": _first("/etc/os-release").splitlines()[0] if _first("/etc/os-release") else "",
        "cpu_model": lscpu or platform.processor(),
        "n_cpu": len(util.all_cpus()),
        "ccd_map": {str(k): v for k, v in util.ccd_map_for_cpus().items()},
        "session_type": os.environ.get("XDG_SESSION_TYPE", ""),
        "desktop": os.environ.get("XDG_CURRENT_DESKTOP", ""),
        "python": platform.python_version(),
        "pynvml": pynvml_ver,
        "mangohud": mangohud_version(),
        "git_commit": _git_commit(root) if root else "",
        "collector_version": _collector_version(),
    }


def _collector_version() -> str:
    try:
        from . import __version__
        return __version__
    except Exception:
        return ""
