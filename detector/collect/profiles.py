"""Collector profiles: which signals run, and at what rate.

`full`  - everything the spec asks for, aimed at short diagnostic runs.
`lite`  - the low-overhead subset used for final proofs when collector
          overhead must be negligible (no subprocess-spawning samplers:
          no `ss -ti` TCP info, no `pw-top`, slower NVML/procfs rates).

Every interval is seconds between samples.  `enabled: False` disables the
sampler entirely.  Rationale for the choices is in docs/DETECTOR-COLLECT.md.
"""

from __future__ import annotations

FULL = {
    "profile": "full",
    "nice": 19,
    "ionice": "idle",
    "affinity": "avoid-game",  # pin away from the game's allowed cores when known
    "samplers": {
        "gpu":        {"interval": 0.02},   # 50 Hz NVML (in-process, cheap)
        "cpu":        {"interval": 0.05},   # 20 Hz per-core util from /proc/stat
        "cpufreq":    {"interval": 0.10},   # 10 Hz per-core scaling_cur_freq
        "sys":        {"interval": 0.05},   # 20 Hz PSI + ctxt/runq/load
        "mem":        {"interval": 0.10},   # 10 Hz meminfo + vmstat
        "disk":       {"interval": 0.10},   # 10 Hz diskstats
        "net":        {"interval": 0.10},   # 10 Hz /proc/net/dev
        "threads":    {"interval": 0.05},   # 20 Hz game per-thread CPU
        "hwmon":      {"interval": 0.25},   # 4 Hz temps/RAPL/battery
        "net_tcp":    {"interval": 1.0},    # ss -ti: subprocess, keep at 1 Hz
        "pipewire":   {"interval": 1.0},    # pw-top: subprocess, keep at 1 Hz
        "kwin":       {"interval": 1.0},    # qdbus6 compositing state
        # off-CPU: per-thread state/wchan/syscall.  Not a single-row sampler --
        # the supervisor owns it directly (collectors/offcpu.py).  `hz` is the
        # scan rate; rows are written on state change (+ keepalive) to stay small.
        "offcpu":     {"hz": 100.0, "keepalive_ms": 1000.0, "stacks": False},
    },
    "logs": ["journal", "kwin", "pipewire", "dmesg"],
}

LITE = {
    "profile": "lite",
    "nice": 19,
    "ionice": "idle",
    "affinity": "avoid-game",
    "samplers": {
        "gpu":        {"interval": 0.05},   # 20 Hz
        "cpu":        {"interval": 0.10},   # 10 Hz
        "cpufreq":    {"interval": 0.25},
        "sys":        {"interval": 0.10},
        "mem":        {"interval": 0.25},
        "disk":       {"interval": 0.25},
        "net":        {"interval": 0.25},
        "threads":    {"interval": 0.10},
        "hwmon":      {"interval": 0.50},
        "net_tcp":    {"enabled": False},
        "pipewire":   {"enabled": False},
        "kwin":       {"enabled": False},
        "offcpu":     {"hz": 100.0, "keepalive_ms": 2000.0, "stacks": False},
    },
    "logs": ["dmesg"],
}

# "min": frametimes (MangoHud) only; every sampler and log off. For measuring the instrument's own overhead.
MIN = {
    "profile": "min",
    "nice": 19,
    "ionice": "idle",
    "affinity": "avoid-game",
    "samplers": {k: {"enabled": False} for k in (
        "gpu", "cpu", "cpufreq", "sys", "mem", "disk", "net", "threads", "hwmon",
        "net_tcp", "pipewire", "kwin")},
    "logs": [],
}
MIN["samplers"]["offcpu"] = {"hz": 100.0, "keepalive_ms": 2000.0, "stacks": False, "enabled": False}

PROFILES = {"full": FULL, "lite": LITE, "min": MIN}


def get(name: str) -> dict:
    if name not in PROFILES:
        raise KeyError(f"unknown profile {name!r}; choose from {sorted(PROFILES)}")
    return PROFILES[name]


def sampler_enabled(profile: dict, name: str) -> bool:
    cfg = profile.get("samplers", {}).get(name, {})
    return bool(cfg.get("enabled", True)) and "interval" in cfg


def sampler_interval(profile: dict, name: str) -> float:
    return float(profile["samplers"][name]["interval"])
