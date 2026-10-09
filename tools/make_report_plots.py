#!/usr/bin/env python3
"""Plots for REPORT.md (reads runs/live-*/out/verdict.json and frametimes.csv)."""
import csv, json, os, sys
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
R = os.path.join(os.path.dirname(__file__), "..", "runs"); O = os.path.join(os.path.dirname(__file__), "..", "docs", "plots")
def V(run):
    return json.load(open(f"{R}/live-{run}/out/verdict.json"))
def hp(run):
    h = V(run)["hitches"]; return h["per_min"] or 0.0, (h["worst_ms"] if h["worst_ms"] == h["worst_ms"] and h["worst_ms"] else 0.0)
groups = [
 ("baseline\n(spectate)", ["baseline-1", "baseline-2", "baseline-3", "D1-blocked", "A1-overlay-off", "C1-sdl-wayland"], "#c0392b"),
 ("pinned off CPU0 /\nTSC fixed (spectate)", ["T2-spectate-no-cpu0", "TS1-tsc-fixed"], "#2e86c1"),
 ("final proof\n(spectate, persistent fix)", ["FP1", "FP2", "FP3"], "#1e8449"),
]
fig, ax = plt.subplots(1, 2, figsize=(11, 4))
x = 0; ticks = []; labels = []
for name, runs, col in groups:
    xs = []
    for r in runs:
        pm, w = hp(r); ax[0].bar(x, pm, color=col); ax[1].bar(x, max(w, 1), color=col); xs.append(x); x += 1
    ticks.append(sum(xs) / len(xs)); labels.append(name); x += 1
for a, t in zip(ax, ["hitches per minute (lower is better)", "worst hitch, ms (log scale)"]):
    a.set_xticks(ticks); a.set_xticklabels(labels, fontsize=8); a.set_title(t, fontsize=10)
ax[1].set_yscale("log"); ax[1].axhline(100, color="k", lw=0.8, ls="--"); ax[1].text(0, 120, "fixed-definition limit 100 ms", fontsize=7)
fig.tight_layout(); fig.savefig(f"{O}/before_after.png", dpi=130); plt.close(fig)
def trace(run, t0=0, n=6 * 60):
    rows = [(float(a), float(b)) for a, b in list(csv.reader(open(f"{R}/live-{run}/frametimes.csv")))[1:]]
    ev = [(float(a), b) for a, b, *_ in csv.reader(open(f"{R}/live-{run}/events.csv")) if b == "warmup_end"]
    s = ev[0][0]; return [(t - s, f) for t, f in rows if 0 <= t - s <= n]
fig, ax = plt.subplots(2, 1, figsize=(11, 5), sharex=True, sharey=True)
for a, run, title, col in [(ax[0], "baseline-2", "before: live spectate, unchanged (baseline-2)", "#c0392b"), (ax[1], "FP1", "after: live spectate, TSC fix in place (FP1)", "#1e8449")]:
    d = trace(run); a.plot([t for t, _ in d], [f for _, f in d], lw=0.4, color=col); a.set_ylabel("frametime ms"); a.set_title(title, fontsize=9)
ax[1].set_xlabel("seconds after warm-up"); ax[1].set_yscale("log"); fig.tight_layout(); fig.savefig(f"{O}/frametime_before_after.png", dpi=130); plt.close(fig)
fig, ax = plt.subplots(figsize=(7, 3))
ax.bar(["cpu0", "cpu1..31"], [19.364, 22.314], color=["#c0392b", "#7f8c8d"]); ax.set_ylim(18, 23)
ax.set_title("TSC offset vs CLOCK_MONOTONIC_RAW per CPU (s): cpu0 is 2.950 s behind", fontsize=9); fig.tight_layout(); fig.savefig(f"{O}/tsc_offsets.png", dpi=130); plt.close(fig)
print("plots written")
