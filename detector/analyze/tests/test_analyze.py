"""Unit tests for the analysis half. Deterministic, synthetic, no Dota, no GUI."""

import json
import os

import numpy as np
import pytest

from detector.analyze import compare as compare_mod
from detector.analyze import correlation, hitches, periodicity, reporting, stats, synth
from detector.analyze.config import HitchConfig
from detector.analyze.rundir import load_rundir


def _frames(hitch_times, duration=30.0, t0=1_000_000.0, fps=144.0, jitter=0.2, mag=60.0, seed=0):
    rng = np.random.default_rng(seed)
    base = 1000.0 / fps
    ht = sorted(hitch_times)
    t, f, k = t0, [], 0
    while t < t0 + duration:
        if k < len(ht) and t >= ht[k]:
            f.append(mag)
            k += 1
        else:
            f.append(base + rng.normal(0, jitter))
        t += f[-1] / 1000.0
    ts, acc = [], t0
    for x in f:
        ts.append(acc)
        acc += x / 1000.0
    return np.asarray(ts), np.asarray(f)


def test_rolling_median_excludes_center():
    t = np.arange(0, 10, 0.01)
    f = np.full_like(t, 7.0)
    f[500] = 100.0
    med = hitches.rolling_median(t, f, 1.0)
    assert abs(med[500] - 7.0) < 1e-9
    assert abs(med[100] - 7.0) < 1e-9


def test_detect_and_floor():
    cfg = HitchConfig().resolve()
    t, f = _frames([1_000_003.0, 1_000_010.0], duration=20.0)
    det = hitches.detect(t, f, cfg)
    times = [e.t for e in det["events"]]
    assert len(times) == 2
    assert abs(times[0] - 1_000_003.0) < 0.05
    assert all(e.magnitude_ms > cfg.floor_ms for e in det["events"])


def test_merge_adjacent_within_gap():
    cfg = HitchConfig().resolve()
    base = 1000.0 / 144.0
    t = [1_000_000.0, 1_000_000.0 + base / 1000, 1_000_000.0 + 2 * base / 1000,
         1_000_000.0 + 0.5]
    f = [base, 80.0, 80.0, base]  # two adjacent hitch frames 6.9 ms apart -> one event
    ts = np.asarray(t)
    fs = np.asarray(f)
    det = hitches.detect(ts, fs, cfg)
    assert len(det["events"]) == 1
    assert det["events"][0].n_frames == 2
    assert abs(det["events"][0].magnitude_ms - 80.0) < 1e-9


def test_below_floor_not_hitch():
    cfg = HitchConfig().resolve()
    base = 1000.0 / 144.0
    t = np.asarray([1_000_000.0, 1_000_000.01, 1_000_000.02])
    f = np.asarray([base, 12.0, base])  # 12 ms < FLOOR(13.9) and < K*median
    det = hitches.detect(t, f, cfg)
    assert len(det["events"]) == 0


def test_fps_lows():
    ft = np.concatenate([np.full(990, 7.0), np.full(10, 70.0)])
    ms, fps = stats.fps_low(ft, 0.01)
    assert abs(ms - 70.0) < 1e-9
    assert abs(fps - 1000.0 / 70.0) < 1e-6
    summ = stats.summary(ft, 144.0)
    assert summ["p99_ms"] > summ["p50_ms"]


def test_effect_sizes_sign():
    a = np.array([1.0, 2.0, 3.0, 4.0])
    b = np.array([10.0, 11.0, 12.0, 13.0])
    assert stats.cohens_d(b, a) > 0
    assert stats.cliffs_delta(b, a) == 1.0
    diff, lo, hi = stats.bootstrap_ci_diff(b, a)
    assert lo > 0 and diff > 0


def test_precision_recall_edges():
    from detector.analyze.selftest import precision_recall
    assert precision_recall([], []) == (1.0, 1.0)
    p, r = precision_recall([], [1.0, 2.0])
    assert r == 0.0 and np.isnan(p)
    p, r = precision_recall([1.0, 2.0], [])
    assert p == 0.0 and np.isnan(r)
    p, r = precision_recall([10.0, 20.1], [10.05, 20.0], tol=0.2)
    assert p == 1.0 and r == 1.0


def _events(times, warmup=0.0, mag=50.0):
    return [hitches.HitchEvent(t=float(t), t_end=float(t), magnitude_ms=mag,
                               peak_ms=mag, excess_ms=mag - 13.9, duration_ms=0.0,
                               n_frames=1) for t in times if t >= warmup]


def test_periodicity_periodic_detected():
    times = [100.0 + 4.0 * k for k in range(60)]
    per = periodicity.analyze_periodicity(_events(times), 100.0, 340.0, n_perm=200)
    assert per["kind"] == "periodic"
    assert abs(per["steady"]["period_s"] - 4.0) / 4.0 < 0.05
    assert per["steady"]["p_value"] < 0.01


def test_periodicity_random_not_significant():
    rng = np.random.default_rng(0)
    times = np.sort(rng.uniform(0, 400, 60))
    per = periodicity.analyze_periodicity(_events(times), 0.0, 400.0, n_perm=200)
    assert per["kind"] in {"aperiodic", "insufficient"}
    if per["steady"]:
        assert not per["steady"]["significant"]


def test_periodicity_sparse_needs_window():
    times = [100.0 + 45.0 * k for k in range(4)]
    per = periodicity.analyze_periodicity(_events(times), 100.0, 280.0, n_perm=100)
    assert per["sparse_assessable"] is False
    assert any("sparse" in w for w in per["warnings"])


def test_periodicity_sparse_detected_long_window():
    times = [50.0 + 45.0 * k for k in range(12)]
    per = periodicity.analyze_periodicity(_events(times), 50.0, 600.0, n_perm=200)
    assert per["sparse"]["significant"]
    assert abs(per["sparse"]["period_s"] - 45.0) / 45.0 < 0.05


def test_synth_rundir_contract(tmp_path):
    spec = synth.periodic_spec(duration_s=40.0, seed=1)
    gt = synth.generate(spec, str(tmp_path / "run"))
    d = tmp_path / "run"
    for f in ("meta.json", "events.csv", "frametimes.csv", "gpu.csv", "dmesg.log"):
        assert (d / f).exists()
    rd = load_rundir(str(d))
    assert rd.run_id == "periodic-1"
    assert len(rd.t) == len(rd.frametime_ms) > 0
    assert np.all(np.diff(rd.t) >= 0)
    assert "gpu_util_pct" in rd.signals["gpu"].columns
    assert len(gt["hitches"]) > 0
    with open(d / "events.csv") as fh:
        assert fh.readline().strip() == "t_epoch,label,detail"
    assert rd.warmup_end() == pytest.approx(gt["t0"] + 20.0)


def test_correlation_finds_correlated_and_ignores_decoy(tmp_path):
    spec = synth.mixed_spec(duration_s=180.0, seed=2)
    synth.generate(spec, str(tmp_path / "m"))
    rd = load_rundir(str(tmp_path / "m"))
    cfg = HitchConfig().resolve()
    det = hitches.detect(rd.t, rd.frametime_ms, cfg)
    hits = [e.t for e in det["events"] if e.t >= rd.warmup_end()]
    table = correlation.correlate_signals(rd, hits, rd.warmup_end(), rd.t_end())
    top = {(r["signal"], r["column"]) for r in table[:8]}
    assert any(s == "gpu" and c == "sm_clock_mhz" for s, c in top)
    decoy = [r for r in table if r["signal"] == "decoy"]
    if decoy:
        assert abs(decoy[0]["z"]) < 5.0


def test_analyze_run_and_outputs(tmp_path):
    spec = synth.periodic_spec(duration_s=140.0, seed=3)
    synth.generate(spec, str(tmp_path / "run"))
    rd = load_rundir(str(tmp_path / "run"))
    v = reporting.analyze_run(rd, n_perm=150)
    assert v["hitches"]["count"] > 0
    assert v["periodicity"]["kind"] in {"periodic", "mixed"}
    arts = reporting.write_outputs(rd, v, str(tmp_path / "out"), plots=False)
    assert os.path.exists(tmp_path / "out" / "verdict.json")
    assert os.path.exists(tmp_path / "out" / "hitches.csv")
    vj = json.loads((tmp_path / "out" / "verdict.json").read_text())
    assert vj["schema_version"] == "1.0"
    assert "_events" not in vj


def test_fixed_check(tmp_path):
    spec = synth.clean_spec(duration_s=1000.0, seed=4)
    synth.generate(spec, str(tmp_path / "clean"))
    rd = load_rundir(str(tmp_path / "clean"))
    good = reporting.analyze_run(rd, n_perm=100)
    res = __import__("detector.analyze.fixed", fromlist=["check_fixed"]).check_fixed(
        [good, good, good])
    assert res["provisional"] is False
    assert res["passed"] is True


def test_compare_improved(tmp_path):
    a = []
    b = []
    for s in range(3):
        synth.generate(synth.periodic_spec(seed=s), str(tmp_path / f"a{s}"))
        synth.generate(synth.clean_spec(seed=s), str(tmp_path / f"b{s}"))
        a.append(reporting.analyze_run(load_rundir(str(tmp_path / f"a{s}")), n_perm=100))
        b.append(reporting.analyze_run(load_rundir(str(tmp_path / f"b{s}")), n_perm=100))
    cmp = compare_mod.compare_runs(a, b)
    hp = [m for m in cmp["metrics"] if m["key"] == "hitches_per_min"][0]
    assert hp["verdict"] == "improved"
    assert cmp["verdict"] in {"improved", "mixed"}


def test_cli_synth_and_detect(tmp_path, capsys):
    from detector.analyze.cli import main
    d = str(tmp_path / "cli-run")
    assert main(["synth", "--kind", "periodic", "--seed", "1", "--duration", "40",
                 "--out", d]) == 0
    assert main(["detect", d, "--n-perm", "100"]) == 0
    assert os.path.exists(os.path.join(d, "out", "verdict.json"))
