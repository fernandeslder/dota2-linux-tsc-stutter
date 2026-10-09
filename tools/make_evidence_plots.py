#!/usr/bin/env python3
"""Evidence plots for README/REPORT (run from the project with runs/ present). Writes docs/plots/ev_*.png."""
import csv, json, os, math
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
ROOT = os.path.join(os.path.dirname(__file__), "..")
R = f"{ROOT}/runs"; O = f"{ROOT}/docs/plots"
RED, BLUE, GREEN, GREY, ORANGE = "#c0392b", "#2e86c1", "#1e8449", "#7f8c8d", "#d68910"

def verdict(run): return json.load(open(f"{R}/live-{run}/out/verdict.json"))
def hits(run):
    return [(float(h["t_epoch"]), float(h["magnitude_ms"])) for h in csv.DictReader(open(f"{R}/live-{run}/out/hitches.csv"))]
def frames(run):
    return [(float(a), float(b)) for a, b in list(csv.reader(open(f"{R}/live-{run}/frametimes.csv")))[1:]]
def events(run):
    return [(float(r[0]), r[1], r[2] if len(r) > 2 else "") for r in csv.reader(open(f"{R}/live-{run}/events.csv")) if r and r[0][0].isdigit()]
def hpm(run):
    h = verdict(run)["hitches"]; return h["per_min"] or 0.0
def worst(run):
    w = verdict(run)["hitches"]["worst_ms"]; return w if w == w and w else 0.0

# ---- 1. experiment matrix -------------------------------------------------------------------------------------------
rows = [  # (label, run, group)   group: pre / diag(pre-fix controls) / post
 ("baseline #1 (spectate)", "baseline-1", "pre"), ("baseline #2", "baseline-2", "pre"), ("baseline #3", "baseline-3", "pre"),
 ("+ instrumentation (blocked-on sampler)", "D1-blocked", "pre"), ("Steam overlay layer OFF", "A1-overlay-off", "ctl"),
 ("SDL Wayland instead of XWayland", "C1-sdl-wayland", "ctl"), ("NVIDIA IRQ moved off cpu0", "R1-irq-cpu31", "ctl"),
 ("DEMO: native, idle", "E1-demohero", "pre"), ("DEMO: audio off (-nosound)", "C2-nosound", "ctl"),
 ("DEMO: minimal instrumentation", "M1-min", "ctl"), ("DEMO: nvidia-powerd stopped", "N1-powerd-off", "ctl"),
 ("DEMO: gamescope", "G1-gamescope", "ctl"), ("DEMO: sched_autogroup toggled", "AG1-autogroup", "ctl"),
 ("DEMO: Proton Experimental (1 min)", "P1-proton-demo", "ctl"),
 ("Dota pinned OFF cpu0 (spectate)", "T2-spectate-no-cpu0", "post"), ("DEMO: pinned off cpu0", "T1-no-cpu0", "post"),
 ("CPU0 TSC re-aligned (spectate)", "TS1-tsc-fixed", "post"), ("FINAL PROOF #1 (spectate)", "FP1", "post"),
 ("FINAL PROOF #2 (20 min)", "FP2", "post"), ("FINAL PROOF #3", "FP3", "post"),
]
col = {"pre": RED, "ctl": ORANGE, "post": GREEN}
fig, ax = plt.subplots(figsize=(10, 7.2))
for i, (lab, run, g) in enumerate(rows[::-1]):
    v = hpm(run); ax.barh(i, v, color=col[g]); w = worst(run)
    ax.text(v + 0.6, i, (f"{v:.1f}/min, worst {w/1000:.2f} s" if w >= 1000 else f"{v:.1f}/min, worst {w:.0f} ms") if v > 0 else "0 hitches", va="center", fontsize=7.5)
ax.set_yticks(range(len(rows))); ax.set_yticklabels([r[0] for r in rows[::-1]], fontsize=8)
ax.set_xlabel("hitches per minute (6-min windows; lower is better)"); ax.set_xlim(0, 75)
ax.set_title("Every A/B condition measured with the detector", fontsize=11)
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color=RED, label="unchanged / pre-fix"), Patch(color=ORANGE, label="pre-fix control (no effect)"), Patch(color=GREEN, label="CPU0 avoided / TSC fixed")], loc="lower right", fontsize=8)
fig.tight_layout(); fig.savefig(f"{O}/ev_experiment_matrix.png", dpi=130); plt.close(fig)

# ---- 2. hitch size distribution: the 2.95 s signature ----------------------------------------------------------------
pre_runs = ["baseline-1", "baseline-2", "baseline-3", "D1-blocked", "A1-overlay-off", "C1-sdl-wayland", "R1-irq-cpu31", "E1-demohero", "C2-nosound", "M1-min", "N1-powerd-off", "G1-gamescope", "AG1-autogroup"]
post_runs = ["FP1", "FP2", "FP3", "TS1-tsc-fixed", "T2-spectate-no-cpu0", "T1-no-cpu0", "H0-demo-fixed", "H2-threads-16", "H1b-threads-unset", "H3-fpsmax0", "P2-proton-fixed"]
def mags(rs):
    out = []
    for r in rs: out += [m for _, m in hits(r) if m >= 40]
    return np.array(out)
mp, mq = mags(pre_runs), mags(post_runs)
bins = np.logspace(math.log10(40), math.log10(4500), 32)
fig, ax = plt.subplots(1, 2, figsize=(11, 4))
ax[0].hist(mp, bins=bins, color=RED, alpha=.8, label=f"before fix: {len(mp)} hitches >= 40 ms ({len(pre_runs)} runs)")
ax[0].hist(mq, bins=bins, color=GREEN, alpha=.8, label=f"after fix / off cpu0: {len(mq)} ({len(post_runs)} runs)")
ax[0].axvline(2950, color="k", ls="--", lw=1); ax[0].text(2500, ax[0].get_ylim()[1] * .85, "2.95 s =\nCPU0 TSC offset", ha="right", fontsize=8)
ax[0].set_xscale("log"); ax[0].set_xlabel("hitch size (ms, log)"); ax[0].set_ylabel("count"); ax[0].legend(fontsize=7.5, loc="upper left"); ax[0].set_title("Size of every hitch >= 40 ms", fontsize=10)
wp = sorted([worst(r) for r in pre_runs if worst(r)]); wq = sorted([worst(r) for r in post_runs if worst(r)])
ax[1].scatter(range(len(wp)), wp, color=RED, label="worst hitch per run, before"); ax[1].scatter(range(len(wp), len(wp) + len(wq)), wq, color=GREEN, label="after")
ax[1].axhline(2950, color="k", ls="--", lw=1); ax[1].axhline(100, color=GREY, ls=":", lw=1); ax[1].text(0.2, 2650, "TSC offset 2.95 s", fontsize=8); ax[1].text(len(wp) + .2, 112, "100 ms limit", fontsize=8, color=GREY)
ax[1].set_yscale("log"); ax[1].set_xticks([]); ax[1].set_ylabel("ms (log)"); ax[1].set_title("Worst hitch of each run (max 3.6 s = offset + a few frames)", fontsize=10); ax[1].legend(fontsize=7.5, loc="center right")
fig.tight_layout(); fig.savefig(f"{O}/ev_hitch_sizes.png", dpi=130); plt.close(fig)

# ---- 3. same-session affinity experiment ---------------------------------------------------------------------------
run = "AF1-phases"; fr = frames(run); ev = [e for e in events(run) if e[1].startswith("phase:")]
t0 = ev[0][0]; hh = hits(run)
fig, ax = plt.subplots(2, 1, figsize=(11, 5.6), gridspec_kw={"height_ratios": [3, 1.3]})
tt = np.array([t - t0 for t, _ in fr]); ff = np.array([f for _, f in fr])
step = max(1, len(tt) // 60000); ax[0].plot(tt[::step], ff[::step], lw=.35, color="#34495e")
names = {"all1": "all CPUs", "no0a": "no CPU0", "no16a": "no CPU16", "all2": "all CPUs", "no0b": "no CPU0", "no16b": "no CPU16"}
bounds = [(e[0] - t0, e[1].split(":")[1]) for e in ev]; ends = [b[0] for b in bounds[1:]] + [tt.max()]
rates = []
for (s, n), e in zip(bounds, ends):
    e = min(e, tt.max())
    if n == "end" or e - s < 20: continue
    cnt = sum(1 for t, _ in hh if s <= t - t0 < e); rate = cnt / ((e - s) / 60); rates.append((names.get(n, n), rate))
    good = n.startswith("no0"); ax[0].axvspan(s, e, color=GREEN if good else RED, alpha=.12)
    ax[0].text((s + e) / 2, 3000, f"{names.get(n,n)}\n{rate:.1f} hitches/min", ha="center", va="top", fontsize=8)
ax[0].set_xlim(-5, tt.max() + 5); ax[0].set_yscale("log"); ax[0].set_ylim(3, 4000); ax[0].set_ylabel("frametime ms"); ax[0].set_xlabel("seconds into the session (Demo Hero, one running game; affinity changed live with taskset)")
ax[0].set_title("Same game process, only the allowed CPUs change: stalls vanish exactly when CPU0 is excluded", fontsize=10)
ax[1].bar(range(len(rates)), [r for _, r in rates], color=[GREEN if "no CPU0" in n else RED for n, _ in rates])
ax[1].set_xticks(range(len(rates))); ax[1].set_xticklabels([n for n, _ in rates], fontsize=8); ax[1].set_ylabel("hitches/min")
fig.tight_layout(); fig.savefig(f"{O}/ev_affinity_phases.png", dpi=130); plt.close(fig)

# ---- 4. where was the busiest Dota thread during hitches ------------------------------------------------------------
def busiest(run):
    th = list(csv.DictReader(open(f"{R}/live-{run}/threads.csv"))); T = np.array([float(r["t_epoch"]) for r in th]); C = np.array([int(float(r["busiest_cpu"])) if r["busiest_cpu"] else -1 for r in th])
    H = [(t, m / 1000) for t, m in hits(run) if m > 150]
    allc = np.bincount(C[C >= 0], minlength=32) / max(1, (C >= 0).sum())
    mask = np.zeros(len(T), bool)
    for t, m in H: mask |= (T >= t - m) & (T <= t)
    hc = np.bincount(C[mask & (C >= 0)], minlength=32) / max(1, (mask & (C >= 0)).sum())
    return allc, hc, len(H)
fig, ax = plt.subplots(1, 3, figsize=(12, 3.4), sharey=True)
for a, run, title in zip(ax, ["baseline-2", "E1-demohero", "D1-blocked"], ["live spectate (baseline-2)", "idle Demo Hero", "live spectate (D1)"]):
    try:
        allc, hc, n = busiest(run)
    except Exception as e:
        a.text(.5, .5, f"n/a: {e}", transform=a.transAxes); continue
    x = np.arange(32); a.bar(x - .2, allc, .4, color=GREY, label="all the time"); a.bar(x + .2, hc, .4, color=RED, label=f"during hitches >150 ms (n={n})")
    a.set_title(title, fontsize=9); a.set_xlabel("CPU number the busiest Dota thread ran on")
ax[0].set_ylabel("share of samples"); ax[0].legend(fontsize=7.5)
fig.suptitle("The stall happens when Dota's busy thread is on CPU0", fontsize=10); fig.tight_layout(); fig.savefig(f"{O}/ev_busiest_cpu.png", dpi=130); plt.close(fig)

# ---- 5. TSC offsets of all 32 CPUs ---------------------------------------------------------------------------------
def tsc(path):
    return [float(l.split("=")[1]) for l in open(path) if l.startswith("cpu")]
b = tsc(f"{ROOT}/results-evidence/tsc_check_before.txt"); a_ = tsc(f"{ROOT}/results-evidence/tsc_check_after.txt")
fig, ax = plt.subplots(1, 2, figsize=(11, 3.4), sharey=False)
ref_b = b[1]; ref_a = a_[1]
ax[0].bar(range(32), [x - ref_b for x in b], color=[RED if i == 0 else GREY for i in range(32)]); ax[0].set_title("before: TSC offset of each CPU relative to CPU1 (s)", fontsize=9)
ax[1].bar(range(32), [(x - ref_a) * 1e6 for x in a_], color=GREEN); ax[1].set_title("after tsc-resync: same quantity in microseconds", fontsize=9)
for x_ in ax: x_.set_xlabel("CPU")
ax[0].text(1.5, -2.9, "CPU0: -2.950 s", color=RED, fontsize=9, va="center")
fig.tight_layout(); fig.savefig(f"{O}/ev_tsc_per_cpu.png", dpi=130); plt.close(fig)

# ---- 6. lows before/after ---------------------------------------------------------------------------------------------
def lows(run):
    f = verdict(run)["frametime"]; return f.get("fps_1pct_low") or f.get("fps_1.0pct_low"), f.get("fps_0.1pct_low")
sets = [("before", ["baseline-1", "baseline-2", "baseline-3"], RED), ("after (FP1-3)", ["FP1", "FP2", "FP3"], GREEN)]
fig, ax = plt.subplots(figsize=(6.5, 3.6)); x = 0
for name, rs, c in sets:
    for r in rs:
        v = verdict(r)["frametime"]; keys = [k for k in v if "low" in k]
        l1 = [v[k] for k in keys if k.startswith("fps_1")][0]; l01 = v["fps_0.1pct_low"]
        ax.bar(x - .18, l1, .36, color=c, alpha=.6); ax.bar(x + .18, l01, .36, color=c); x += 1
    x += .6
ax.set_xticks([1, 4.6]); ax.set_xticklabels(["before (3 runs)", "after (FP1-3)"]); ax.set_ylabel("fps"); ax.set_title("1% low (light) and 0.1% low (dark) frame rate", fontsize=10)
fig.tight_layout(); fig.savefig(f"{O}/ev_lows.png", dpi=130); plt.close(fig)
# ---- 7. detector's own report plots, before vs after ------------------------------------------------------------------
from PIL import Image
def sheet(pairs, out, w=1100):
    ims = []
    for title, path in pairs:
        im = Image.open(path).convert("RGB"); im = im.resize((w, int(im.height * w / im.width))); ims.append((title, im))
    H = sum(i.height for _, i in ims) + 34 * len(ims); sh = Image.new("RGB", (w, H), "white")
    from PIL import ImageDraw; d = ImageDraw.Draw(sh); y = 0
    for t, i in ims:
        d.text((8, y + 10), t, fill=(20, 20, 20)); sh.paste(i, (0, y + 30)); y += i.height + 34
    sh.save(out, optimize=True)
for kind in ("frametime_trace", "hitch_timeline", "interval_histogram"):
    sheet([(f"BEFORE  live-baseline-2   ({kind})", f"{R}/live-baseline-2/out/{kind}.png"), (f"AFTER   live-FP2 (20 min)   ({kind})", f"{R}/live-FP2/out/{kind}.png")], f"{O}/ev_detector_{kind}.png")
print("evidence plots written")
