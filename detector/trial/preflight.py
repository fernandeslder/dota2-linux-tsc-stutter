"""`stutter preflight` -- read-only go/no-go checks before a trial.

Every check is independent and side-effect free.  Each returns one of:

* ``PASS`` -- as required for a trustworthy trial.
* ``WARN`` -- workable, but note it (it can bias the numbers).
* ``FAIL`` -- do not trust a trial until this is fixed.

The one deliberate hard failure on this laptop is **AC power**: an unplugged
machine runs on a different power/clock budget, so a run started on battery is
not comparable to the AC baseline and is refused.
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
from dataclasses import dataclass, field
from typing import List, Optional

from ..collect import util
from . import steam as steammod

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"

DISK_WARN_GIB = 20.0
DISK_FAIL_GIB = 2.0


@dataclass
class Check:
    name: str
    status: str
    detail: str
    data: dict = field(default_factory=dict)


def _nv(*args: str, timeout: float = 8.0):
    return util.run_capture(["nvidia-smi", *args], timeout=timeout)


def _csv_query(fields: str) -> List[dict]:
    rc, out, _ = _nv(f"--query-gpu={fields}", "--format=csv,noheader,nounits")
    if rc != 0 or not out.strip():
        return []
    keys = [f.strip() for f in fields.split(",")]
    rows = []
    for line in out.strip().splitlines():
        cells = [c.strip() for c in line.split(",")]
        rows.append({k: (cells[i] if i < len(cells) else "") for i, k in enumerate(keys)})
    return rows


# ---------------------------------------------------------------------------
# checks
# ---------------------------------------------------------------------------

def check_nvidia_gpu() -> Check:
    if not util.have("nvidia-smi"):
        return Check("nvidia-gpu", FAIL, "nvidia-smi not found (no NVIDIA driver?)")
    rows = _csv_query("name,driver_version")
    if not rows or not rows[0].get("name"):
        return Check("nvidia-gpu", FAIL, "nvidia-smi returned no GPU")
    g = rows[0]
    return Check("nvidia-gpu", PASS, f"{g['name']}, driver {g['driver_version']}",
                 {"gpus": rows})


def check_vulkan() -> Check:
    if not util.have("vulkaninfo"):
        return Check("vulkan-device", FAIL, "vulkaninfo not installed (vulkan-tools)")
    rc, out, err = util.run_capture(["vulkaninfo", "--summary"], timeout=25)
    if rc != 0:
        return Check("vulkan-device", FAIL, f"vulkaninfo failed rc={rc}: {(err or out)[:200]}")
    devices = []
    cur = None
    for line in out.splitlines():
        if re.match(r"\s*GPU\d+:", line):
            cur = {}
            devices.append(cur)
            continue
        if cur is not None and "=" in line:
            k, v = line.split("=", 1)
            cur[k.strip()] = v.strip()
    nvidia = [d for d in devices if d.get("vendorID", "").lower() == "0x10de"]
    if not devices:
        return Check("vulkan-device", FAIL, "no Vulkan physical devices")
    if not nvidia:
        return Check("vulkan-device", FAIL,
                     "no NVIDIA Vulkan device (Dota would use: "
                     + ", ".join(d.get("deviceName", "?") for d in devices) + ")")
    name = nvidia[0].get("deviceName", "?")
    kind = nvidia[0].get("deviceType", "")
    detail = f"Dota would use: {name} ({kind}, driverID {nvidia[0].get('driverID','?')})"
    status = PASS
    if len(devices) > 1:
        status = WARN
        detail += f"; {len(devices) - 1} other device(s) also present"
    return Check("vulkan-device", status, detail, {"devices": devices})


def check_nvidia_clocks() -> Check:
    if not util.have("nvidia-smi"):
        return Check("nvidia-clocks", FAIL, "nvidia-smi not found")
    rows = _csv_query("pstate,clocks.current.graphics,clocks.max.graphics,"
                      "clocks_throttle_reasons.active,persistence_mode")
    if not rows:
        return Check("nvidia-clocks", WARN, "could not query clock state")
    r = rows[0]
    lock_support = False
    rc, helpout, _ = _nv("--help", timeout=6)
    if rc == 0 and "--lock-gpu-clocks" in helpout:
        lock_support = True
    rc, q, _ = _nv("-q", "-d", "CLOCK", timeout=8)
    locked = "gpu locked" in q.lower()
    detail = (f"pstate {r.get('pstate','?')}, "
              f"sm {r.get('clocks.current.graphics','?')}/{r.get('clocks.max.graphics','?')} MHz, "
              f"throttle {r.get('clocks_throttle_reasons.active','?')}, "
              f"persistence {r.get('persistence_mode','?')}, "
              f"clock-lock {'SUPPORTED' if lock_support else 'unsupported'}"
              + (", CURRENTLY LOCKED" if locked else ""))
    status = PASS
    if r.get("persistence_mode", "").strip().lower() == "disabled":
        status = WARN
        detail += "; persistence disabled (first-use clock ramp may add latency)"
    return Check("nvidia-clocks", status, detail,
                 {"lock_supported": lock_support, "locked": locked, "raw": r})


def check_nvidia_powerd() -> Check:
    active = _systemctl_active("nvidia-powerd")
    if active is True:
        return Check("nvidia-powerd", PASS, "active")
    if active is False:
        return Check("nvidia-powerd", WARN, "inactive (dynamic boost may be limited)")
    return Check("nvidia-powerd", WARN, "systemctl could not report state")


def _systemctl_active(unit: str) -> Optional[bool]:
    rc, out, _ = util.run_capture(["systemctl", "is-active", unit], timeout=5)
    if rc not in (0, 3):
        return None
    return out.strip() == "active"


def check_ollama() -> Check:
    if not util.have("ollama"):
        return Check("ollama", PASS, "not installed")
    active = _systemctl_active("ollama")
    models = []
    rc, out, _ = util.run_capture(["ollama", "ps"], timeout=8)
    if rc == 0:
        for line in out.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 4 and parts[0] != "NAME":
                models.append(parts[0])
    if active:
        detail = f"active" + (f", {len(models)} model(s) loaded: {', '.join(models)}" if models else "")
        return Check("ollama", WARN, detail + " (GPU competitor; use `stutter trial run --quiesce`)")
    return Check("ollama", PASS, "inactive")


def check_containers() -> Check:
    runner = "docker" if util.have("docker") else ("podman" if util.have("podman") else "")
    if not runner:
        return Check("containers", PASS, "no container runtime")
    rc, out, _ = util.run_capture([runner, "ps", "--format", "{{.Names}}\t{{.Status}}"], timeout=12)
    if rc != 0:
        return Check("containers", WARN, f"{runner} present but query failed")
    names = [l.split("\t")[0] for l in out.splitlines() if l.strip()]
    if names:
        return Check("containers", WARN,
                     f"{len(names)} running: {', '.join(names)} (CPU/IO competitors)")
    return Check("containers", PASS, "none running")


def check_steam() -> Check:
    pids = steammod.steam_pids()
    if pids:
        return Check("steam", PASS, f"running (pids {pids[:3]}{'...' if len(pids) > 3 else ''})")
    return Check("steam", WARN, "not running (needed to launch Dota; must be quit to set "
                               "LaunchOptions)")


def check_mangohud() -> Check:
    if not util.have("mangohud"):
        return Check("mangohud", FAIL, "mangohud not installed")
    ver = util.run_capture(["mangohud", "--version"], timeout=5)[1].strip()
    layer = os.path.exists("/usr/share/vulkan/implicit_layer.d/MangoHud.x86_64.json")
    if not layer:
        for root in ("/usr/share/vulkan", "/etc/vulkan"):
            if os.path.exists(os.path.join(root, "implicit_layer.d", "MangoHud.x86_64.json")):
                layer = True
                break
    status = PASS if layer else WARN
    return Check("mangohud", status,
                 f"{ver or 'mangohud present'}; Vulkan layer {'present' if layer else 'MISSING'}",
                 {"version": ver, "layer": layer})


def check_dota(account: Optional[str] = None, vdf_path: Optional[str] = None) -> Check:
    # install
    installdir, manifest = "", ""
    for root in steammod.steam_roots():
        p = os.path.join(root, "steamapps", "common", "dota 2 beta")
        if os.path.isdir(p):
            installdir = p
        m = os.path.join(root, "steamapps", "appmanifest_570.acf")
        if os.path.isfile(m):
            manifest = m
        if installdir:
            break
    try:
        acc = steammod.find_dota_config(account, vdf_path)
        opts = steammod.get_launch_options(acc)
        acct_info = {"steamid": acc.steamid, "vdf": acc.vdf_path}
    except steammod.SteamConfigError as exc:
        opts, acc, acct_info = None, None, {"error": str(exc)}
    if not installdir:
        return Check("dota", FAIL, "Dota 2 install not found "
                                   f"({acct_info.get('error', 'no steamapps/common/dota 2 beta')})",
                     {"launch_options": opts, **acct_info})
    detail = f"installed at {installdir}"
    if opts:
        detail += f'; LaunchOptions="{opts}"'
    else:
        detail += "; no LaunchOptions set"
    return Check("dota", PASS, detail,
                 {"installdir": installdir, "appmanifest": manifest,
                  "launch_options": opts, **acct_info})


def check_display() -> Check:
    if not util.have("kscreen-doctor"):
        return Check("display", WARN, "kscreen-doctor not available")
    rc, out, _ = util.run_capture(["kscreen-doctor", "-j"], timeout=10)
    if rc != 0:
        return Check("display", WARN, "kscreen-doctor -j failed")
    try:
        d = json.loads(out)
    except ValueError:
        return Check("display", WARN, "kscreen-doctor JSON unparseable")
    primary = None
    for o in d.get("outputs", []):
        if o.get("enabled") and o.get("priority", 0) and o.get("primary"):
            primary = o
            break
    if primary is None:
        for o in d.get("outputs", []):
            if o.get("enabled"):
                primary = o
                break
    comp = None
    if util.have("qdbus6"):
        rc2, out2, _ = util.run_capture(
            ["qdbus6", "org.kde.KWin", "/Compositor", "org.kde.kwin.Compositing.active"],
            timeout=5)
        if rc2 == 0:
            comp = out2.strip().lower() == "true"
    if primary is None:
        return Check("display", WARN, f"no enabled output (compositing={comp})")
    mode = primary.get("currentModeId")
    name, refresh = "", None
    for m in primary.get("modes", []):
        if m.get("id") == mode:
            name = m.get("name", "")
            refresh = m.get("refreshRate")
    vrr = primary.get("vrr")
    if vrr is None:
        # kscreen's JSON omits VRR; the human-readable output has it.
        _rc, text, _ = util.run_capture(["kscreen-doctor", "-o"], timeout=10)
        mm = re.search(r"Vrr:\s*(\S+)", text)
        vrr = mm.group(1) if mm else "unknown"
    detail = (f"{primary.get('name','?')} {name} ({refresh} Hz), "
              f"VRR={vrr}, compositing={'on' if comp else ('off' if comp is False else '?')}")
    status = PASS
    if vrr not in ("Never", "incapable", "unknown", "Disabled", "disabled"):
        status = WARN
        detail += " (VRR on: record it, it changes frametimes)"
    return Check("display", status, detail,
                 {"output": primary.get("name"), "mode": name, "refresh": refresh,
                  "vrr": vrr, "compositing": comp})


def check_cpu_governor() -> Check:
    gov = _read("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor")
    epp = _read("/sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference")
    if not gov:
        return Check("cpu-governor", WARN, "cpufreq not readable")
    status = PASS if gov == "performance" else WARN
    detail = f"governor={gov or '?'}, EPP={epp or '?'}"
    if status == WARN:
        detail += " (not 'performance': clocks may not be pinned high)"
    return Check("cpu-governor", status, detail, {"governor": gov, "epp": epp})


def check_platform_profile() -> Check:
    prof = _read("/sys/firmware/acpi/platform_profile")
    choices = _read("/sys/firmware/acpi/platform_profile_choices")
    if not prof:
        return Check("platform-profile", WARN, "platform_profile not exposed")
    status = PASS if prof == "performance" else WARN
    detail = f"{prof}" + (f" (choices: {choices})" if choices else "")
    if status == WARN:
        detail += "; consider `powerprofilesctl set performance`"
    return Check("platform-profile", status, detail, {"profile": prof, "choices": choices})


def check_disk() -> Check:
    try:
        u = shutil.disk_usage(REPO_ROOT)
    except OSError as exc:
        return Check("disk", WARN, f"could not stat disk: {exc}")
    free_gib = u.free / (1024 ** 3)
    status = PASS if free_gib >= DISK_WARN_GIB else (FAIL if free_gib < DISK_FAIL_GIB else WARN)
    return Check("disk", status, f"{free_gib:.1f} GiB free on the runs filesystem",
                 {"free_gib": free_gib})


def check_versions() -> Check:
    kernel = platform.release()
    driver = ""
    rows = _csv_query("driver_version")
    if rows:
        driver = rows[0].get("driver_version", "")
    return Check("versions", PASS, f"kernel {kernel}, NVIDIA driver {driver or '?'}",
                 {"kernel": kernel, "driver": driver})


def check_ac_power() -> Check:
    mains = []
    batteries = []
    for entry in sorted(os.listdir("/sys/class/power_supply")):
        base = os.path.join("/sys/class/power_supply", entry)
        typ = _read(os.path.join(base, "type"))
        if typ == "Mains":
            mains.append((entry, _read(os.path.join(base, "online"))))
        elif typ == "Battery":
            batteries.append((entry, _read(os.path.join(base, "status"))))
    if not mains and not batteries:
        return Check("ac-power", WARN, "no power_supply devices (desktop?)")
    online = any(v == "1" for _, v in mains)
    discharging = any(s == "Discharging" for _, s in batteries)
    parts = [f"AC {'online' if online else 'OFFLINE'}"]
    parts += [f"{n}={s}" for n, s in batteries]
    detail = "; ".join(parts)
    if not online or discharging:
        return Check("ac-power", FAIL,
                     detail + " -- unplugged/battery: not comparable to the AC baseline",
                     {"online": online, "mains": mains, "batteries": batteries})
    return Check("ac-power", PASS, detail, {"online": online, "mains": mains,
                                            "batteries": batteries})


def _read(path: str) -> str:
    try:
        with open(path) as fh:
            return fh.read().strip()
    except OSError:
        return ""


# ---------------------------------------------------------------------------
# driver
# ---------------------------------------------------------------------------

def run_checks(account: Optional[str] = None, vdf_path: Optional[str] = None) -> List[Check]:
    checks = [
        check_nvidia_gpu,
        check_vulkan,
        check_nvidia_clocks,
        check_nvidia_powerd,
        check_ollama,
        check_containers,
        check_steam,
        check_mangohud,
        lambda: check_dota(account, vdf_path),
        check_display,
        check_cpu_governor,
        check_platform_profile,
        check_disk,
        check_versions,
        check_ac_power,
    ]
    out = []
    for fn in checks:
        try:
            out.append(fn())
        except Exception as exc:  # a check must never abort preflight
            out.append(Check(getattr(fn, "__name__", "check"), WARN, f"check errored: {exc}"))
    return out


def render(checks: List[Check]) -> str:
    lines = []
    width = max(len(c.name) for c in checks) if checks else 0
    for c in checks:
        lines.append(f"[{c.status}] {c.name.ljust(width)}  {c.detail}")
    n = {s: sum(1 for c in checks if c.status == s) for s in (PASS, WARN, FAIL)}
    lines.append(f"SUMMARY: {n[PASS]} PASS, {n[WARN]} WARN, {n[FAIL]} FAIL")
    return "\n".join(lines)


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="stutter preflight")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--account", default=None, help="Steam account id (userdata dir name)")
    ap.add_argument("--vdf", default=None, help="explicit localconfig.vdf path")
    args = ap.parse_args(argv)

    checks = run_checks(account=args.account, vdf_path=args.vdf)
    if args.json:
        print(json.dumps([{"name": c.name, "status": c.status, "detail": c.detail,
                           "data": c.data} for c in checks], indent=2, default=str))
    else:
        print(render(checks))
    return 1 if any(c.status == FAIL for c in checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
