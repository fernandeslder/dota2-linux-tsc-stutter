"""Tunable constants for the hitch definition and the analysis pipeline.

The spec (``docs/SPEC-detector.md``) fixes the *initial* numbers; this module is the
single place they live so the sensitivity study and ``selftest`` can sweep them.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

DEFAULT_TARGET_FPS = 144.0
DEFAULT_K = 2.5
DEFAULT_W_S = 1.0
DEFAULT_FLOOR_MIN_MS = 12.0
DEFAULT_FLOOR_TARGET_MULT = 2.0
DEFAULT_MERGE_GAP_MS = 100.0

# Low-severity tier (reported alongside the primary hitches, never mixed in).
DEFAULT_K_LOW = 2.0
DEFAULT_FLOOR_LOW_MIN_MS = 8.0
DEFAULT_FLOOR_LOW_TARGET_MULT = 1.5

DEFAULT_WARMUP_S = 20.0

MIN_WINDOW_FOR_SPARSE_S = 300.0
MIN_FRAMES_FOR_MEDIAN = 10
PERIOD_MIN_S = 0.5
PERIOD_MAX_S = 60.0
SPARSE_PERIOD_MIN_S = 30.0
SPARSE_PERIOD_MAX_S = 90.0
STEADY_MAX_S = 10.0
PERMUTATIONS = 400
RNG_SEED = 20261008

# --- data quality ---------------------------------------------------------
# MangoHud occasionally emits a corrupt frame (fps~0, frametime~1e8 ms). Any
# frametime above this is physically implausible (a >10 s stall would end the
# game/run) and is rejected before detection so it cannot poison worst_ms or
# the fps lows. See docs/VALIDATION-e2e.md bug B3.
MAX_PLAUSIBLE_FRAMETIME_MS = 10_000.0

# --- explicit sparse-hitch assessment ------------------------------------
# Sparse stalls are *severe and isolated*; the leftover vkcube jitter sits just
# above FLOOR. Candidate sparse hitches are those with magnitude >=
# max(SPARSE_SEVERITY_MULT * FLOOR, FLOOR + SPARSE_SEVERITY_PLUS_MS). The
# interval-regularity test then looks for a tight mode in the sparse band
# [20, 100] s. Deliberately independent of the (underpowered) sparse-band
# permutation null.
SPARSE_SEVERITY_MULT = 1.5
SPARSE_SEVERITY_PLUS_MS = 6.0
SPARSE_MIN_EVENTS = 8
SPARSE_MIN_INTERVALS = 5
SPARSE_INTERVAL_MIN_S = 30.0
SPARSE_INTERVAL_MAX_S = 90.0
SPARSE_MODE_TOL = 0.25
SPARSE_CV_MAX = 0.15
SPARSE_MIN_MODE_FRACTION = 0.5
SPARSE_RATE_BOOT = 2000

CORR_FAST_WINDOW_S = 0.5
CORR_SLOW_WINDOW_S = 2.0
CORR_SLOW_DT_S = 1.0
CORR_CONTROL_MULT = 20
CORR_MIN_CONTROL = 200
# Correlation ranking: cap the (unbounded) z of zero-variance controls, drop
# pairs whose control spread is effectively zero, and correct for the many
# (signal, column, feature) tests with Benjamini-Hochberg FDR.
CORR_Z_CAP = 20.0
CORR_FDR_Q = 0.05
CORR_MIN_CONTROL_SD_FRAC = 1e-6

# "blocked-on" analysis (detector/analyze/blocked.py): per hitch, look at the
# window [hitch_start - pre, hitch_end]; `pre` is `max(BLOCKED_PRE_MS,
# magnitude_ms)` so a single long frame is covered back to when it started.
BLOCKED_PRE_MS = 50.0
BLOCKED_MIN_COVERAGE = 0.05   # a thread/bucket must cover >=5% of the window
BLOCKED_MAX_ROWS = 30
BLOCKED_MAX_WINDOW_S = 5.0


def target_ms(target_fps: float) -> float:
    return 1000.0 / float(target_fps)


@dataclass
class HitchConfig:
    """Configuration of the rolling-median outlier hitch definition."""

    target_fps: float = DEFAULT_TARGET_FPS
    k: float = DEFAULT_K
    w_s: float = DEFAULT_W_S
    floor_ms: float = 0.0
    floor_min_ms: float = DEFAULT_FLOOR_MIN_MS
    floor_target_mult: float = DEFAULT_FLOOR_TARGET_MULT
    merge_gap_ms: float = DEFAULT_MERGE_GAP_MS
    k_low: float = DEFAULT_K_LOW
    floor_low_ms: float = 0.0
    floor_low_min_ms: float = DEFAULT_FLOOR_LOW_MIN_MS
    floor_low_target_mult: float = DEFAULT_FLOOR_LOW_TARGET_MULT

    def resolve(self) -> "HitchConfig":
        """Fill the derived floors (``max(mult*target, min)``) if not set explicitly."""
        if self.floor_ms <= 0:
            self.floor_ms = max(self.floor_target_mult * target_ms(self.target_fps),
                                self.floor_min_ms)
        if self.floor_low_ms <= 0:
            self.floor_low_ms = max(self.floor_low_target_mult * target_ms(self.target_fps),
                                    self.floor_low_min_ms)
        return self

    @property
    def merge_gap_s(self) -> float:
        return self.merge_gap_ms / 1000.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["target_ms"] = target_ms(self.target_fps)
        return d
