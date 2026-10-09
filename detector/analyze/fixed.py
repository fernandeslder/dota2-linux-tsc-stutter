"""The "fixed" check.

Reads thresholds from ``fixed_def.json`` (defaults are PROVISIONAL until the live
run-to-run baseline variance is measured -- see ``docs/FIXED-DEFINITION.md``) and
evaluates one or more run verdicts against them.
"""

from __future__ import annotations

import json
import os

DEFAULT_DEF_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixed_def.json")


def load_def(path: str | None = None) -> dict:
    with open(path or DEFAULT_DEF_PATH) as fh:
        return json.load(fh)


def check_fixed(verdicts: list, defn: dict | None = None) -> dict:
    defn = defn or load_def()
    crit = defn["criteria"]
    n = len(verdicts)
    checks = []

    def add(name, passed, details):
        checks.append({"criterion": name, "passed": bool(passed), "details": details})

    if crit.get("min_consecutive_runs", {}).get("enabled", True):
        need = crit["min_consecutive_runs"]["value"]
        add("min_consecutive_runs", n >= need, {"have": n, "need": need})

    if crit.get("no_steady_periodic", {}).get("enabled", True):
        c = crit["no_steady_periodic"]
        offenders = []
        for v in verdicts:
            steady = (v.get("periodicity") or {}).get("steady")
            if steady and steady.get("significant") and steady.get("period_s", 1e9) < c["max_period_s"]:
                offenders.append({"run": v.get("run_id"), "period_s": steady["period_s"],
                                  "p": steady["p_value"]})
        add("no_steady_periodic", not offenders,
            {"offenders": offenders, "max_period_s": c["max_period_s"], "p_threshold": c["p_threshold"]})

    if crit.get("sparse_rate_per_min_max", {}).get("enabled", True):
        c = crit["sparse_rate_per_min_max"]
        offenders = []
        hard = []
        for v in verdicts:
            rate = (v.get("hitches") or {}).get("sparse_per_min")
            if rate is None:
                continue
            if rate > c["absolute_cap"]:
                hard.append({"run": v.get("run_id"), "sparse_per_min": rate})
            elif rate > c["value"]:
                offenders.append({"run": v.get("run_id"), "sparse_per_min": rate})
        add("sparse_rate_per_min_max", not offenders and not hard,
            {"over_value": offenders, "over_absolute_cap": hard,
             "value": c["value"], "absolute_cap": c["absolute_cap"]})

    if crit.get("fps_0p1pct_low_min", {}).get("enabled", True):
        c = crit["fps_0p1pct_low_min"]
        offenders = []
        for v in verdicts:
            low = (v.get("frametime") or {}).get("fps_0.1pct_low")
            if low is not None and low < c["value"]:
                offenders.append({"run": v.get("run_id"), "fps_0.1pct_low": low})
        add("fps_0p1pct_low_min", not offenders, {"offenders": offenders, "value": c["value"]})

    if crit.get("min_run_duration_min", {}).get("enabled", True):
        c = crit["min_run_duration_min"]
        offenders = []
        for v in verdicts:
            dur = ((v.get("window") or {}).get("duration_s") or 0) / 60.0
            if dur < c["value"]:
                offenders.append({"run": v.get("run_id"), "duration_min": dur})
        add("min_run_duration_min", not offenders, {"offenders": offenders, "value": c["value"]})

    if crit.get("hitches_per_min_max", {}).get("enabled", False):
        c = crit["hitches_per_min_max"]
        off = [{"run": v.get("run_id"), "per_min": (v.get("hitches") or {}).get("per_min")}
               for v in verdicts if ((v.get("hitches") or {}).get("per_min") or 0) > c["value"]]
        add("hitches_per_min_max", not off, {"offenders": off, "value": c["value"]})

    if crit.get("worst_hitch_ms_max", {}).get("enabled", False):
        c = crit["worst_hitch_ms_max"]
        off = []
        for v in verdicts:
            w = (v.get("hitches") or {}).get("worst_ms")
            if w is not None and w == w and w > c["value"]:
                off.append({"run": v.get("run_id"), "worst_ms": w})
        add("worst_hitch_ms_max", not off, {"offenders": off, "value": c["value"]})

    if crit.get("longest_run_min", {}).get("enabled", False):
        c = crit["longest_run_min"]
        durs = [((v.get("window") or {}).get("duration_s") or 0) / 60.0 for v in verdicts]
        add("longest_run_min", bool(durs) and max(durs) >= c["value"],
            {"longest_min": max(durs) if durs else 0, "need": c["value"]})

    passed = all(c["passed"] for c in checks)
    return {
        "passed": passed,
        "provisional": bool(defn.get("provisional", True)),
        "note": defn.get("note", ""),
        "n_runs": n,
        "checks": checks,
    }


def render_fixed_md(result: dict) -> str:
    L = ["# 'Fixed' check", ""]
    L.append(f"- **passed: {result['passed']}**  (provisional thresholds: {result['provisional']})")
    if result["provisional"]:
        L.append(f"- NOTE: {result['note']}")
    L.append(f"- runs evaluated: {result['n_runs']}")
    L.append("")
    L.append("| criterion | passed | details |")
    L.append("|---|---|---|")
    for c in result["checks"]:
        L.append(f"| {c['criterion']} | {'yes' if c['passed'] else 'NO'} | `{json.dumps(c['details'])}` |")
    L.append("")
    return "\n".join(L) + "\n"
