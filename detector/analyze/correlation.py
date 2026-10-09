"""Correlation of *every* numeric signal column around each hitch, generically.

For each ``<name>.csv`` in the run-dir and each numeric column in it we compare the
signal in a window centred on every hitch against the same-length window at many
random non-hitch ("control") times. Fast signals (median sample interval <= 1 s) use
a +-500 ms window; slow signals use +-2 s.

Per (signal, column, feature) with ``feature in {mean, min, max, step}`` we report
the hitch-window value vs the control distribution: a z-score, Cohen's d, Cliff's
delta, and a Mann-Whitney p-value. ``step`` is the (second half - first half) mean
across the window, so a *step change* in a clock / pstate / power signal at the
hitch is caught even when the window mean is diluted.

Ranking is by **effect size** (|Cliff's delta|), not by the unbounded z: z is capped
at ``CORR_Z_CAP`` and pairs whose control spread is effectively zero are flagged
(``degenerate_control``) rather than allowed to dominate with z~1e13. Every row also
carries a Benjamini-Hochberg FDR ``q_value`` across all rows.

Text streams (``<name>.log``) are handled the same way at the line level: every
distinct normalised template is counted near hitches vs near controls.
"""

from __future__ import annotations

import re

import numpy as np

from .config import (CORR_CONTROL_MULT, CORR_FAST_WINDOW_S, CORR_FDR_Q,
                     CORR_MIN_CONTROL, CORR_MIN_CONTROL_SD_FRAC, CORR_SLOW_DT_S,
                     CORR_SLOW_WINDOW_S, CORR_Z_CAP, RNG_SEED)

_NUM = re.compile(r"(0x[0-9a-fA-F]+|\d+(?:\.\d+)?)")

FEATURES = ("mean", "min", "max", "step")


def _window_features(t: np.ndarray, v: np.ndarray, center: float, half: float):
    """Return (mean, min, max, step) over ``[center-half, center+half]``, NaN-aware."""
    lo = int(np.searchsorted(t, center - half, side="left"))
    hi = int(np.searchsorted(t, center + half, side="right"))
    if hi - lo < 1:
        return None
    seg = np.asarray(v[lo:hi], dtype=float)
    finite = np.isfinite(seg)
    if not finite.any():
        return None
    vals = seg[finite]
    mean = float(np.mean(vals))
    mn = float(np.min(vals))
    mx = float(np.max(vals))
    step = float("nan")
    if seg.size >= 2:
        mid = seg.size // 2
        a = seg[:mid]
        b = seg[mid:]
        a = a[np.isfinite(a)]
        b = b[np.isfinite(b)]
        if a.size and b.size:
            step = float(np.mean(b) - np.mean(a))
    return mean, mn, mx, step


def _cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if a.size < 2 or b.size < 2:
        return float("nan")
    na, nb = a.size, b.size
    pooled = np.sqrt(((na - 1) * a.var(ddof=1) + (nb - 1) * b.var(ddof=1)) / (na + nb - 2))
    if pooled == 0:
        return 0.0 if a.mean() == b.mean() else float(np.sign(a.mean() - b.mean()) * 10.0)
    return float((a.mean() - b.mean()) / pooled)


def _midranks(x: np.ndarray) -> np.ndarray:
    """Average ranks (ties share the mean rank) -- required for a correct delta."""
    x = np.asarray(x, dtype=float)
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty(x.size)
    sx = x[order]
    i = 0
    while i < x.size:
        j = i
        while j + 1 < x.size and sx[j + 1] == sx[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return ranks


def _cliffs_delta(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if a.size == 0 or b.size == 0:
        return float("nan")
    # Rank-based Cliff's delta = (P(a>b) - P(a<b)) = 2*U_a/(n*m) - 1, where
    # U_a = R_a - n(n+1)/2 is the Mann-Whitney U of a against b. Midranks make
    # ties contribute 0 (essential for signals that are mostly a constant value).
    n = a.size
    m = b.size
    ranks = _midranks(np.concatenate([a, b]))
    u_a = ranks[:n].sum() - n * (n + 1) / 2.0
    return float(2.0 * u_a / (n * m) - 1.0)


def _bh_fdr(pvals) -> np.ndarray:
    """Benjamini-Hochberg q-values (NaN-safe, monotone)."""
    p = np.asarray(pvals, dtype=float)
    n = p.size
    q = np.full(n, np.nan)
    ok = np.isfinite(p)
    m = int(ok.sum())
    if m == 0:
        return q
    idx = np.flatnonzero(ok)
    order = idx[np.argsort(p[idx])]
    ranked = p[order]
    qv = ranked * m / (np.arange(m) + 1)
    qv = np.minimum.accumulate(qv[::-1])[::-1]
    q[order] = np.clip(qv, 0.0, 1.0)
    return q


def _sample_control_times(hitch_times, t0, t1, m, rng):
    if t1 <= t0:
        return np.empty(0)
    guard = 1.5
    out = []
    tries = 0
    while len(out) < m and tries < m * 50:
        tries += 1
        cand = rng.uniform(t0, t1)
        if hitch_times.size and np.min(np.abs(hitch_times - cand)) < guard:
            continue
        out.append(cand)
    return np.asarray(out)


def _mannwhitney_p(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    a = a[np.isfinite(a)]
    b = b[np.isfinite(b)]
    if a.size < 3 or b.size < 3:
        return float("nan")
    try:
        from scipy.stats import mannwhitneyu
        return float(mannwhitneyu(a, b, alternative="two-sided").pvalue)
    except Exception:
        return float("nan")


def correlate_signals(rundir, hitch_times, warmup_end, t_end, seed: int = RNG_SEED) -> list:
    """Ranked enrichment table for every numeric column of every signal CSV."""
    hitch_times = np.asarray(sorted(hitch_times), dtype=float)
    rng = np.random.default_rng(seed)
    m = max(CORR_MIN_CONTROL, CORR_CONTROL_MULT * max(1, hitch_times.size))
    controls = _sample_control_times(hitch_times, warmup_end, t_end, m, rng)
    table = []

    for name, sig in rundir.signals.items():
        if len(sig.t) < 2:
            continue
        dt = sig.dt_median()
        slow = np.isfinite(dt) and dt > CORR_SLOW_DT_S
        half = CORR_SLOW_WINDOW_S if slow else CORR_FAST_WINDOW_S
        for col, v in sig.columns.items():
            v = np.asarray(v, dtype=float)
            if not np.isfinite(v).any():
                continue
            obs, ctl = [], []
            for t in hitch_times:
                f = _window_features(sig.t, v, t, half)
                if f is not None:
                    obs.append(f)
            for t in controls:
                f = _window_features(sig.t, v, t, half)
                if f is not None:
                    ctl.append(f)
            if len(obs) < 3 or len(ctl) < 3:
                continue
            obs = np.asarray(obs, dtype=float)
            ctl = np.asarray(ctl, dtype=float)
            for fi, fname in enumerate(FEATURES):
                o = obs[:, fi]
                cc = ctl[:, fi]
                o = o[np.isfinite(o)]
                cc = cc[np.isfinite(cc)]
                if o.size < 3 or cc.size < 3:
                    continue
                # A feature that is constant across hitches AND controls carries no
                # information -- drop it (this is what produced z~1e13 rows before).
                if np.ptp(np.concatenate([o, cc])) == 0.0:
                    continue
                sd = float(np.std(cc, ddof=1)) if cc.size > 1 else 0.0
                cmean = float(np.mean(cc))
                degenerate = sd <= max(abs(cmean) * CORR_MIN_CONTROL_SD_FRAC, 1e-12)
                raw_z = (float(np.mean(o)) - cmean) / sd if sd > 0 else 0.0
                z = float(np.clip(raw_z, -CORR_Z_CAP, CORR_Z_CAP))
                d = _cohens_d(o, cc)
                cliff = _cliffs_delta(o, cc)
                ratio = (float(np.mean(o)) / cmean if abs(cmean) > 1e-12 else float("nan"))
                table.append({
                    "signal": name,
                    "column": col,
                    "feature": fname,
                    "window_s": half,
                    "slow": bool(slow),
                    "n_hitch_windows": int(o.size),
                    "n_control_windows": int(cc.size),
                    "hitch_mean": float(np.mean(o)),
                    "control_mean": cmean,
                    "control_sd": sd,
                    "delta": float(np.mean(o) - cmean),
                    "z": z,
                    "z_uncapped": float(raw_z) if np.isfinite(raw_z) else None,
                    "degenerate_control": bool(degenerate),
                    "cohens_d": float(d),
                    "cliffs_delta": float(cliff),
                    "enrichment": float(ratio),
                    "p_value": _mannwhitney_p(o, cc),
                })

    q = _bh_fdr([r["p_value"] for r in table])
    for r, qi in zip(table, q):
        r["q_value"] = float(qi) if np.isfinite(qi) else None
        r["significant_fdr"] = bool(np.isfinite(qi) and qi < CORR_FDR_Q)
    # Rank by effect size (robust to scale), tie-broken by |z| then |delta|.
    table.sort(key=lambda r: (abs(r["cliffs_delta"]) if np.isfinite(r["cliffs_delta"]) else -1,
                              abs(r["z"]), abs(r["delta"])), reverse=True)
    return table


def _template(text: str) -> str:
    return _NUM.sub("#", text.strip())[:160]


def correlate_logs(rundir, hitch_times, warmup_end, t_end, seed: int = RNG_SEED) -> list:
    """Ranked enrichment of normalised log-line templates near hitches vs controls."""
    hitch_times = np.asarray(sorted(hitch_times), dtype=float)
    rng = np.random.default_rng(seed)
    m = max(CORR_MIN_CONTROL, CORR_CONTROL_MULT * max(1, hitch_times.size))
    controls = _sample_control_times(hitch_times, warmup_end, t_end, m, rng)
    half = CORR_FAST_WINDOW_S
    out = []
    for name, log in rundir.logs.items():
        if len(log.t) == 0:
            continue
        hitch_counts, ctrl_counts = {}, {}
        for t in hitch_times:
            lo = int(np.searchsorted(log.t, t - half, side="left"))
            hi = int(np.searchsorted(log.t, t + half, side="right"))
            for i in range(lo, hi):
                k = _template(log.lines[i])
                hitch_counts[k] = hitch_counts.get(k, 0) + 1
        for t in controls:
            lo = int(np.searchsorted(log.t, t - half, side="left"))
            hi = int(np.searchsorted(log.t, t + half, side="right"))
            for i in range(lo, hi):
                k = _template(log.lines[i])
                ctrl_counts[k] = ctrl_counts.get(k, 0) + 1
        nh = max(1, hitch_times.size)
        nc = max(1, controls.size)
        keys = set(hitch_counts) | set(ctrl_counts)
        for k in keys:
            hc = hitch_counts.get(k, 0)
            cc = ctrl_counts.get(k, 0)
            rate_h = hc / nh
            rate_c = cc / nc
            if hc == 0 and cc == 0:
                continue
            enrich = (rate_h / rate_c) if rate_c > 0 else float("inf")
            out.append({
                "log": name,
                "template": k,
                "near_hitch": int(hc),
                "near_control": int(cc),
                "per_hitch": rate_h,
                "per_control": rate_c,
                "enrichment": float(enrich),
                "delta": float(rate_h - rate_c),
            })
    out.sort(key=lambda r: (r["delta"], r["near_hitch"]), reverse=True)
    return out
