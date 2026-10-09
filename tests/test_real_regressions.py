"""Regression tests on the REAL e2e captures (skipped when the data is absent).

``runs/validate-*`` is gitignored in this worktree, but present locally for replay.
These encode the two findings from docs/VALIDATION-e2e.md: the corrupt MangoHud
frame (B3) and the ollama GPU-clock transition the correlation table missed (§1/§7).
"""

import os

import numpy as np
import pytest

from detector.analyze import correlation, hitches, sparse
from detector.analyze.config import CORR_Z_CAP, HitchConfig
from detector.analyze.rundir import load_rundir

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS = os.path.join(ROOT, "runs")
CLEAN = os.path.join(RUNS, "validate-clean-20261008-181807")
SPARSE = os.path.join(RUNS, "validate-sparse-20261008-183907")


def _have(run):
    return os.path.exists(os.path.join(run, "frametimes.csv"))


@pytest.mark.skipif(not _have(SPARSE), reason="real sparse capture not present")
def test_sparse_run_worst_is_sane_and_flagged_regular():
    rd = load_rundir(SPARSE)
    cfg = HitchConfig().resolve()
    we = rd.warmup_end()
    te = rd.t_end()
    det = hitches.detect(rd.t, rd.frametime_ms, cfg)
    ev = [e for e in det["events"] if e.t >= we]
    mask = rd.t >= we
    hs = hitches.hitch_stats(ev, rd.t[mask], rd.frametime_ms[mask], cfg, we,
                             cfg.target_fps)
    # B3: without sanitisation this was 99,673,900 ms
    assert hs["worst_ms"] < 10000.0
    assert rd.frametime_quality["rows_rejected"] >= 1
    assert rd.frametime_quality["reasons"]["over_max"] >= 1
    # B2: the sparse 45 s rhythm is recovered explicitly
    sp = sparse.analyze_sparse(ev, we, te, cfg=cfg)
    assert sp["assessment"] == "regular"
    assert abs(sp["period_s"] - 45.0) / 45.0 < 0.05


@pytest.mark.skipif(not _have(CLEAN), reason="real clean capture not present")
def test_ollama_clock_transition_ranks_top_and_z_is_capped():
    rd = load_rundir(CLEAN)
    cfg = HitchConfig().resolve()
    det = hitches.detect(rd.t, rd.frametime_ms, cfg)
    hits = [e.t for e in det["events"] if e.t >= rd.warmup_end()]
    table = correlation.correlate_signals(rd, hits, rd.warmup_end(), rd.t_end())
    assert table
    # §7 regression: the GPU clock transition used to be absent from the top-25
    top5 = {(r["signal"], r["column"]) for r in table[:5]}
    assert any(s == "gpu" and c in ("sm_clock_mhz", "graphics_clock_mhz")
               for s, c in top5), top5
    # B4: no degenerate z explosions
    assert max(abs(r["z"]) for r in table) <= CORR_Z_CAP + 1e-6
    assert not any(abs(r["z"]) > 1e6 for r in table)
    # the transition is significant after FDR
    assert any(r["signal"] == "gpu" and r["column"] == "sm_clock_mhz"
               and r.get("significant_fdr") for r in table[:10])
