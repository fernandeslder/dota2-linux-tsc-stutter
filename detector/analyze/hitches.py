"""Hitch detection: rolling-median outlier + absolute floor, then merging.

A frame ``i`` is a hitch iff

    f_i > K * rolling_median(f, +-W)   AND   f_i > FLOOR

where the rolling median is centred on ``i`` in *time* (+-W seconds) and excludes
``i`` itself. Adjacent hitch frames whose timestamps are within ``merge_gap_ms``
(100 ms default) merge into one event; the event time is the first hitched frame,
magnitude is the max frametime, and duration is the summed excess over FLOOR.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np

from . import stats as st
from .config import HitchConfig, MIN_FRAMES_FOR_MEDIAN


@dataclass
class HitchEvent:
    t: float                 # start epoch seconds (first hitched frame)
    t_end: float             # last hitched frame time (epoch seconds)
    magnitude_ms: float      # max frametime within the event
    peak_ms: float           # alias of magnitude_ms (kept explicit in output)
    excess_ms: float         # sum of (frametime - floor) over hitched frames
    duration_ms: float       # time span of the event (t_end - t)
    n_frames: int            # number of hitched frames in the event
    severity: str = "high"   # "high" | "low"

    def to_dict(self) -> dict:
        return asdict(self)


def rolling_median(t: np.ndarray, f: np.ndarray, w_s: float,
                   min_count: int = MIN_FRAMES_FOR_MEDIAN) -> np.ndarray:
    """Centred rolling median in seconds, always excluding the centre sample.

    ``min_count`` is accepted for API stability but the centre exclusion is
    unconditional: including the centre would let a hitch raise its own baseline
    (and, on tiny windows, hide itself entirely).
    """
    n = f.size
    med = np.full(n, np.nan)
    if n == 0:
        return med
    lo = np.searchsorted(t, t - w_s, side="left")
    hi = np.searchsorted(t, t + w_s, side="right")
    for i in range(n):
        a, b = lo[i], hi[i]
        if a < i:
            seg = np.concatenate((f[a:i], f[i + 1:b]))
        else:
            seg = f[a + 1:b] if b > a else f[a:b][:0]
        med[i] = float(np.median(seg)) if seg.size else f[i]
    return med


def _merge(t: np.ndarray, f: np.ndarray, mask: np.ndarray, floor_ms: float,
           merge_gap_s: float, severity: str) -> list:
    idx = np.flatnonzero(mask)
    events = []
    if idx.size == 0:
        return events
    group = [idx[0]]
    for k in idx[1:]:
        if t[k] - t[group[-1]] <= merge_gap_s:
            group.append(k)
        else:
            events.append(_event(group, t, f, floor_ms, severity))
            group = [k]
    events.append(_event(group, t, f, floor_ms, severity))
    return events


def _event(group, t, f, floor_ms, severity) -> HitchEvent:
    ts = t[group]
    fs = f[group]
    return HitchEvent(
        t=float(ts[0]),
        t_end=float(ts[-1]),
        magnitude_ms=float(fs.max()),
        peak_ms=float(fs.max()),
        excess_ms=float(np.sum(fs - floor_ms)),
        duration_ms=float((ts[-1] - ts[0]) * 1000.0),
        n_frames=int(len(group)),
        severity=severity,
    )


def detect(t: np.ndarray, f: np.ndarray, cfg: HitchConfig | None = None) -> dict:
    """Run the full pixel-level detection.

    Returns ``{"events": [...], "low_events": [...], "median": ndarray,
    "threshold_ms": ndarray, "mask": ndarray}``.
    """
    cfg = (cfg or HitchConfig()).resolve()
    if t.size == 0:
        return {"events": [], "low_events": [], "median": np.empty(0),
                "threshold_ms": np.empty(0), "mask": np.zeros(0, dtype=bool)}
    med = rolling_median(t, f, cfg.w_s)
    threshold = np.where(np.isnan(med), np.inf, cfg.k * med)
    mask = (f > threshold) & (f > cfg.floor_ms)
    events = _merge(t, f, mask, cfg.floor_ms, cfg.merge_gap_s, "high")

    low_threshold = np.where(np.isnan(med), np.inf, cfg.k_low * med)
    low_mask = (f > low_threshold) & (f > cfg.floor_low_ms) & ~mask
    low_mask = _suppress_inside_events(low_mask, t, events)
    low_events = _merge(t, f, low_mask, cfg.floor_low_ms, cfg.merge_gap_s, "low")

    return {"events": events, "low_events": low_events, "median": med,
            "threshold_ms": threshold, "mask": mask}


def _suppress_inside_events(mask, t, events) -> np.ndarray:
    if not events:
        return mask
    out = mask.copy()
    starts = np.array([e.t for e in events])
    ends = np.array([e.t_end for e in events])
    for i in np.flatnonzero(mask):
        ti = t[i]
        if np.any((starts <= ti) & (ti <= ends)):
            out[i] = False
    return out


def intervals_s(events: list, warmup_end: float) -> np.ndarray:
    ts = np.array([e.t for e in events if e.t >= warmup_end])
    if ts.size < 2:
        return np.empty(0)
    return np.diff(np.sort(ts))


def hitch_stats(events: list, t: np.ndarray, f: np.ndarray, cfg: HitchConfig,
                warmup_end: float, fps_cap: float) -> dict:
    """Event counts/rates plus the inter-hitch interval distribution."""
    ev = [e for e in events if e.t >= warmup_end]
    n = len(ev)
    duration_s = 0.0
    if t.size:
        duration_s = float(max(0.0, (t[-1] + f[-1] / 1000.0) - warmup_end))
    per_min = (n / (duration_s / 60.0)) if duration_s > 0 else float("nan")
    worst = max(ev, key=lambda e: e.magnitude_ms) if ev else None
    ivs = intervals_s(ev, warmup_end)
    if ivs.size:
        q = np.percentile(ivs, [50, 90, 95, 99])
        hist_counts, hist_edges = np.histogram(ivs, bins=min(20, max(5, ivs.size)))
        histogram = {"edges_s": hist_edges.tolist(), "counts": hist_counts.tolist()}
        interval = {
            "count": int(ivs.size),
            "min_s": float(ivs.min()),
            "max_s": float(ivs.max()),
            "p50_s": float(q[0]), "p90_s": float(q[1]),
            "p95_s": float(q[2]), "p99_s": float(q[3]),
            "mean_s": float(ivs.mean()), "cv": float(ivs.std() / ivs.mean()) if ivs.mean() else float("nan"),
            "hist": histogram,
        }
    else:
        interval = {"count": 0, "hist": None}
    return {
        "count": n,
        "per_min": per_min,
        "duration_s": duration_s,
        "worst_ms": float(worst.magnitude_ms) if worst else float("nan"),
        "worst_t": float(worst.t) if worst else float("nan"),
        "median_ms": float(np.median([e.magnitude_ms for e in ev])) if ev else float("nan"),
        "intervals": interval,
    }
