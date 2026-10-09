#!/usr/bin/env python3
"""Validate a run directory against the SPEC-detector.md data contract.

Exit 0 = valid, 1 = problems found.  Prints a per-file report.

Usage: python3 tools/validate_run_dir.py runs/<run-id> [--min-frames N]
"""

from __future__ import annotations

import argparse
import json
import os
import sys

REQUIRED_META = ["run_id", "collector_profile", "t_start_epoch", "host", "mangohud"]
REQUIRED_EVENTS = ["run_start", "collectors_start", "collectors_stop"]


def check(rd, min_frames=100):
    problems = []
    info = {}

    def need(cond, msg):
        if not cond:
            problems.append(msg)
        return cond

    meta_path = os.path.join(rd, "meta.json")
    if not need(os.path.exists(meta_path), "missing meta.json"):
        return problems, info
    with open(meta_path) as fh:
        meta = json.load(fh)
    for k in REQUIRED_META:
        need(k in meta, f"meta.json missing key {k!r}")

    # events
    ev = os.path.join(rd, "events.csv")
    if need(os.path.exists(ev), "missing events.csv"):
        with open(ev) as fh:
            lines = fh.read().strip().splitlines()
        need(lines and lines[0] == "t_epoch,label,detail", "events.csv bad header")
        labels = [l.split(",")[1] for l in lines[1:] if l]
        for want in REQUIRED_EVENTS:
            need(want in labels, f"events.csv missing {want!r} mark")
        info["events"] = len(lines) - 1
        info["injected_stalls"] = labels.count("injected_stall")

    # frametimes
    ft = os.path.join(rd, "frametimes.csv")
    if need(os.path.exists(ft), "missing frametimes.csv"):
        with open(ft) as fh:
            lines = fh.read().strip().splitlines()
        need(lines and lines[0] == "t_epoch,frametime_ms", "frametimes.csv bad header")
        n = len(lines) - 1
        info["frames"] = n
        need(n >= min_frames, f"frametimes.csv only {n} frames (< {min_frames})")
        prev = None
        mono = True
        pos = True
        for line in lines[1:]:
            t, v = line.split(",")[:2]
            t, v = float(t), float(v)
            if v <= 0:
                pos = False
            if prev is not None and t < prev - 1e-6:
                mono = False
            prev = t
        need(pos, "frametimes.csv has non-positive values")
        need(mono, "frametimes.csv t_epoch is not monotonic")

    # generic signal CSVs
    signal_rows = {}
    for name in sorted(os.listdir(rd)):
        if not name.endswith(".csv") or name in ("events.csv", "frametimes.csv"):
            continue
        p = os.path.join(rd, name)
        with open(p) as fh:
            lines = fh.read().strip().splitlines()
        if not lines:
            problems.append(f"{name} is empty")
            continue
        hdr = lines[0].split(",")
        need(hdr[0] == "t_epoch", f"{name} header must start with t_epoch")
        width = len(hdr)
        bad = 0
        for line in lines[1:]:
            if len(line.split(",")) != width:
                bad += 1
        need(bad == 0, f"{name}: {bad} rows with wrong column count")
        signal_rows[name] = len(lines) - 1
    info["signals"] = signal_rows

    # raw + out dirs
    need(os.path.isdir(os.path.join(rd, "raw")), "missing raw/")
    need(os.path.isdir(os.path.join(rd, "out")), "missing out/")
    need(bool(meta.get("mangohud_log")), "meta.mangohud_log not set (no MangoHud log?)")

    return problems, info


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--min-frames", type=int, default=100)
    args = ap.parse_args()
    problems, info = check(args.run_dir, args.min_frames)
    print(json.dumps(info, indent=2))
    if problems:
        print("\nPROBLEMS:")
        for p in problems:
            print(f"  - {p}")
        print("RESULT: INVALID")
        return 1
    print("RESULT: VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
