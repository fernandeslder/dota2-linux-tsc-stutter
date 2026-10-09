"""``stutter selftest`` -- validate the analysis pipeline against synthetic ground truth.

Generates synthetic runs with known truth (4 s periodic, 45 s sparse, mixed, clean) and
checks:

* recovered period within +-5% of truth,
* hitch precision/recall >= 0.95 against injected ground truth,
* **no** periodic flag on clean traces (false-positive rate over >= 50 seeds),
* warm-up exclusion (hitches before ``warmup_end`` are dropped),
* a K / FLOOR sensitivity table.

Returns (and prints) a structured result; ``passed`` is True only if every assertion
holds. Nothing here runs Dota.
"""

from __future__ import annotations

import dataclasses
import os
import shutil
import tempfile

import numpy as np

from . import reporting, synth
from .config import HitchConfig
from .rundir import load_rundir

PR_TOL_S = 0.25
PERIOD_TOL_FRAC = 0.05


def precision_recall(det_times, gt_times, tol: float = PR_TOL_S) -> tuple:
    det = np.asarray(sorted(det_times), dtype=float)
    gt = np.asarray(sorted(gt_times), dtype=float)
    if gt.size == 0 and det.size == 0:
        return 1.0, 1.0
    if det.size == 0:
        return float("nan"), 0.0        # missed everything
    if gt.size == 0:
        return 0.0, float("nan")        # everything detected is a false positive
    used = set()
    tp = 0
    for d in det:
        j = int(np.argmin(np.abs(gt - d)))
        if abs(gt[j] - d) <= tol and j not in used:
            used.add(j)
            tp += 1
    recall = tp / gt.size
    precision = tp / det.size
    return float(precision), float(recall)


def _post_warmup(events, warmup_end):
    return [e.t for e in events if e.t >= warmup_end]


def _analyze(spec, workdir, cfg, n_perm):
    d = os.path.join(workdir, spec.run_id)
    gt = synth.generate(spec, d)
    rd = load_rundir(d)
    v = reporting.analyze_run(rd, cfg, n_perm=n_perm)
    events = v.get("_events", [])
    we = rd.warmup_end()
    det = _post_warmup(events, we)
    gt_times = [h["t"] for h in gt["hitches"] if h["t"] >= we]
    return v, gt, det, gt_times, we


def _check(results, name, passed, detail):
    results["assertions"].append({"name": name, "passed": bool(passed), "detail": detail})
    if not passed:
        results["passed"] = False


def _period_close(got, want, frac=PERIOD_TOL_FRAC):
    if got is None or want is None or want == 0:
        return False
    return abs(got - want) / want <= frac


def _scenario(results, name, spec_factory, truth_period, want_kinds, seeds, workdir,
              cfg, n_perm, key_check=True):
    rows = []
    for s in range(seeds):
        spec = spec_factory(s)
        v, gt, det, gt_times, we = _analyze(spec, workdir, cfg, n_perm)
        prec, rec = precision_recall(det, gt_times)
        per = v["periodicity"]
        steady = per.get("steady")
        band = steady if (name != "sparse") else per.get("sparse")
        period = band["period_s"] if band else None
        kind = per["kind"]
        rows.append({
            "seed": s, "kind": kind, "period_s": period, "precision": prec,
            "recall": rec, "n_gt": len(gt_times), "n_det": len(det),
        })
        if key_check:
            _check(results, f"{name}[{s}].kind", kind in want_kinds,
                   f"kind={kind} want={want_kinds}")
            _check(results, f"{name}[{s}].period", _period_close(period, truth_period),
                   f"period={period} want~{truth_period}")
        _check(results, f"{name}[{s}].recall", rec >= 0.95, f"recall={rec:.3f}")
        _check(results, f"{name}[{s}].precision", prec >= 0.95, f"precision={prec:.3f}")
    results[name] = rows
    return rows


def run_selftest(workdir: str | None = None, n_seeds: int = 50, scenario_seeds: int = 10,
                 n_perm: int = 250, cfg: HitchConfig | None = None, keep: bool = False,
                 verbose: bool = True) -> dict:
    cfg = (cfg or HitchConfig()).resolve()
    tmp = workdir or tempfile.mkdtemp(prefix="stutter-selftest-")
    os.makedirs(tmp, exist_ok=True)
    results = {"workdir": tmp, "n_seeds": n_seeds, "scenario_seeds": scenario_seeds,
               "assertions": [], "passed": True}

    def log(*a):
        if verbose:
            print(*a, flush=True)

    log(f"[selftest] workdir={tmp} clean_seeds={n_seeds} scenario_seeds={scenario_seeds} n_perm={n_perm}")

    log("[selftest] periodic (4.0 s) ...")
    _scenario(results, "periodic", lambda s: synth.periodic_spec(seed=s),
              4.0, {"periodic", "mixed"}, scenario_seeds, tmp, cfg, n_perm)

    log("[selftest] sparse (45 s) ...")
    _scenario(results, "sparse", lambda s: synth.sparse_spec(seed=s),
              45.0, {"sparse"}, scenario_seeds, tmp, cfg, n_perm)

    log("[selftest] mixed (4 s + sparse) ...")
    _scenario(results, "mixed", lambda s: synth.mixed_spec(seed=s),
              4.0, {"mixed", "periodic"}, scenario_seeds, tmp, cfg, n_perm)

    log(f"[selftest] clean (no hitches) x{n_seeds} ...")
    clean_rows = []
    flagged = 0
    false_hitch_total = 0
    for s in range(n_seeds):
        v, gt, det, gt_times, we = _analyze(synth.clean_spec(seed=1000 + s), tmp, cfg, n_perm)
        kind = v["periodicity"]["kind"]
        is_flagged = kind in {"periodic", "sparse", "mixed"}
        flagged += int(is_flagged)
        false_hitch_total += len(det)
        clean_rows.append({"seed": 1000 + s, "kind": kind, "n_false_hitches": len(det)})
    fp_rate = flagged / n_seeds
    results["clean"] = clean_rows
    results["false_positive_rate"] = fp_rate
    results["clean_false_hitches_mean"] = false_hitch_total / n_seeds
    log(f"[selftest] clean false-positive rate = {fp_rate:.4f} "
        f"({flagged}/{n_seeds}); mean false hitches/run = {false_hitch_total/n_seeds:.3f}")
    _check(results, "clean.no_periodic_flag", fp_rate == 0.0,
           f"false-positive rate={fp_rate} ({flagged}/{n_seeds})")

    log("[selftest] warm-up exclusion ...")
    spec = synth.periodic_spec(seed=99, duration_s=120.0)
    spec.schedule_from_t0 = True
    spec.warmup_s = 20.0
    v, gt, det, gt_times, we = _analyze(spec, tmp, cfg, n_perm)
    all_events = [e.t for e in v.get("_events", [])]
    pre = [t for t in all_events if t < we]
    n_gt_pre = len([h for h in gt["hitches"] if h["t"] < we])
    n_gt_post = len(gt_times)
    results["warmup"] = {"n_gt_pre": n_gt_pre, "n_gt_post": n_gt_post,
                         "n_det_pre": len(pre), "n_det_post": len(det)}
    log(f"[selftest] warmup: gt pre/post={n_gt_pre}/{n_gt_post}, "
        f"detected pre/post={len(pre)}/{len(det)}")
    _check(results, "warmup.no_pre_warmup_events", len(pre) == 0,
           f"{len(pre)} events before warmup_end")
    _check(results, "warmup.pre_warmup_excluded", n_gt_pre > 0 and len(pre) == 0,
           f"gt_pre={n_gt_pre}")

    log("[selftest] sensitivity table (K, FLOOR) ...")
    results["sensitivity"] = _sensitivity(tmp, cfg)
    for row in results["sensitivity"]:
        log(f"    {row['scenario']:<9} {row['axis']}={row['value']:<6} "
            f"precision={row['precision']:.3f} recall={row['recall']:.3f} "
            f"clean_false_pos={row['false_positives']}")

    if not keep and workdir is None:
        shutil.rmtree(tmp, ignore_errors=True)
        results["workdir"] = "(removed)"
    n_pass = sum(1 for a in results["assertions"] if a["passed"])
    results["n_assertions"] = len(results["assertions"])
    results["n_passed"] = n_pass
    log(f"[selftest] assertions: {n_pass}/{len(results['assertions'])} passed; "
        f"overall={'PASS' if results['passed'] else 'FAIL'}")
    return results


def _sensitivity(workdir, base: HitchConfig):
    from . import hitches as hitch_mod

    clear = synth.periodic_spec(seed=321, duration_s=160.0)
    crd = load_rundir(_gen(clear, workdir, "sens-clear"))

    marginal = synth.periodic_spec(seed=322, duration_s=160.0)
    marginal.periodic_ms = 18.0        # just above the default FLOOR (13.9 ms)
    marginal.noise_spike_ms = 14.0     # near-floor noise that a low FLOOR would flag
    marginal.noise_spike_rate = 12.0
    mrd = load_rundir(_gen(marginal, workdir, "sens-marginal"))

    clean = synth.clean_spec(seed=654, duration_s=160.0)
    nrd = load_rundir(_gen(clean, workdir, "sens-clean"))
    nwe = nrd.warmup_end()

    runs = [("clear", crd, _gt(crd, clear)), ("marginal", mrd, _gt(mrd, marginal))]

    rows = []
    configs = []
    for k in (2.0, 2.5, 3.0, 3.5, 4.0):
        configs.append(("K", k, dataclasses.replace(base, k=k, floor_ms=0.0).resolve()))
    for fl in (10.0, 13.9, 17.5, 21.0, 25.0):
        configs.append(("FLOOR_ms", fl,
                        dataclasses.replace(base, floor_ms=fl, floor_min_ms=fl).resolve()))

    for scenario, rd, gt_times in runs:
        for axis, value, c in configs:
            dt = _post_warmup(hitch_mod.detect(rd.t, rd.frametime_ms, c)["events"],
                              rd.warmup_end())
            prec, rec = precision_recall(dt, gt_times)
            fp = len(_post_warmup(hitch_mod.detect(nrd.t, nrd.frametime_ms, c)["events"], nwe))
            rows.append({"scenario": scenario, "axis": axis, "value": value,
                         "precision": prec, "recall": rec, "false_positives": fp})
    return rows


def _gen(spec, workdir, name):
    path = os.path.join(workdir, name)
    gt = synth.generate(spec, path)
    spec._gt = gt
    return path


def _gt(rd, spec):
    return [h["t"] for h in spec._gt["hitches"] if h["t"] >= rd.warmup_end()]
