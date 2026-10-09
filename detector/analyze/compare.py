"""A/B comparison of two sets of runs (A: before, B: after).

Every metric is reported with the run-to-run mean/SD in each set, the bootstrap CI
of the B-A difference, an effect size (Cohen's d and Cliff's delta) and a verdict
that accounts for the run-to-run variance: a difference is only called
improved/worse when the CI excludes zero *and* the effect size is at least
``effect_threshold`` (default 0.5); otherwise ``inconclusive``.
"""

from __future__ import annotations

import numpy as np

from . import stats as st

METRICS = [
    {"key": "hitches_per_min", "direction": "lower", "label": "Hitches / min"},
    {"key": "worst_ms", "direction": "lower", "label": "Worst hitch (ms)"},
    {"key": "p99_ms", "direction": "lower", "label": "p99 frametime (ms)"},
    {"key": "p95_ms", "direction": "lower", "label": "p95 frametime (ms)"},
    {"key": "fps_1pct_low", "direction": "higher", "label": "1% low (fps)"},
    {"key": "fps_0.1pct_low", "direction": "higher", "label": "0.1% low (fps)"},
    {"key": "mean_fps", "direction": "higher", "label": "Mean fps"},
    {"key": "periodic_flag", "direction": "lower", "label": "Steady periodic flag (0/1)"},
]

EFFECT_THRESHOLD = 0.5


def extract_metrics(verdict: dict) -> dict:
    ft = verdict["frametime"]
    per = verdict["periodicity"]
    steady = per.get("steady")
    periodic_flag = 1.0 if (steady and steady.get("significant")) else 0.0
    return {
        "hitches_per_min": verdict["hitches"]["per_min"],
        "worst_ms": verdict["hitches"]["worst_ms"],
        "p99_ms": ft.get("p99_ms"),
        "p95_ms": ft.get("p95_ms"),
        "fps_1pct_low": ft.get("fps_1pct_low"),
        "fps_0.1pct_low": ft.get("fps_0.1pct_low"),
        "mean_fps": ft.get("mean_fps"),
        "periodic_flag": periodic_flag,
    }


def _compare_metric(a, b, direction, effect_threshold=EFFECT_THRESHOLD):
    a = np.asarray([x for x in a if x is not None and np.isfinite(x)], dtype=float)
    b = np.asarray([x for x in b if x is not None and np.isfinite(x)], dtype=float)
    out = {
        "n_a": int(a.size), "n_b": int(b.size),
        "mean_a": float(a.mean()) if a.size else float("nan"),
        "mean_b": float(b.mean()) if b.size else float("nan"),
        "sd_a": float(a.std(ddof=1)) if a.size > 1 else 0.0,
        "sd_b": float(b.std(ddof=1)) if b.size > 1 else 0.0,
    }
    if a.size == 0 or b.size == 0:
        out.update({"delta": float("nan"), "ci_lo": float("nan"), "ci_hi": float("nan"),
                    "cohens_d": float("nan"), "cliffs_delta": float("nan"),
                    "verdict": "insufficient_runs"})
        return out
    delta, lo, hi = st.bootstrap_ci_diff(b, a)
    d = st.cohens_d(b, a)
    out.update({
        "delta": delta, "ci_lo": lo, "ci_hi": hi,
        "cohens_d": d, "cliffs_delta": st.cliffs_delta(b, a),
        "rel_change_pct": (100.0 * (b.mean() - a.mean()) / a.mean()) if a.mean() else float("nan"),
    })
    if a.size < 2 or b.size < 2:
        out["verdict"] = "inconclusive"
        return out
    if not np.isfinite(lo) or not np.isfinite(hi) or lo <= 0 <= hi:
        out["verdict"] = "inconclusive"
        return out
    if np.isnan(d) or (np.isfinite(d) and abs(d) < effect_threshold):
        out["verdict"] = "inconclusive"
        return out
    improved = (delta > 0) if direction == "higher" else (delta < 0)
    out["verdict"] = "improved" if improved else "worse"
    return out


def compare_runs(a_verdicts: list, b_verdicts: list,
                 effect_threshold: float = EFFECT_THRESHOLD) -> dict:
    a_metrics = [extract_metrics(v) for v in a_verdicts]
    b_metrics = [extract_metrics(v) for v in b_verdicts]
    results = []
    for m in METRICS:
        r = _compare_metric([x[m["key"]] for x in a_metrics],
                            [x[m["key"]] for x in b_metrics],
                            m["direction"], effect_threshold)
        r.update({"key": m["key"], "label": m["label"], "direction": m["direction"]})
        results.append(r)
    verdicts = [r["verdict"] for r in results]
    if "worse" in verdicts and "improved" in verdicts:
        overall = "mixed"
    elif "worse" in verdicts:
        overall = "worse"
    elif "improved" in verdicts:
        overall = "improved"
    else:
        overall = "inconclusive"
    return {
        "A_runs": [v.get("run_id") for v in a_verdicts],
        "B_runs": [v.get("run_id") for v in b_verdicts],
        "effect_threshold": effect_threshold,
        "metrics": results,
        "verdict": overall,
    }


def render_compare_md(cmp: dict) -> str:
    L = ["# A/B comparison (A = before, B = after)", ""]
    L.append(f"- A runs: {', '.join(str(x) for x in cmp['A_runs'])}")
    L.append(f"- B runs: {', '.join(str(x) for x in cmp['B_runs'])}")
    L.append(f"- **overall verdict: {cmp['verdict']}** "
             f"(effect threshold |d| >= {cmp['effect_threshold']})")
    L.append("")
    L.append("| metric | A mean±sd | B mean±sd | Δ (B-A) | 95% CI | d | verdict |")
    L.append("|---|---|---|---|---|---|---|")
    for r in cmp["metrics"]:
        L.append(f"| {r['label']} | {r['mean_a']:.3g}±{r['sd_a']:.3g} | "
                 f"{r['mean_b']:.3g}±{r['sd_b']:.3g} | {r['delta']:+.3g} | "
                 f"[{r['ci_lo']:.3g}, {r['ci_hi']:.3g}] | {r['cohens_d']:+.2f} | "
                 f"{r['verdict']} |")
    L.append("")
    L.append("A metric is called improved/worse only when the bootstrap CI of the B-A "
             "difference excludes 0 and |Cohen's d| >= threshold; otherwise inconclusive. "
             "With < 2 runs per side the run-to-run variance is unknown and every "
             "verdict is inconclusive.")
    L.append("")
    return "\n".join(L) + "\n"
