"""Periodicity of the hitch-event series.

Three views, as the spec asks:

1. **Autocorrelation** of the binned (default 100 ms) hitch-count series (FFT based).
2. **Spectrum** via a Lomb-Scargle periodogram (``scipy.signal.lombscargle``) on the
   binned series, reported alongside a plain FFT periodogram.
3. **Interval histogram** with mode detection.

Significance uses a *uniform-timing (Poisson) null*: we drop the same number of
events uniformly at random in the same window, rebin, and recompute the in-band peak
power. ``p = (1 + #null >= observed) / (1 + n_perm)`` with ``p < 0.01`` required.

Why not a shuffled-interval null? For a near-constant interval (a perfect 4 s rhythm)
shuffling the intervals reproduces the same rhythm, so that null can never reject.
The uniform-timing null is the correct "periodic vs random" test.

Bands (evaluated independently, so a *mixed* run can report both):

* **steady band** 0.5-10 s (spec: "steady rhythm < 10 s, esp. ~4 s")
* **sparse band** 30-90 s (spec: "sparse 30-90 s hitches"); only assessable on a
  post-warm-up window >= 5 min (300 s), otherwise the verdict is loudly caveated.

Harmonic resolution: an impulse train's periodogram peaks at ``P, P/2, P/3, ...`` in
period, so the argmax can land on a harmonic (e.g. 2 s for a true 4 s rhythm). We pick
the *largest* multiple of the detected period that still has a strong in-band peak --
that is the fundamental. If a significant steady component exists, hitches not
explained by its phase are re-searched in the sparse band (``sparse_residual``).
"""

from __future__ import annotations

import numpy as np

from .config import (MIN_WINDOW_FOR_SPARSE_S, PERIOD_MIN_S, PERMUTATIONS, RNG_SEED,
                     SPARSE_PERIOD_MAX_S, SPARSE_PERIOD_MIN_S, STEADY_MAX_S)

BIN_S = 0.1
STEADY_LO, STEADY_HI = PERIOD_MIN_S, STEADY_MAX_S
SPARSE_LO, SPARSE_HI = SPARSE_PERIOD_MIN_S, SPARSE_PERIOD_MAX_S
P_THRESHOLD = 0.01


def _bin_series(t_ev, t0, t1, bin_s: float = BIN_S):
    nbins = max(1, int(np.ceil((t1 - t0) / bin_s)))
    counts = np.zeros(nbins)
    if t_ev.size:
        idx = np.clip(np.floor((t_ev - t0) / bin_s).astype(int), 0, nbins - 1)
        np.add.at(counts, idx, 1.0)
    centers = t0 + (np.arange(nbins) + 0.5) * bin_s
    return counts, centers, nbins


def _spectrum(counts, bin_s: float):
    y = counts - counts.mean()
    power = np.abs(np.fft.rfft(y)) ** 2
    freqs = np.fft.rfftfreq(counts.size, d=bin_s)
    with np.errstate(divide="ignore"):
        periods = np.where(freqs > 0, 1.0 / freqs, np.inf)
    keep = np.isfinite(periods) & (periods >= PERIOD_MIN_S) & (periods <= SPARSE_HI * 1.5)
    order = np.argsort(periods[keep])
    return periods[keep][order], power[keep][order]


def _autocorr(counts, bin_s: float):
    y = counts - counts.mean()
    n = counts.size
    ac = np.fft.irfft(np.abs(np.fft.rfft(y)) ** 2, n=n)
    if ac[0] > 0:
        ac = ac / ac[0]
    lags = np.arange(n) * bin_s
    keep = (lags >= PERIOD_MIN_S) & (lags <= SPARSE_HI * 1.5)
    return lags[keep], ac[keep]


def _band_peak(periods, power, lo, hi):
    m = (periods >= lo) & (periods <= hi)
    if not np.any(m):
        return None, 0.0
    sub = np.nan_to_num(power[m], nan=0.0)
    j = int(np.argmax(sub))
    return float(periods[m][j]), float(sub[j])


def _resolve_fundamental(periods, power, pk, peak_power, hi, frac=0.4):
    """Spectral fallback: prefer the largest multiple of ``pk`` with a strong peak."""
    if not pk or pk <= 0:
        return pk
    best = pk
    for m in (2, 3, 4):
        cand = pk * m
        if cand > hi:
            break
        j = int(np.argmin(np.abs(periods - cand)))
        if abs(periods[j] - cand) <= 0.03 * cand and power[j] >= frac * peak_power:
            best = max(best, float(periods[j]))
    return best


def _estimate_period(times, lo, hi, periods, power, pk, pp):
    """Fundamental period from the in-band inter-hitch intervals.

    An impulse train's spectrum peaks at P, P/2, P/3, ... so an argmax is harmonic-
    ambiguous; the interval distribution has no such ambiguity. We take the median
    in-band interval and snap it to a nearby spectral peak when one exists. Only if
    there are too few in-band intervals do we fall back to the spectrum.
    """
    if times.size >= 2:
        ivs = np.diff(np.sort(times))
        inb = ivs[(ivs >= lo) & (ivs <= hi)]
        if inb.size >= 3:
            cand = float(np.median(inb))
            if periods.size:
                j = int(np.argmin(np.abs(periods - cand)))
                if abs(periods[j] - cand) <= 0.05 * cand and power[j] >= 0.3 * pp:
                    cand = float(periods[j])
            return cand, "interval"
    return _resolve_fundamental(periods, power, pk, pp, hi), "spectral"


def _peak_error(times, lo, hi, n_boot=80, seed=RNG_SEED):
    if times.size < 6:
        return float("nan")
    rng = np.random.default_rng(seed)
    peaks = []
    for _ in range(n_boot):
        sample = np.sort(rng.choice(times, times.size, replace=True))
        c, _, _ = _bin_series(sample, sample.min(), sample.max())
        p, pw = _spectrum(c, BIN_S)
        pk, pp = _band_peak(p, pw, lo, hi)
        if pk is None:
            continue
        est, _ = _estimate_period(sample, lo, hi, p, pw, pk, pp)
        if est is not None:
            peaks.append(est)
    if len(peaks) < 3:
        return float("nan")
    return float(np.std(peaks))


def _fraction_explained(times, period_s, tol_frac=0.1):
    if times.size == 0 or not period_s or period_s <= 0:
        return float("nan")
    t0 = times.min()
    phases = (times - t0) % period_s
    counts, edges = np.histogram(phases, bins=36, range=(0, period_s))
    j = int(np.argmax(counts))
    center = 0.5 * (edges[j] + edges[j + 1])
    tol = max(tol_frac * period_s, 0.1)
    d = np.abs(phases - center)
    d = np.minimum(d, period_s - d)
    return float(np.mean(d <= tol))


def _ls_event_peak(times, mags):
    if times.size < 4:
        return None, 0.0
    try:
        from scipy.signal import lombscargle
    except Exception:
        return None, 0.0
    periods = np.logspace(np.log10(PERIOD_MIN_S), np.log10(SPARSE_HI), 300)
    y = np.asarray(mags, dtype=float)
    yc = y - y.mean()
    if np.allclose(yc, 0):
        return None, 0.0
    try:
        p = np.nan_to_num(lombscargle(times - times[0], yc, 2 * np.pi / periods,
                                      normalize=True), nan=0.0)
    except Exception:
        return None, 0.0
    j = int(np.argmax(p))
    return float(periods[j]), float(p[j])


def _uniform_null(t_ev, t0, t1, lo, hi, n_perm, seed):
    if t_ev.size == 0:
        return np.zeros(n_perm)
    rng = np.random.default_rng(seed)
    stats = np.empty(n_perm)
    for k in range(n_perm):
        rt = np.sort(rng.uniform(t0, t1, t_ev.size))
        c, _, _ = _bin_series(rt, t0, t1)
        p, pw = _spectrum(c, BIN_S)
        _, stats[k] = _band_peak(p, pw, lo, hi)
    return stats


def _pvalue(observed, null):
    null = np.asarray(null, dtype=float)
    return float((1.0 + np.sum(null >= observed)) / (1.0 + null.size))


def _band_result(times, t0, t1, lo, hi, n_perm, seed):
    if times.size < 4:
        return None
    c, _, _ = _bin_series(times, t0, t1)
    periods, power = _spectrum(c, BIN_S)
    pk, pp = _band_peak(periods, power, lo, hi)
    if pk is None:
        return None
    period, source = _estimate_period(times, lo, hi, periods, power, pk, pp)
    null = _uniform_null(times, t0, t1, lo, hi, n_perm, seed)
    p = _pvalue(pp, null)
    return {
        "period_s": period,
        "spectral_peak_s": pk,
        "period_source": source,
        "power": pp,
        "p_value": p,
        "period_err_s": _peak_error(times, lo, hi),
        "fraction_explained": _fraction_explained(times, period),
        "significant": bool(p < P_THRESHOLD),
        "n_events": int(times.size),
    }


def _intervals(times):
    if times.size < 2:
        return None
    ivs = np.diff(np.sort(times))
    counts, edges = np.histogram(ivs, bins=min(25, max(5, ivs.size)))
    j = int(np.argmax(counts))
    return {
        "edges_s": edges.tolist(),
        "counts": counts.tolist(),
        "mode_s": float(0.5 * (edges[j] + edges[j + 1])),
        "median_s": float(np.median(ivs)),
        "quantiles_s": {q: float(np.percentile(ivs, q)) for q in (10, 25, 50, 75, 90)},
    }


def analyze_periodicity(events, warmup_end: float, t_end: float,
                        n_perm: int = PERMUTATIONS, seed: int = RNG_SEED) -> dict:
    """Return the periodicity verdict for hitch events after ``warmup_end``."""
    ev = [e for e in events if e.t >= warmup_end]
    times = np.asarray(sorted(e.t for e in ev), dtype=float)
    mags = np.asarray([e.magnitude_ms for e in ev], dtype=float)
    window_s = float(max(0.0, t_end - warmup_end))

    result = {
        "n_events": int(times.size),
        "window_s": window_s,
        "window_min": window_s / 60.0,
        "sparse_assessable": bool(window_s >= MIN_WINDOW_FOR_SPARSE_S),
        "kind": "insufficient",
        "steady": None,
        "sparse": None,
        "sparse_residual": None,
        "interval_hist": _intervals(times),
        "autocorr_peak": None,
        "lombscargle_peak": None,
        "warnings": [],
    }

    if not result["sparse_assessable"]:
        result["warnings"].append(
            f"post-warm-up window {window_s/60.0:.1f} min < 5 min: sparse (30-90 s) "
            "periodicity cannot be assessed")
    if times.size < 4:
        result["warnings"].append(
            f"only {times.size} hitch event(s): periodic verdict unreliable")
        return result

    c, _, _ = _bin_series(times, warmup_end, t_end)
    lags, ac = _autocorr(c, BIN_S)
    ac_period, ac_power = _band_peak(lags, ac, STEADY_LO, SPARSE_HI)
    result["autocorr_peak"] = {"period_s": ac_period, "power": ac_power}
    ls_period, ls_power = _ls_event_peak(times, mags)
    result["lombscargle_peak"] = {"period_s": ls_period, "power": ls_power}

    result["steady"] = _band_result(times, warmup_end, t_end, STEADY_LO, STEADY_HI,
                                    n_perm, seed)
    result["sparse"] = _band_result(times, warmup_end, t_end, SPARSE_LO, SPARSE_HI,
                                    n_perm, seed + 1)
    if result["sparse"] is not None:
        result["sparse"]["assessable"] = result["sparse_assessable"]

    steady_sig = bool(result["steady"] and result["steady"]["significant"])

    if steady_sig:
        P = result["steady"]["period_s"]
        phases = (times - times.min()) % P
        tol = max(0.1 * P, 0.1)
        d = np.abs(phases - _best_phase(phases, P))
        d = np.minimum(d, P - d)
        residual = times[d > tol]
        if residual.size >= 4:
            res = _band_result(residual, warmup_end, t_end, SPARSE_LO, SPARSE_HI,
                               n_perm, seed + 2)
            if res is not None:
                res["assessable"] = result["sparse_assessable"]
                res["n_residual"] = int(residual.size)
                result["sparse_residual"] = res

    sparse_sig = bool(result["sparse"] and result["sparse"]["significant"]
                      and result["sparse_assessable"])
    resid_sig = bool(result["sparse_residual"] and result["sparse_residual"]["significant"]
                     and result["sparse_assessable"])

    if steady_sig and (sparse_sig or resid_sig):
        result["kind"] = "mixed"
    elif steady_sig:
        result["kind"] = "periodic"
    elif sparse_sig or resid_sig:
        result["kind"] = "sparse"
    else:
        result["kind"] = "aperiodic"
    return result


def _best_phase(phases, period_s):
    counts, edges = np.histogram(phases, bins=36, range=(0, period_s))
    j = int(np.argmax(counts))
    return 0.5 * (edges[j] + edges[j + 1])


def spectrum_and_autocorr(events, warmup_end: float, t_end: float):
    """Return the binned-series spectrum and autocorrelation for plotting/export."""
    times = np.asarray(sorted(e.t for e in events if e.t >= warmup_end), dtype=float)
    if times.size < 2:
        return None
    c, _, _ = _bin_series(times, warmup_end, t_end)
    periods, power = _spectrum(c, BIN_S)
    lags, ac = _autocorr(c, BIN_S)
    return {"periods": periods, "power": power, "lags": lags, "autocorr": ac}
