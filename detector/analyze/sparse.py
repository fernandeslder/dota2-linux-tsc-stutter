"""Explicit sparse-hitch assessment, independent of the periodicity null.

The sparse *band* permutation test in :mod:`periodicity` is underpowered when the
sparse rhythm contributes only ~10-15 events: the uniform-timing null cannot reach
``p < 0.01`` against the real background of vkcube jitter (see
``docs/VALIDATION-e2e.md`` §3 / bug B2). This module answers the sparse question
*directly* and cheaply:

* **Which hitches are "sparse"?** Severe stalls: a candidate is a post-warm-up
  primary hitch with ``magnitude_ms >= max(1.5*FLOOR, FLOOR + 6 ms)``. The leftover
  vkcube jitter sits just above FLOOR, whereas real sparse stalls are much larger, so
  this gate separates them without any periodicity assumption. If a significant
  *steady* rhythm exists, hitches explained by its phase are removed first, so a mixed
  4 s + 45 s run is reduced to its sparse residual.

* **Rate** of sparse candidates per minute, with a Poisson bootstrap CI, plus the
  interval quantiles and CV.

* **Sparse-regular test**: take the inter-candidate intervals that fall in the
  sparse band ``[20, 100] s``; find the histogram mode; a *tight* modal cluster
  (>= 4 intervals, within +-25 % of the mode, CV <= 0.15, >= 50 % of the band
  intervals) is a regular sparse rhythm. Period = median of the cluster.

Verdict field: ``assessment`` in ``none | irregular | regular`` with
``period_s``/``label`` when regular, plus sample-size caveats. Validated by
replaying ``runs/validate-sparse-*`` (regular ~45 s) and ``runs/validate-clean-*``
(no regular sparse rhythm), and on synthetic traces.
"""

from __future__ import annotations

import numpy as np

from .config import (RNG_SEED, SPARSE_CV_MAX, SPARSE_INTERVAL_MAX_S,
                     SPARSE_INTERVAL_MIN_S, SPARSE_MIN_EVENTS,
                     SPARSE_MIN_INTERVALS, SPARSE_MIN_MODE_FRACTION,
                     SPARSE_MODE_TOL, SPARSE_RATE_BOOT, SPARSE_SEVERITY_MULT,
                     SPARSE_SEVERITY_PLUS_MS)

_PHASE_TOL_FRAC = 0.1


def sparse_severity_ms(cfg) -> float:
    """Magnitude threshold above which a primary hitch counts as a sparse candidate."""
    return max(SPARSE_SEVERITY_MULT * cfg.floor_ms,
               cfg.floor_ms + SPARSE_SEVERITY_PLUS_MS)


def _steady_residual(times: np.ndarray, period_s: float) -> np.ndarray:
    """Hitches *not* explained by a steady ``period_s`` phase (tol = +-10 %)."""
    if times.size == 0 or not period_s or period_s <= 0:
        return times
    t0 = times.min()
    phases = (times - t0) % period_s
    counts, edges = np.histogram(phases, bins=36, range=(0, period_s))
    j = int(np.argmax(counts))
    center = 0.5 * (edges[j] + edges[j + 1])
    tol = max(_PHASE_TOL_FRAC * period_s, 0.1)
    d = np.abs(phases - center)
    d = np.minimum(d, period_s - d)
    return times[d > tol]


def _robust_steady_period(times: np.ndarray, lo: float = 0.5, hi: float = 10.0):
    """Dominant steady period from the *modal* inter-hitch interval.

    The interval median is fragile under jitter/hitches (a mixed 4 s + 45 s run over
    a real noisy capture went 4.1 s -> 3.55 s, which broke the phase residual); the
    histogram mode is stable. Returns None when there are too few intervals.
    """
    if times.size < 9:
        return None
    iv = np.diff(np.sort(times))
    inb = iv[(iv >= lo) & (iv <= hi)]
    if inb.size < 8:
        return None
    edges = np.arange(lo, hi + 0.001, 0.1)
    counts, _ = np.histogram(inb, bins=edges)
    j = int(np.argmax(counts))
    if counts[j] < 4:
        return None
    mode = 0.5 * (edges[j] + edges[j + 1])
    cluster = inb[np.abs(inb - mode) <= 0.15 * mode]
    return float(np.median(cluster)) if cluster.size >= 4 else float(mode)


def _interval_stats(iv: np.ndarray) -> dict:
    if iv.size == 0:
        return {"count": 0}
    q = np.percentile(iv, [10, 25, 50, 75, 90])
    return {
        "count": int(iv.size),
        "min_s": float(iv.min()),
        "p10_s": float(q[0]), "p25_s": float(q[1]), "p50_s": float(q[2]),
        "p75_s": float(q[3]), "p90_s": float(q[4]),
        "max_s": float(iv.max()),
        "mean_s": float(iv.mean()),
        "cv": float(iv.std() / iv.mean()) if iv.mean() else float("nan"),
    }


def _rate_ci(n: int, duration_min: float, n_boot: int, seed: int):
    if duration_min <= 0:
        return float("nan"), float("nan"), float("nan")
    rate = n / duration_min
    if n == 0:
        return rate, 0.0, float(np.percentile(np.random.default_rng(seed).poisson(0, n_boot), 97.5) / duration_min)
    rng = np.random.default_rng(seed)
    boots = rng.poisson(n, n_boot) / duration_min
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return rate, float(lo), float(hi)


def analyze_sparse(events, warmup_end: float, t_end: float, steady: dict | None = None,
                   cfg=None, n_boot: int = SPARSE_RATE_BOOT, seed: int = RNG_SEED) -> dict:
    """Return the explicit sparse-hitch assessment (see module docstring)."""
    if cfg is None:
        from .config import HitchConfig
        cfg = HitchConfig().resolve()

    ev = [e for e in events if e.t >= warmup_end]
    severity_ms = sparse_severity_ms(cfg)
    cand = np.asarray(sorted(e.t for e in ev if e.magnitude_ms >= severity_ms), dtype=float)
    n_primary = len(ev)

    window_s = float(max(0.0, t_end - warmup_end))
    window_min = window_s / 60.0

    residual_applied = bool(steady and steady.get("significant"))
    resid_period = None
    times = cand
    if residual_applied:
        resid_period = _robust_steady_period(cand) or steady.get("period_s") or None
        if resid_period:
            times = _steady_residual(cand, float(resid_period))
        else:
            residual_applied = False

    out = {
        "assessment": "none",
        "label": "none",
        "n_primary_hitches": int(n_primary),
        "n_sparse_candidates": int(times.size),
        "severity_min_ms": float(severity_ms),
        "residual_applied": bool(residual_applied),
        "steady_period_s": float(steady["period_s"]) if (steady and steady.get("period_s")) else None,
        "residual_period_s": float(resid_period) if residual_applied else None,
        "window_s": window_s,
        "window_min": window_min,
        "rate_per_min": float("nan"),
        "rate_ci95_per_min": [float("nan"), float("nan")],
        "rate_ci_method": "poisson-bootstrap",
        "n_boot": int(n_boot),
        "period_s": None,
        "interval_quantiles_s": _interval_stats(np.empty(0)),
        "sparse_band_intervals_s": [],
        "mode_s": None,
        "mode_cluster": {"n": 0, "cv": None, "fraction": None},
        "cv_max": SPARSE_CV_MAX,
        "mode_tol_frac": SPARSE_MODE_TOL,
        "interval_band_s": [SPARSE_INTERVAL_MIN_S, SPARSE_INTERVAL_MAX_S],
        "caveats": [],
    }

    if times.size == 0:
        out["caveats"].append("no severe isolated hitches in the window")
        _append_sample_caveats(out)
        return out

    rate, lo, hi = _rate_ci(int(times.size), window_min, n_boot, seed)
    out["rate_per_min"] = float(rate)
    out["rate_ci95_per_min"] = [float(lo), float(hi)]

    iv = np.diff(times) if times.size >= 2 else np.empty(0)
    out["interval_quantiles_s"] = _interval_stats(iv)

    siv = iv[(iv >= SPARSE_INTERVAL_MIN_S) & (iv <= SPARSE_INTERVAL_MAX_S)]
    out["sparse_band_intervals_s"] = [round(float(x), 3) for x in siv]

    if siv.size:
        edges = np.linspace(SPARSE_INTERVAL_MIN_S, SPARSE_INTERVAL_MAX_S, 21)
        counts, _ = np.histogram(siv, bins=edges)
        j = int(np.argmax(counts))
        mode = 0.5 * (edges[j] + edges[j + 1])
        out["mode_s"] = float(mode)
        cluster = siv[np.abs(siv - mode) <= SPARSE_MODE_TOL * mode]
        cv = float(cluster.std() / cluster.mean()) if cluster.size and cluster.mean() else float("nan")
        frac = float(cluster.size / siv.size)
        out["mode_cluster"] = {"n": int(cluster.size), "cv": cv, "fraction": frac}
        regular = (cluster.size >= SPARSE_MIN_INTERVALS and np.isfinite(cv)
                   and cv <= SPARSE_CV_MAX and frac >= SPARSE_MIN_MODE_FRACTION)
        if regular:
            out["assessment"] = "regular"
            out["period_s"] = float(np.median(cluster))
            out["label"] = f"regular({out['period_s']:.1f}s)"
        else:
            out["assessment"] = "irregular"
            out["label"] = "irregular"
    else:
        # severe hitches exist but none are spaced in the sparse band: the run is
        # dominated by a dense/steady rhythm, not a sparse phenomenon.
        out["assessment"] = "none"
        out["label"] = "none"

    _append_sample_caveats(out)
    return out


def _append_sample_caveats(out: dict) -> None:
    if out["window_s"] < 300.0:
        out["caveats"].append(
            f"post-warm-up window {out['window_min']:.1f} min < 5 min: sparse assessment unreliable")
    if out["n_sparse_candidates"] < SPARSE_MIN_EVENTS and out["n_sparse_candidates"] > 0:
        out["caveats"].append(
            f"only {out['n_sparse_candidates']} sparse candidate(s) (<{SPARSE_MIN_EVENTS}): "
            "rate/period estimate is uncertain")
    nb = len(out["sparse_band_intervals_s"])
    if 0 < nb < SPARSE_MIN_INTERVALS:
        out["caveats"].append(
            f"only {nb} interval(s) in the [20, 100] s band (<{SPARSE_MIN_INTERVALS}): "
            "regularity cannot be established")
