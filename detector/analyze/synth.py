"""Synthetic run-dir generator.

Produces realistic 144 fps frametime traces with per-frame jitter and injected
hitches -- periodic (default 4 s), sparse (30-90 s), mixed, or clean -- plus
companion signal CSVs and log streams that are correlated with a *subset* of the
hitches (so the correlation stage has something to find and something to reject).

Writes a full run-dir that follows the data contract and returns the ground truth::

    {
      "run_id": ...,
      "hitches": [{"t","magnitude_ms","kind"}, ...],   # post-warm-up injected stalls
      "periodic_s": 4.0, "sparse_s": 45.0, "warmup_s": 20.0,
      "duration_s": 420.0, "target_fps": 144.0, "seed": 0,
    }
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field

import numpy as np

T0_DEFAULT = 1_700_000_000.0


@dataclass
class SynthSpec:
    duration_s: float = 180.0
    target_fps: float = 144.0
    jitter_ms: float = 0.30
    noise_spike_ms: float = 10.0
    noise_spike_rate: float = 1.0          # spikes per minute
    periodic_s: float | None = None
    periodic_ms: float = 55.0
    periodic_jitter_s: float = 0.05
    periodic_skip: float = 0.0             # fraction of periods skipped
    sparse_s: float | None = None
    sparse_ms: float = 70.0
    sparse_jitter_s: float = 2.0
    sparse_skip: float = 0.0
    sparse_offset_s: float = 0.0
    warmup_s: float = 20.0
    schedule_from_t0: bool = False        # schedule hitches from t0 (tests warm-up exclusion)
    companion: bool = True
    seed: int = 0
    run_id: str = "synth"
    label: str = "synthetic"
    t0: float = T0_DEFAULT
    gpu_hz: float = 10.0
    cpu_hz: float = 10.0
    sys_hz: float = 1.0
    hitch_pulse_burst: int = 1


def _scheduled(spec: SynthSpec, rng):
    """Absolute scheduled hitch times with kind + magnitude."""
    out = []
    start = spec.t0 if spec.schedule_from_t0 else spec.t0 + spec.warmup_s
    end = spec.t0 + spec.duration_s
    if spec.periodic_s:
        k = 0
        while True:
            t = start + k * spec.periodic_s
            if t >= end:
                break
            if spec.periodic_skip == 0 or rng.random() >= spec.periodic_skip:
                out.append((t, spec.periodic_ms, "periodic"))
            k += 1
    if spec.sparse_s:
        k = 1
        while True:
            t = start + spec.sparse_offset_s + k * spec.sparse_s + rng.normal(0, spec.sparse_jitter_s)
            if t >= end:
                break
            if spec.sparse_skip == 0 or rng.random() >= spec.sparse_skip:
                out.append((t, spec.sparse_ms, "sparse"))
            k += 1
    out.sort()
    return out


def _build_frametimes(spec: SynthSpec, scheduled, rng):
    base_ms = 1000.0 / spec.target_fps
    frames_t, frames_f = [], []
    gt = []
    t = spec.t0
    end = spec.t0 + spec.duration_s
    si = 0
    burst = max(1, spec.hitch_pulse_burst)
    while t < end:
        if si < len(scheduled) and t >= scheduled[si][0]:
            _, hm, kind = scheduled[si]
            mag = hm * (1.0 + rng.normal(0, 0.03))
            first_t = t
            for b in range(burst):
                frames_t.append(t)
                frames_f.append(mag if b == 0 else max(1.0, base_ms * (1 + abs(rng.normal(0, 0.5)))))
                t += (mag if b == 0 else base_ms) / 1000.0
            gt.append({"t": float(first_t), "magnitude_ms": float(mag), "kind": kind})
            si += 1
            while si < len(scheduled) and scheduled[si][0] <= t:
                si += 1
            continue
        f = max(1.0, base_ms + rng.normal(0, spec.jitter_ms))
        frames_t.append(t)
        frames_f.append(f)
        t += f / 1000.0
    return np.asarray(frames_t), np.asarray(frames_f), gt


def _build_series(spec: SynthSpec, rng, hz, base_map):
    n = max(2, int(spec.duration_s * hz))
    t = spec.t0 + np.arange(n) / hz
    cols = {}
    for name, (base, sd) in base_map.items():
        cols[name] = base + rng.normal(0, sd, n)
    return t, cols


def _apply_pulses(t, cols, hitches, selection, pulse_cols, half_s):
    """Add a rectangular pulse on selected hitches to each pulse column."""
    for name, (amp, signed) in pulse_cols.items():
        v = cols[name]
        for h in hitches:
            if not selection(h):
                continue
            m = (t >= h["t"] - half_s) & (t <= h["t"] + half_s)
            v[m] += (-amp if signed else amp)
        cols[name] = v
    return cols


def _write_csv(path, t, cols):
    names = list(cols.keys())
    with open(path, "w") as fh:
        fh.write("t_epoch," + ",".join(names) + "\n")
        for i in range(len(t)):
            fh.write(f"{t[i]:.6f}," + ",".join(f"{cols[c][i]:.6f}" for c in names) + "\n")


def generate(spec: SynthSpec, out_dir: str, clean: bool = True) -> dict:
    """Write a synthetic run-dir at ``out_dir`` and return its ground truth."""
    rng = np.random.default_rng(spec.seed)
    if clean:
        pass
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(os.path.join(out_dir, "raw"), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "out"), exist_ok=True)

    scheduled = _scheduled(spec, rng)
    ft_t, ft_f, gt = _build_frametimes(spec, scheduled, rng)

    # occasional sub-floor noise spikes (must NOT be flagged; they stay below FLOOR)
    if spec.noise_spike_rate > 0 and len(ft_f) > 10:
        nspk = int(spec.duration_s / 60.0 * spec.noise_spike_rate)
        for _ in range(nspk):
            i = int(rng.integers(1, len(ft_f) - 1))
            ft_f[i] = spec.noise_spike_ms * (1 + abs(rng.normal(0, 0.1)))

    with open(os.path.join(out_dir, "frametimes.csv"), "w") as fh:
        fh.write("t_epoch,frametime_ms\n")
        for i in range(len(ft_t)):
            fh.write(f"{ft_t[i]:.6f},{ft_f[i]:.6f}\n")

    meta = {
        "run_id": spec.run_id,
        "label": spec.label,
        "synthetic": True,
        "launch_options": "synthetic",
        "host": "synthetic",
        "driver": "synthetic",
        "kernel": "synthetic",
        "collector_profile": "synthetic",
        "t_start_epoch": spec.t0,
        "warmup_s": spec.warmup_s,
        "target_fps": spec.target_fps,
        "seed": spec.seed,
    }
    with open(os.path.join(out_dir, "meta.json"), "w") as fh:
        json.dump(meta, fh, indent=2)

    with open(os.path.join(out_dir, "events.csv"), "w") as fh:
        fh.write("t_epoch,label,detail\n")
        fh.write(f"{spec.t0:.6f},run_start,synthetic\n")
        fh.write(f"{spec.t0+1.0:.6f},game_launched,synthetic\n")
        fh.write(f"{spec.t0+5.0:.6f},match_loaded,synthetic\n")
        fh.write(f"{spec.t0+spec.warmup_s:.6f},warmup_end,synthetic\n")
        fh.write(f"{spec.t0+spec.duration_s:.6f},window_end,synthetic\n")
        for h in gt:
            fh.write(f"{h['t']:.6f},injected_stall,{h['kind']}:{h['magnitude_ms']:.1f}\n")

    if spec.companion:
        _write_companions(spec, rng, out_dir, gt)

    gt_out = {
        "run_id": spec.run_id,
        "seed": spec.seed,
        "hitches": gt,
        "periodic_s": spec.periodic_s,
        "sparse_s": spec.sparse_s,
        "warmup_s": spec.warmup_s,
        "duration_s": spec.duration_s,
        "target_fps": spec.target_fps,
        "t0": spec.t0,
    }
    with open(os.path.join(out_dir, "out", "ground_truth.json"), "w") as fh:
        json.dump(gt_out, fh, indent=2)
    return gt_out


def _write_companions(spec: SynthSpec, rng, out_dir, gt):
    # GPU: 10 Hz, drops on ~60% of hitches.
    t, cols = _build_series(
        spec, rng, spec.gpu_hz,
        {"gpu_util_pct": (45.0, 2.0), "sm_clock_mhz": (2400.0, 15.0),
         "power_w": (80.0, 2.0), "vram_pct": (55.0, 1.0)})
    _apply_pulses(t, cols, gt,
                  lambda h: (int(round((h["t"] - spec.t0) * 100)) % 5) != 0,
                  {"gpu_util_pct": (35.0, True), "sm_clock_mhz": (900.0, True),
                   "power_w": (30.0, True)},
                  half_s=0.30)
    _write_csv(os.path.join(out_dir, "gpu.csv"), t, cols)

    # CPU: 10 Hz, PSI spike on ~40% of hitches.
    t, cols = _build_series(
        spec, rng, spec.cpu_hz,
        {"psi_cpu_some_avg10": (0.5, 0.1), "ctxt_switch_rate": (120000.0, 3000.0),
         "busiest_core_util": (70.0, 3.0)})
    _apply_pulses(t, cols, gt,
                  lambda h: (int(round((h["t"] - spec.t0) * 100)) % 3) == 0,
                  {"psi_cpu_some_avg10": (3.0, False), "busiest_core_util": (18.0, False)},
                  half_s=0.30)
    _write_csv(os.path.join(out_dir, "cpu.csv"), t, cols)

    # SYS: 1 Hz (slow signal -> +-2 s window), dirty spike on ~30% of hitches.
    t, cols = _build_series(
        spec, rng, spec.sys_hz,
        {"mem_dirty_mb": (50.0, 10.0), "swap_used_mb": (10.0, 2.0)})
    _apply_pulses(t, cols, gt,
                  lambda h: (int(round((h["t"] - spec.t0) * 100)) % 10) == 0,
                  {"mem_dirty_mb": (400.0, False)},
                  half_s=1.5)
    _write_csv(os.path.join(out_dir, "sys.csv"), t, cols)

    # DECOY: 10 Hz random walk, uncorrelated by construction.
    n = max(2, int(spec.duration_s * spec.gpu_hz))
    dt = spec.t0 + np.arange(n) / spec.gpu_hz
    walk = np.cumsum(rng.normal(0, 0.5, n)) + 100.0
    _write_csv(os.path.join(out_dir, "decoy.csv"), dt, {"noise_metric": walk})

    # LOGS: noise everywhere, plus a correlated template near ~20% of hitches.
    dmesg, journal = [], []
    tn = spec.t0 + 2.0
    while tn < spec.t0 + spec.duration_s:
        dmesg.append((tn, "kernel: unrelated periodic message"))
        tn += rng.uniform(20, 40)
    for h in gt:
        if (int(round((h["t"] - spec.t0) * 100)) % 5) == 0:
            dmesg.append((h["t"] + rng.uniform(-0.2, 0.2),
                          "nvidia 0000:01:00.0: Xid 13 something happened"))
            journal.append((h["t"] + rng.uniform(-0.2, 0.2),
                            "pipewire: xrun detected"))
    tn = spec.t0 + 3.0
    while tn < spec.t0 + spec.duration_s:
        journal.append((tn, "systemd: random journal noise"))
        tn += rng.uniform(30, 90)
    for name, rows in (("dmesg.log", dmesg), ("journal.log", journal)):
        rows.sort()
        with open(os.path.join(out_dir, name), "w") as fh:
            for t, txt in rows:
                fh.write(f"{t:.6f} {txt}\n")


def clean_spec(duration_s=180.0, seed=0) -> SynthSpec:
    return SynthSpec(duration_s=duration_s, seed=seed, run_id=f"clean-{seed}", label="clean")


def periodic_spec(duration_s=160.0, seed=0, period_s=4.0, mag_ms=55.0) -> SynthSpec:
    return SynthSpec(duration_s=duration_s, seed=seed, run_id=f"periodic-{seed}",
                     label="periodic", periodic_s=period_s, periodic_ms=mag_ms)


def sparse_spec(duration_s=420.0, seed=0, period_s=45.0, mag_ms=70.0) -> SynthSpec:
    return SynthSpec(duration_s=duration_s, seed=seed, run_id=f"sparse-{seed}",
                     label="sparse", sparse_s=period_s, sparse_ms=mag_ms)


def mixed_spec(duration_s=420.0, seed=0) -> SynthSpec:
    return SynthSpec(duration_s=duration_s, seed=seed, run_id=f"mixed-{seed}",
                     label="mixed", periodic_s=4.0, periodic_ms=45.0,
                     sparse_s=45.0, sparse_ms=75.0, sparse_offset_s=22.5,
                     sparse_jitter_s=0.1)
