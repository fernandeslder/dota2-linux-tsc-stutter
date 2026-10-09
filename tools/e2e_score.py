"""Score a finished e2e run: detect/report + precision/recall vs ground truth.

Usage: python3 tools/e2e_score.py runs/validate-<sc>-<stamp> [--n-perm 400]
Writes runs/.../e2e-score.json (derived, committable) and prints a summary.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from detector.analyze import reporting  # noqa: E402
from detector.analyze.config import HitchConfig  # noqa: E402
from detector.analyze.rundir import load_rundir  # noqa: E402


def read_hitches(run_dir, primary_only=True):
    """Read detected hitches; default to the primary tier (severity=high), which is
    the tier the verdict / FIXED definition counts (see docs/VALIDATION-e2e.md B6)."""
    p = os.path.join(run_dir, "out", "hitches.csv")
    rows = []
    with open(p) as fh:
        for r in csv.DictReader(fh):
            if primary_only and r.get("severity") != "high":
                continue
            rows.append((float(r["t_epoch"]), float(r["magnitude_ms"])))
    return rows


def load_gt(run_dir):
    with open(os.path.join(run_dir, "e2e-ground-truth.json")) as fh:
        return json.load(fh)


def score_detection(gt_stalls, hitches, tol_s=0.5):
    used = [False] * len(hitches)
    tp_err, fn = [], 0
    for s in gt_stalls:
        b = s["t_cont"]
        best, bestj = None, -1
        for j, (ht, hm) in enumerate(hitches):
            if used[j]:
                continue
            d = ht - b
            if abs(d) <= tol_s and (best is None or abs(d) < abs(best)):
                best, bestj = d, j
        if best is None:
            fn += 1
        else:
            used[bestj] = True
            tp_err.append(best)
    tp = len(tp_err)
    fp = sum(1 for u in used if not u)
    return {"tp": tp, "fp": fp, "fn": fn,
            "precision": round(tp / max(1, tp + fp), 4),
            "recall": round(tp / max(1, tp + fn), 4),
            "err_ms": sorted(round(e * 1000, 1) for e in tp_err)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--n-perm", type=int, default=400)
    ap.add_argument("--seed", type=int, default=20261008)
    args = ap.parse_args()

    rd = load_rundir(args.run_dir)
    cfg = HitchConfig().resolve()
    verdict = reporting.analyze_run(rd, cfg, n_perm=args.n_perm, seed=args.seed)
    out = os.path.join(rd.path, "out")
    reporting.write_outputs(rd, verdict, out, plots=True)

    h = read_hitches(rd.path)
    gt = load_gt(rd.path)
    det = score_detection(gt.get("stalls", []), h)

    w = verdict["window"]
    per = verdict["periodicity"]
    score = {
        "run_dir": rd.path,
        "scenario": gt.get("scenario"),
        "window_s": round(w["duration_s"], 1),
        "n_frames": w["n_frames"],
        "n_gt": len(gt.get("stalls", [])),
        "n_detected": len(h),
        "detection": det,
        "hitches_per_min": verdict["hitches"]["per_min"],
        "worst_ms": verdict["hitches"]["worst_ms"],
        "p50_ms": verdict["frametime"]["p50_ms"],
        "p99_ms": verdict["frametime"]["p99_ms"],
        "periodicity_kind": per["kind"],
        "steady": {k: per["steady"].get(k) for k in
                   ("period_s", "period_err_s", "p_value", "significant",
                    "fraction_explained")},
        "sparse": {k: per["sparse"].get(k) for k in
                   ("period_s", "p_value", "significant", "fraction_explained")},
        "sparse_residual": {k: (per.get("sparse_residual") or {}).get(k) for k in
                            ("period_s", "p_value", "significant")},
        "sparse_assessable": per["sparse_assessable"],
        "sparse_assessment": verdict.get("sparse"),
        "data_quality": verdict.get("data_quality"),
        "correlation_top5": [{"signal": r["signal"], "column": r["column"],
                              "feature": r["feature"],
                              "cliffs_delta": round(r["cliffs_delta"], 3),
                              "z": round(r["z"], 2), "q_value": r.get("q_value")}
                             for r in verdict["correlation"]["signals"][:5]],
        "warnings": verdict.get("warnings", []),
    }
    with open(os.path.join(rd.path, "e2e-score.json"), "w") as fh:
        json.dump(score, fh, indent=2)
    print(json.dumps(score, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
