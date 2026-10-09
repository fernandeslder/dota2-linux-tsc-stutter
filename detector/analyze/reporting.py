"""Analysis orchestration, plots and the machine-readable verdict.

``analyze_run`` turns a loaded :class:`RunDir` into the verdict dict; ``write_outputs``
persists it plus PNGs, ``hitches.csv``, ``stats.json``, ``report.md`` and the full
correlation tables under ``out/``.

**verdict.json schema (version 1.0)**

===================  =========================================================
key                  meaning
===================  =========================================================
schema_version       ``"1.0"``
tool                 ``"stutter"``
run_id / run_dir     identity
generated_utc        ISO-8601 UTC timestamp
config               resolved :class:`HitchConfig` (K, W, FLOOR, merge gap, fps cap)
window               t_start, warmup_end, t_end, duration_s, n_frames, warmup_source
hitch_definition     human-readable restatement of the rule + merge gap
hitches              count, per_min, worst_ms/t, median_ms, low tier count/rate
frametime            p50/p95/p99 ms, fps_1pct_low, fps_0.1pct_low, mean_fps,
                     frame_drop_frac, n_frames
data_quality         frametime rows read/kept/rejected + reasons (nonfinite,
                     nonpositive, over_max), max_plausible_ms, examples
intervals            count, min/max/mean/p50/p90/p95/p99 s, cv, histogram
periodicity          kind (periodic|sparse|mixed|aperiodic|insufficient),
                     steady/sparse/sparse_residual band results
                     (period_s, spectral_peak_s, period_source, p_value,
                     period_err_s, fraction_explained, significant),
                     interval_hist, autocorr_peak, lombscargle_peak, warnings
sparse               explicit sparse-hitch assessment independent of the
                     permutation null: assessment (none|irregular|regular),
                     label, period_s, rate_per_min + bootstrap CI, interval
                     quantiles, interval mode + modal-cluster CV/fraction,
                     severity gate, caveats
correlation          {"signals": [...top N...], "logs": [...top N...]}
warnings             list of strings (also inside periodicity.warnings)
artifacts            relative paths of produced files
===================  =========================================================
"""

from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone

import numpy as np

from . import correlation, hitches as hitch_mod, periodicity, sparse as sparse_mod, stats as st
from . import blocked as blocked_mod
from .config import HitchConfig

PLOT_DPI = 110
TOP_SIGNALS = 25
TOP_LOGS = 15


def analyze_run(rundir, cfg: HitchConfig | None = None, n_perm: int = None,
                seed: int = None) -> dict:
    from .config import PERMUTATIONS, RNG_SEED
    cfg = (cfg or HitchConfig()).resolve()
    n_perm = PERMUTATIONS if n_perm is None else n_perm
    seed = RNG_SEED if seed is None else seed

    warmup_end = rundir.warmup_end()
    t_end = rundir.t_end()
    warmup_source = "mark" if rundir.first_mark("warmup_end") is not None else "default(20s)"

    det = hitch_mod.detect(rundir.t, rundir.frametime_ms, cfg)
    mask = rundir.t >= warmup_end
    ft = rundir.frametime_ms[mask]
    t = rundir.t[mask]
    events = [e for e in det["events"] if e.t >= warmup_end]
    low_events = [e for e in det["low_events"] if e.t >= warmup_end]
    hitch_stats = hitch_mod.hitch_stats(events, t, ft, cfg, warmup_end, cfg.target_fps)
    low_stats = hitch_mod.hitch_stats(low_events, t, ft, cfg, warmup_end, cfg.target_fps)

    per = periodicity.analyze_periodicity(events, warmup_end, t_end, n_perm=n_perm, seed=seed)
    sp = sparse_mod.analyze_sparse(events, warmup_end, t_end,
                                   steady=per.get("steady"), cfg=cfg, seed=seed)
    hit_times = [e.t for e in events if e.t >= warmup_end]
    duration_min = hitch_stats["duration_s"] / 60.0 if hitch_stats["duration_s"] else float("nan")
    isolated = _isolated_count(hit_times, gap_s=15.0)
    sparse_per_min = (isolated / duration_min) if duration_min and np.isfinite(duration_min) else float("nan")
    corr_signals = correlation.correlate_signals(rundir, hit_times, warmup_end, t_end)
    corr_logs = correlation.correlate_logs(rundir, hit_times, warmup_end, t_end)
    run_end = float(rundir.meta.get("collector_end_epoch") or 0.0) or float(t_end)
    blocked = blocked_mod.analyze_blocked(rundir, events, run_end)

    warnings = list(rundir.warnings) + list(per.get("warnings", []))
    verdict = {
        "schema_version": "1.0",
        "tool": "stutter",
        "run_id": rundir.run_id,
        "run_dir": os.path.abspath(rundir.path),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "config": cfg.to_dict(),
        "hitch_definition": {
            "rule": "frametime_ms > K * rolling_median(+-W, excl. centre) AND frametime_ms > FLOOR",
            "K": cfg.k, "W_s": cfg.w_s, "FLOOR_ms": cfg.floor_ms,
            "merge_gap_ms": cfg.merge_gap_ms, "target_fps": cfg.target_fps,
            "low_tier": {"K": cfg.k_low, "FLOOR_ms": cfg.floor_low_ms},
        },
        "window": {
            "t_start": float(t[0]) if t.size else float("nan"),
            "warmup_end": float(warmup_end),
            "t_end": float(t_end),
            "duration_s": float(hitch_stats["duration_s"]),
            "n_frames": int(t.size),
            "warmup_source": warmup_source,
        },
        "hitches": {
            "count": hitch_stats["count"],
            "per_min": hitch_stats["per_min"],
            "worst_ms": hitch_stats["worst_ms"],
            "worst_t": hitch_stats["worst_t"],
            "median_ms": hitch_stats["median_ms"],
            "low_count": low_stats["count"],
            "low_per_min": low_stats["per_min"],
            "isolated_count": int(isolated),
            "sparse_per_min": sparse_per_min,
        },
        "frametime": st.summary(ft, cfg.target_fps),
        "data_quality": dict(rundir.frametime_quality),
        "intervals": hitch_stats["intervals"],
        "periodicity": per,
        "sparse": sp,
        "correlation": {
            "signals": corr_signals[:TOP_SIGNALS],
            "logs": corr_logs[:TOP_LOGS],
        },
        "blocked": blocked,
        "warnings": warnings,
        "artifacts": {},
    }
    verdict["_full_corr_signals"] = corr_signals
    verdict["_full_corr_logs"] = corr_logs
    verdict["_events"] = events
    verdict["_low_events"] = low_events
    verdict["_detect"] = det
    return verdict


def _rel_seconds(t, ref):
    return (np.asarray(t, dtype=float) - ref) / 60.0


def _isolated_count(times, gap_s: float = 15.0) -> int:
    """Hitches with no other hitch within ``gap_s`` on either side (the 'sparse' ones)."""
    ts = sorted(times)
    n = len(ts)
    isolated = 0
    for i, t in enumerate(ts):
        prev = (t - ts[i - 1]) if i > 0 else float("inf")
        nxt = (ts[i + 1] - t) if i < n - 1 else float("inf")
        if min(prev, nxt) > gap_s:
            isolated += 1
    return isolated


def _write_csv(path, rows, header):
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


def _plots(rundir, verdict, out_dir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cfg = verdict["config"]
    we = verdict["window"]["warmup_end"]
    t_end = verdict["window"]["t_end"]
    mask = rundir.t >= we
    t = rundir.t[mask]
    ft = rundir.frametime_ms[mask]
    x = _rel_seconds(t, we)
    events = verdict["_events"]
    made = []

    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(x, ft, lw=0.4, color="steelblue", label="frametime")
    ax.axhline(cfg["floor_ms"], color="orange", ls="--", lw=0.8,
               label=f"FLOOR {cfg['floor_ms']:.1f} ms")
    if events:
        ex = [(e.t - we) / 60.0 for e in events]
        ey = [e.magnitude_ms for e in events]
        ax.scatter(ex, ey, color="red", s=18, zorder=5, label="hitch")
    ax.set_xlabel("minutes since warm-up end")
    ax.set_ylabel("frametime (ms)")
    ax.set_title(f"{rundir.run_id}: frametime trace with hitches")
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    p = os.path.join(out_dir, "frametime_trace.png")
    fig.savefig(p, dpi=PLOT_DPI)
    plt.close(fig)
    made.append(p)

    fig, ax = plt.subplots(figsize=(12, 2.6))
    if events:
        ex = [(e.t - we) / 60.0 for e in events]
        ey = [e.magnitude_ms for e in events]
        ax.vlines(ex, 0, ey, color="red", lw=1.0)
        ax.scatter(ex, ey, color="darkred", s=12)
    ax.set_xlim(0, max(0.1, (t_end - we) / 60.0))
    ax.set_xlabel("minutes since warm-up end")
    ax.set_ylabel("hitch (ms)")
    ax.set_title("hitch timeline")
    fig.tight_layout()
    p = os.path.join(out_dir, "hitch_timeline.png")
    fig.savefig(p, dpi=PLOT_DPI)
    plt.close(fig)
    made.append(p)

    iv = verdict["intervals"]
    fig, ax = plt.subplots(figsize=(6, 4))
    if iv.get("hist"):
        edges = np.asarray(iv["hist"]["edges_s"])
        counts = np.asarray(iv["hist"]["counts"])
        ax.bar(0.5 * (edges[:-1] + edges[1:]), counts,
               width=np.diff(edges), color="slateblue")
    ax.set_xlabel("inter-hitch interval (s)")
    ax.set_ylabel("count")
    ax.set_title("inter-hitch interval histogram")
    fig.tight_layout()
    p = os.path.join(out_dir, "interval_histogram.png")
    fig.savefig(p, dpi=PLOT_DPI)
    plt.close(fig)
    made.append(p)

    sa = periodicity.spectrum_and_autocorr(events, we, t_end)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    if sa is not None:
        axes[0].semilogx(sa["lags"], sa["autocorr"], color="teal")
        axes[0].set_xlabel("lag (s)")
        axes[0].set_ylabel("autocorrelation")
        axes[0].set_title("autocorrelation (binned hitch series)")
        axes[1].semilogx(sa["periods"], sa["power"], color="purple")
        axes[1].set_xlabel("period (s)")
        axes[1].set_ylabel("power")
        axes[1].set_title("spectrum (Lomb-Scargle / periodogram)")
        p2 = verdict["periodicity"].get("steady")
        if p2 and p2.get("significant"):
            axes[1].axvline(p2["period_s"], color="red", ls="--", lw=0.8,
                            label=f"P={p2['period_s']:.2f}s")
            axes[1].legend(fontsize=8)
    fig.tight_layout()
    p = os.path.join(out_dir, "spectrum_autocorr.png")
    fig.savefig(p, dpi=PLOT_DPI)
    plt.close(fig)
    made.append(p)

    sig = verdict["correlation"]["signals"][:15]
    fig, ax = plt.subplots(figsize=(8, max(3, 0.35 * len(sig))))
    if sig:
        labels = [f"{r['signal']}.{r['column']} [{r['feature']}]" for r in sig][::-1]
        zvals = [r["z"] for r in sig][::-1]
        colors = ["crimson" if z < 0 else "seagreen" for z in zvals]
        ax.barh(labels, zvals, color=colors)
        ax.axvline(0, color="k", lw=0.6)
    ax.set_xlabel("z-score of signal around hitches vs control windows")
    ax.set_title("correlation panel (top ranked signals)")
    fig.tight_layout()
    p = os.path.join(out_dir, "correlation_panel.png")
    fig.savefig(p, dpi=PLOT_DPI)
    plt.close(fig)
    made.append(p)
    return made


def write_outputs(rundir, verdict, out_dir, plots: bool = True):
    os.makedirs(out_dir, exist_ok=True)
    events = verdict["_events"]
    low = verdict["_low_events"]

    hcsv = os.path.join(out_dir, "hitches.csv")
    _write_csv(hcsv,
               [[f"{e.t:.6f}", f"{e.t_end:.6f}", f"{e.magnitude_ms:.3f}",
                 f"{e.excess_ms:.3f}", f"{e.duration_ms:.3f}", e.n_frames, e.severity]
                for e in list(events) + list(low)],
               ["t_epoch", "t_end", "magnitude_ms", "excess_ms", "duration_ms",
                "n_frames", "severity"])

    scsv = os.path.join(out_dir, "correlation_signals.csv")
    corr_sig = verdict.get("_full_corr_signals", verdict["correlation"]["signals"])
    _write_csv(scsv,
               [[r["signal"], r["column"], r["feature"], f"{r['z']:.4f}",
                 f"{r.get('cliffs_delta', float('nan')):.4f}",
                 f"{r.get('cohens_d', float('nan')):.4f}",
                 f"{r['p_value']:.6g}",
                 ("" if r.get("q_value") is None else f"{r['q_value']:.6g}"),
                 int(bool(r.get("significant_fdr", False))),
                 int(bool(r.get("degenerate_control", False))),
                 f"{r['enrichment']:.4f}",
                 f"{r['hitch_mean']:.6g}", f"{r['control_mean']:.6g}",
                 f"{r['delta']:.6g}", r["n_hitch_windows"], r["slow"]]
                for r in corr_sig],
               ["signal", "column", "feature", "z", "cliffs_delta", "cohens_d",
                "p_value", "q_value", "significant_fdr", "degenerate_control",
                "enrichment", "hitch_mean", "control_mean", "delta",
                "n_hitch_windows", "slow"])

    lcsv = os.path.join(out_dir, "correlation_logs.csv")
    corr_log = verdict.get("_full_corr_logs", verdict["correlation"]["logs"])
    _write_csv(lcsv,
               [[r["log"], r["near_hitch"], r["near_control"], f"{r['enrichment']:.4f}",
                 f"{r['delta']:.4f}", r["template"]]
                for r in corr_log],
               ["log", "near_hitch", "near_control", "enrichment", "delta", "template"])

    bcsv = os.path.join(out_dir, "blocked_on.csv")
    blocked_mod.write_blocked_csv(bcsv, verdict.get("blocked", {}))

    stats_p = os.path.join(out_dir, "stats.json")
    with open(stats_p, "w") as fh:
        json.dump({k: verdict[k] for k in
                   ("run_id", "config", "hitch_definition", "window", "hitches",
                    "frametime", "data_quality", "intervals", "periodicity",
                    "sparse", "warnings")},
                  fh, indent=2)

    artifacts = {"hitches_csv": "hitches.csv", "stats_json": "stats.json",
                 "correlation_signals_csv": "correlation_signals.csv",
                 "correlation_logs_csv": "correlation_logs.csv",
                 "blocked_on_csv": "blocked_on.csv"}
    if plots:
        for p in _plots(rundir, verdict, out_dir):
            artifacts[os.path.basename(p)] = os.path.basename(p)

    verdict.pop("_events", None)
    verdict.pop("_low_events", None)
    verdict.pop("_detect", None)
    verdict.pop("_full_corr_signals", None)
    verdict.pop("_full_corr_logs", None)
    verdict["artifacts"] = artifacts

    vp = os.path.join(out_dir, "verdict.json")
    with open(vp, "w") as fh:
        json.dump(verdict, fh, indent=2)

    rp = os.path.join(out_dir, "report.md")
    with open(rp, "w") as fh:
        fh.write(render_report(rundir, verdict))
    artifacts["verdict_json"] = "verdict.json"
    artifacts["report_md"] = "report.md"
    return artifacts


def render_report(rundir, verdict) -> str:
    V = verdict
    ft = V["frametime"]
    h = V["hitches"]
    p = V["periodicity"]
    L = []
    L.append(f"# Stutter report — {V['run_id']}")
    L.append("")
    L.append(f"- run-dir: `{V['run_dir']}`")
    L.append(f"- window: {V['window']['duration_s']/60.0:.1f} min after warm-up "
             f"(warm-up source: {V['window']['warmup_source']}), "
             f"{V['window']['n_frames']} frames")
    L.append(f"- hitch rule: {V['hitch_definition']['rule']} "
             f"(K={V['config']['k']}, W={V['config']['w_s']}s, "
             f"FLOOR={V['config']['floor_ms']:.1f} ms, "
             f"merge<={V['config']['merge_gap_ms']:.0f} ms)")
    L.append("")
    L.append("## Hitches")
    L.append(f"- **{h['count']} hitches** ({h['per_min']:.2f}/min); "
             f"worst {h['worst_ms']:.1f} ms; median {h['median_ms']:.1f} ms")
    L.append(f"- isolated/sparse hitches (>15 s from any other): {h.get('isolated_count', 0)} "
             f"({h.get('sparse_per_min', float('nan')):.2f}/min)")
    L.append(f"- low-severity tier: {h['low_count']} ({h['low_per_min']:.2f}/min)")
    L.append("")
    L.append("## Frametimes")
    L.append(f"- p50 {ft['p50_ms']:.2f} ms | p95 {ft['p95_ms']:.2f} ms | p99 {ft['p99_ms']:.2f} ms")
    L.append(f"- 1% low **{ft['fps_1pct_low']:.1f} fps**, 0.1% low **{ft['fps_0.1pct_low']:.1f} fps**, "
             f"mean {ft['mean_fps']:.1f} fps")
    L.append(f"- frames below 50% of cap: {100*ft['frame_drop_frac']:.2f}%")
    L.append("")
    dq = V.get("data_quality") or {}
    if dq:
        L.append("## Data quality")
        L.append(f"- frametime rows: {dq.get('rows_kept', 0)} kept / "
                 f"{dq.get('rows_total', 0)} read; "
                 f"**{dq.get('rows_rejected', 0)} rejected** "
                 f"(> {dq.get('max_plausible_ms', 0):.0f} ms / non-positive / non-finite)")
        L.append("")
    L.append("## Periodicity")
    L.append(f"- verdict: **{p['kind']}** (window {p['window_min']:.1f} min, "
             f"sparse assessable: {p['sparse_assessable']})")
    for band in ("steady", "sparse", "sparse_residual"):
        b = p.get(band)
        if not b:
            continue
        L.append(f"- {band}: period {b['period_s']:.2f} s "
                 f"(spectral peak {b['spectral_peak_s']:.2f} s, source {b['period_source']}) "
                 f"+- {b.get('period_err_s') if b.get('period_err_s') is not None else float('nan'):.2f} s, "
                 f"p={b['p_value']:.4g}, significant={b['significant']}, "
                 f"fraction explained {b['fraction_explained']:.2f}")
    for w in p.get("warnings", []):
        L.append(f"- WARNING: {w}")
    L.append("")
    sp = V.get("sparse") or {}
    if sp:
        L.append("## Sparse hitches (explicit assessment)")
        L.append(f"- assessment: **{sp.get('label', sp.get('assessment', 'none'))}** "
                 f"({sp.get('n_sparse_candidates', 0)} severe candidate(s) of "
                 f"{sp.get('n_primary_hitches', 0)} primary; severity gate "
                 f"{sp.get('severity_min_ms', 0):.1f} ms"
                 + (f", steady phase {sp['steady_period_s']:.2f} s removed"
                    if sp.get('residual_applied') else "") + ")")
        if np.isfinite(sp.get("rate_per_min", float("nan"))):
            lo, hi = sp.get("rate_ci95_per_min", [float("nan"), float("nan")])
            L.append(f"- rate: {sp['rate_per_min']:.2f}/min "
                     f"(95% CI {lo:.2f}-{hi:.2f}, {sp.get('rate_ci_method')})")
        iq = sp.get("interval_quantiles_s") or {}
        if iq.get("count"):
            L.append(f"- intervals (s): p50 {iq.get('p50_s', float('nan')):.1f}, "
                     f"p90 {iq.get('p90_s', float('nan')):.1f}, "
                     f"CV {iq.get('cv', float('nan')):.2f}")
        mc = sp.get("mode_cluster") or {}
        if sp.get("mode_s") is not None:
            L.append(f"- interval mode {sp['mode_s']:.1f} s; modal cluster "
                     f"n={mc.get('n', 0)} cv="
                     f"{(mc.get('cv') if mc.get('cv') is not None else float('nan')):.3f} "
                     f"frac={mc.get('fraction', float('nan')):.2f}")
        for c in sp.get("caveats", []):
            L.append(f"- CAVEAT: {c}")
        L.append("")
    L.append("## What moved around hitches")
    sig = V["correlation"]["signals"][:15]
    if sig:
        L.append("| signal.column | feature | cliff's d | z | p | q | hitch | control |")
        L.append("|---|---|---|---|---|---|---|---|")
        for r in sig:
            qv = r.get("q_value")
            L.append(f"| {r['signal']}.{r['column']} | {r['feature']} | "
                     f"{r.get('cliffs_delta', float('nan')):+.2f} | "
                     f"{r['z']:.2f} | {r['p_value']:.3g} | "
                     f"{('n/a' if qv is None else f'{qv:.2g}')} | "
                     f"{r['hitch_mean']:.3g} | {r['control_mean']:.3g} |")
    else:
        L.append("_no signal had enough samples around hitches_")
    logs = V["correlation"]["logs"][:8]
    if logs:
        L.append("")
        L.append("| log | near hitch | near control | template |")
        L.append("|---|---|---|---|")
        for r in logs:
            L.append(f"| {r['log']} | {r['near_hitch']} | {r['near_control']} | "
                     f"`{r['template'][:70]}` |")
    L.append("")
    L.append(blocked_mod.render_blocked_md(V.get("blocked", {"available": False, "reason": "missing"})))
    L.append("## Artifacts")
    for k, v in V.get("artifacts", {}).items():
        L.append(f"- `{v}`")
    L.append("")
    return "\n".join(L) + "\n"
