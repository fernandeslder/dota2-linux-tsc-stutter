"""Tests for robust frametime parsing (data quality) and the sparse assessment.

The corrupt-frametime fixture is taken **verbatim** from the real e2e capture that
exposed bug B3 (``runs/validate-sparse-20261008-183907``): MangoHud logged one frame
with ``fps~1e-5, frametime~9.96739e7 ms``, which poisoned ``worst_ms``.
"""

import csv
import json
import os

import numpy as np
import pytest

from detector.analyze import correlation, hitches, reporting, sparse
from detector.analyze.config import HitchConfig
from detector.analyze.rundir import load_rundir, sanitize_frametimes

FIXTURES = os.path.join(os.path.dirname(__file__), "..", "..", "..", "tests", "fixtures")
CORRUPT_FT = os.path.abspath(os.path.join(FIXTURES, "sparse-frametimes-corrupt.csv"))
CORRUPT_RAW = os.path.abspath(os.path.join(FIXTURES, "sparse-mangohud-corrupt-line.csv"))


def _read_fixture():
    t, f = [], []
    with open(CORRUPT_FT) as fh:
        for r in csv.DictReader(fh):
            t.append(float(r["t_epoch"]))
            f.append(float(r["frametime_ms"]))
    return np.asarray(t), np.asarray(f)


def test_corrupt_fixture_is_the_real_glitch():
    _, f = _read_fixture()
    assert float(np.max(f)) == pytest.approx(9.96739e7)
    # raw MangoHud line: fps ~1e-5 and frametime ~1e8
    with open(CORRUPT_RAW) as fh:
        raw = fh.readline().split(",")
    assert float(raw[0]) < 1e-3
    assert float(raw[1]) == pytest.approx(9.96739e7)


def test_sanitize_frametimes_rejects_real_corrupt_row():
    t, f = _read_fixture()
    t2, f2, q = sanitize_frametimes(t, f)
    assert q["rows_total"] == 8
    assert q["rows_kept"] == 7
    assert q["rows_rejected"] == 1
    assert q["reasons"]["over_max"] == 1
    assert q["rejected_examples"][0]["frametime_ms"] == pytest.approx(9.96739e7)
    assert np.max(f2) < 10000.0
    assert len(t2) == len(f2) == 7


def test_sanitize_rejects_nonfinite_and_nonpositive():
    t = np.arange(4, dtype=float)
    f = np.array([7.0, np.nan, -3.0, np.inf])
    _, f2, q = sanitize_frametimes(t, f)
    assert q["reasons"]["nonfinite"] == 2
    assert q["reasons"]["nonpositive"] == 1
    assert q["rows_kept"] == 1


def _minimal_rundir(tmp_path, frametime_path):
    d = tmp_path / "run"
    d.mkdir()
    (d / "frametimes.csv").write_bytes(open(frametime_path, "rb").read())
    (d / "meta.json").write_text(json.dumps({"run_id": "corrupt-real"}))
    (d / "events.csv").write_text(
        "t_epoch,label,detail\n"
        f"{1791495640.0:.6f},run_start,x\n"
        f"{1791495640.0:.6f},warmup_end,x\n"
        f"{1791495650.0:.6f},window_end,x\n")
    return str(d)


def test_load_rundir_surfaces_real_corruption(tmp_path):
    rd = load_rundir(_minimal_rundir(tmp_path, CORRUPT_FT))
    assert rd.frametime_quality["rows_rejected"] == 1
    assert rd.frametime_quality["reasons"]["over_max"] == 1
    assert np.max(rd.frametime_ms) < 10000.0
    # the warning is surfaced too
    assert any("data quality" in w for w in rd.warnings)


def test_verdict_reports_data_quality_and_sane_worst(tmp_path):
    rd = load_rundir(_minimal_rundir(tmp_path, CORRUPT_FT))
    v = reporting.analyze_run(rd, n_perm=30)
    assert v["data_quality"]["rows_rejected"] == 1
    # the corrupt 9.97e7 ms frame never reaches worst_ms (there may be no real hitch
    # in this tiny fixture, so nan is fine; what matters is the huge value is gone)
    assert not (v["hitches"]["worst_ms"] > 10000.0)
    reporting.write_outputs(rd, v, str(tmp_path / "out"), plots=False)
    vj = json.loads((tmp_path / "out" / "verdict.json").read_text())
    assert vj["data_quality"]["rows_rejected"] == 1
    assert "sparse" in vj and "assessment" in vj["sparse"]


def test_loader_keeps_rows_with_blank_cells(tmp_path):
    """Real signal CSVs leave cells blank (gpu fan_pct, threads rows); a blank must
    become NaN, never drop the whole row (that silently discarded gpu/threads)."""
    p = tmp_path / "gpu.csv"
    p.write_text(
        "t_epoch,sm_clock_mhz,fan_pct,enc_util\n"
        "1.0,210,,,\n"
        "2.0,2460,45,3\n")
    from detector.analyze.rundir import load_signal
    sig = load_signal(str(p), "gpu")
    assert len(sig.t) == 2
    assert sig.columns["sm_clock_mhz"].tolist() == [210.0, 2460.0]
    assert np.isnan(sig.columns["fan_pct"][0]) and sig.columns["fan_pct"][1] == 45.0


# --- sparse assessment ----------------------------------------------------

def _ev(times, mag=60.0, warmup=0.0):
    return [hitches.HitchEvent(t=float(t), t_end=float(t), magnitude_ms=mag,
                               peak_ms=mag, excess_ms=mag - 13.9, duration_ms=0.0,
                               n_frames=1) for t in times if t >= warmup]


def test_sparse_regular_recovered():
    rng = np.random.default_rng(0)
    times = [50.0 + 45.0 * k + rng.normal(0, 1.0) for k in range(11)]
    sp = sparse.analyze_sparse(_ev(times), 0.0, 600.0)
    assert sp["assessment"] == "regular"
    assert abs(sp["period_s"] - 45.0) / 45.0 < 0.05
    lo, hi = sp["rate_ci95_per_min"]
    assert lo <= sp["rate_per_min"] <= hi


def test_sparse_dense_periodic_is_none():
    times = [50.0 + 4.0 * k for k in range(80)]
    sp = sparse.analyze_sparse(_ev(times), 0.0, 600.0)
    assert sp["assessment"] == "none"


def test_sparse_irregular():
    rng = np.random.default_rng(1)
    times = np.sort(rng.uniform(0, 600, 12))
    sp = sparse.analyze_sparse(_ev(times), 0.0, 600.0)
    assert sp["assessment"] in {"none", "irregular"}
    assert sp["assessment"] != "regular"


def test_sparse_mild_hitches_below_severity_gate():
    # jitter just above FLOOR must not count as sparse candidates
    times = [10.0 + 45.0 * k for k in range(10)]
    sp = sparse.analyze_sparse(_ev(times, mag=15.0), 0.0, 600.0)
    assert sp["n_sparse_candidates"] == 0
    assert sp["assessment"] == "none"


def test_sparse_short_window_caveat():
    times = [5.0 + 45.0 * k for k in range(3)]
    sp = sparse.analyze_sparse(_ev(times), 0.0, 200.0)
    assert any("5 min" in c for c in sp["caveats"])


def test_sparse_steady_residual_reveals_sparse_component():
    # 4 s steady grid + a sparse 45 s component: after removing the steady phase the
    # sparse rhythm should be recovered.
    times = [20.0 + 4.0 * k for k in range(80)] + [22.5 + 45.0 * j for j in range(12)]
    steady = {"significant": True, "period_s": 4.0}
    sp = sparse.analyze_sparse(_ev(np.sort(times)), 0.0, 600.0, steady=steady)
    assert sp["residual_applied"] is True
    assert sp["assessment"] == "regular"
    assert abs(sp["period_s"] - 45.0) / 45.0 < 0.1


# --- correlation helpers --------------------------------------------------

def test_cliffs_delta_bounds_and_value():
    assert correlation._cliffs_delta([3, 4, 5], [1, 2]) == pytest.approx(1.0)
    assert correlation._cliffs_delta([1, 2], [3, 4, 5]) == pytest.approx(-1.0)
    assert correlation._cliffs_delta([1, 2, 3], [1, 2, 3]) == pytest.approx(0.0)
    # tie-heavy: a and b identical zeros -> 0 (not biased by sort order)
    assert correlation._cliffs_delta([0.0] * 5, [0.0] * 20) == pytest.approx(0.0)


def test_bh_fdr_monotone_and_bounded():
    p = np.array([0.001, 0.01, 0.2, 0.9, float("nan")])
    q = correlation._bh_fdr(p)
    assert q[0] <= q[1] <= q[2] <= q[3] <= 1.0
    assert np.isnan(q[4])
    assert q[0] > p[0]  # BH inflates p-values


def test_step_feature_detects_clock_step(tmp_path):
    """A clock that steps up at every hitch should surface via the 'step' feature."""
    t = np.arange(0.0, 200.0, 0.1)
    clock = np.full_like(t, 200.0)
    hitches_t = [50.0, 90.0, 130.0, 170.0]
    for ht in hitches_t:
        clock[t >= ht] += 500.0  # a step at each hitch (sustained afterwards)
    p = tmp_path / "gpu.csv"
    with open(p, "w") as fh:
        fh.write("t_epoch,sm_clock_mhz\n")
        for ti, ci in zip(t, clock):
            fh.write(f"{ti:.3f},{ci:.3f}\n")
    from detector.analyze.rundir import load_signal, RunDir
    rd = RunDir(path=str(tmp_path), run_id="s", meta={}, events=[], t=np.empty(0),
                frametime_ms=np.empty(0),
                signals={"gpu": load_signal(str(p), "gpu")}, logs={})
    table = correlation.correlate_signals(rd, hitches_t, 40.0, 200.0)
    assert table
    top = table[0]
    assert top["signal"] == "gpu"
    assert abs(top["cliffs_delta"]) == pytest.approx(1.0)
    # the step feature must be among the top-ranked features
    assert any(r["feature"] == "step" for r in table[:4])


def test_correlation_nan_columns_are_skipped_not_crashing(tmp_path):
    from detector.analyze.rundir import RunDir, load_signal
    p = tmp_path / "sig.csv"
    p.write_text("t_epoch,good,allnan\n"
                 + "".join(f"{i*0.1:.1f},{i%5},\n" for i in range(1, 200)))
    rd = RunDir(path=str(tmp_path), run_id="s", meta={}, events=[], t=np.empty(0),
                frametime_ms=np.empty(0), signals={"sig": load_signal(str(p), "sig")},
                logs={})
    table = correlation.correlate_signals(rd, [5.0, 10.0, 15.0, 20.0], 1.0, 30.0)
    assert all(r["column"] != "allnan" for r in table)
