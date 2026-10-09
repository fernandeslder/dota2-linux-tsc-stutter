"""Frametime statistics: percentiles, 1%/0.1% lows, frame-drop fraction, and the
run-to-run comparison helpers (effect size, bootstrap CI).

Definitions (documented so ``verdict.json`` is unambiguous):

* ``pXX_ms``           -- the XXth percentile of per-frame frametimes (ms).
* ``fps_1pct_low``     -- mean frametime of the slowest 1% of frames, converted to
                          fps (``1000 / mean_ms``). Same for the 0.1% low.
* ``frame_drop_frac``  -- fraction of frames whose frametime exceeds
                          ``1000 / (fps_cap * drop_frac)`` (i.e. instantaneous fps
                          below ``drop_frac`` x the cap). Default drop_frac = 0.5.
"""

from __future__ import annotations

import numpy as np


def percentiles_ms(frametime_ms: np.ndarray, qs=(50, 95, 99)):
    if frametime_ms.size == 0:
        return {f"p{q}_ms": float("nan") for q in qs}
    vals = np.percentile(frametime_ms, qs)
    return {f"p{q}_ms": float(v) for q, v in zip(qs, vals)}


def fps_low(frametime_ms: np.ndarray, frac: float):
    """Slowest ``frac`` fraction of frames -> (mean_ms, fps)."""
    if frametime_ms.size == 0 or frac <= 0:
        return float("nan"), float("nan")
    n = max(1, int(np.ceil(frametime_ms.size * frac)))
    slowest = np.sort(frametime_ms)[-n:]
    mean_ms = float(np.mean(slowest))
    return mean_ms, float(1000.0 / mean_ms) if mean_ms > 0 else float("inf")


def frame_drop_fraction(frametime_ms: np.ndarray, fps_cap: float, drop_frac: float = 0.5):
    if frametime_ms.size == 0 or fps_cap <= 0:
        return float("nan")
    threshold_ms = 1000.0 / (fps_cap * drop_frac)
    return float(np.mean(frametime_ms > threshold_ms))


def mean_fps(frametime_ms: np.ndarray) -> float:
    if frametime_ms.size == 0:
        return float("nan")
    m = float(np.mean(frametime_ms))
    return float(1000.0 / m) if m > 0 else float("inf")


def summary(frametime_ms: np.ndarray, fps_cap: float) -> dict:
    out = {}
    out.update(percentiles_ms(frametime_ms, (50, 95, 99)))
    m1, f1 = fps_low(frametime_ms, 0.01)
    m01, f01 = fps_low(frametime_ms, 0.001)
    out["fps_1pct_low"] = f1
    out["fps_0.1pct_low"] = f01
    out["mean_fps"] = mean_fps(frametime_ms)
    out["frame_drop_frac"] = frame_drop_fraction(frametime_ms, fps_cap)
    out["n_frames"] = int(frametime_ms.size)
    return out


def cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    """Pooled-SD standardised mean difference (a - b); sign = a slower/higher."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if a.size < 2 or b.size < 2:
        return float("nan")
    na, nb = a.size, b.size
    va, vb = a.var(ddof=1), b.var(ddof=1)
    pooled = np.sqrt(((na - 1) * va + (nb - 1) * vb) / (na + nb - 2))
    if pooled == 0:
        return 0.0 if a.mean() == b.mean() else float(np.sign(a.mean() - b.mean()) * np.inf)
    return float((a.mean() - b.mean()) / pooled)


def cliffs_delta(a: np.ndarray, b: np.ndarray) -> float:
    """Non-parametric effect size in [-1, 1] (P(a>b) - P(a<b))."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if a.size == 0 or b.size == 0:
        return float("nan")
    gt = lt = 0
    for x in a:
        gt += int(np.sum(x > b))
        lt += int(np.sum(x < b))
    n = a.size * b.size
    return float((gt - lt) / n)


def bootstrap_ci_diff(a: np.ndarray, b: np.ndarray, n_boot: int = 5000,
                      alpha: float = 0.05, seed: int = 12345):
    """Bootstrap CI for mean(a) - mean(b), resampling each group independently."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if a.size == 0 or b.size == 0:
        return float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    diff = float(a.mean() - b.mean())
    if a.size < 2 or b.size < 2:
        return diff, float("nan"), float("nan")
    boots = np.empty(n_boot)
    for i in range(n_boot):
        boots[i] = rng.choice(a, a.size).mean() - rng.choice(b, b.size).mean()
    lo, hi = np.percentile(boots, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return diff, float(lo), float(hi)
