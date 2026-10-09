"""Command-line interface: ``stutter detect|report|compare|selftest|fixed|synth``.

Wired up by ``bin/stutter`` (POSIX sh) and also runnable as ``python3 -m detector.analyze``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from . import compare as compare_mod
from . import fixed as fixed_mod
from . import reporting
from . import selftest as selftest_mod
from . import synth as synth_mod
from .config import DEFAULT_TARGET_FPS, HitchConfig
from .rundir import load_rundir


def _cfg(args) -> HitchConfig:
    cfg = HitchConfig(
        target_fps=getattr(args, "target_fps", DEFAULT_TARGET_FPS),
        k=getattr(args, "k", None) or HitchConfig().k,
        w_s=getattr(args, "w", None) or HitchConfig().w_s,
        merge_gap_ms=getattr(args, "merge_gap_ms", None) or HitchConfig().merge_gap_ms,
    )
    floor = getattr(args, "floor_ms", None)
    if floor:
        cfg.floor_ms = floor
    fmin = getattr(args, "floor_min_ms", None)
    if fmin:
        cfg.floor_min_ms = fmin
    return cfg.resolve()


def _add_hitch_opts(p):
    p.add_argument("--target-fps", type=float, default=DEFAULT_TARGET_FPS,
                   help="fps cap used for the FLOOR and fps-lows (default 144)")
    p.add_argument("--k", type=float, default=None, help="outlier multiplier K (default 2.5)")
    p.add_argument("--w", type=float, default=None, help="rolling-median half-window seconds (default 1.0)")
    p.add_argument("--floor-ms", type=float, default=None, help="absolute FLOOR in ms (overrides default)")
    p.add_argument("--floor-min-ms", type=float, default=None, help="minimum FLOOR in ms (default 12)")
    p.add_argument("--merge-gap-ms", type=float, default=None, help="merge gap in ms (default 100)")
    p.add_argument("--n-perm", type=int, default=None, help="permutation count for periodicity p-values (default 400)")
    p.add_argument("--seed", type=int, default=None, help="RNG seed for permutation/bootstrap nulls")


def build_parser():
    p = argparse.ArgumentParser(prog="stutter", description="Dota 2 stutter detector (analysis)")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("detect", help="hitch events + stats for one run-dir")
    d.add_argument("run_dir")
    d.add_argument("--out", default=None)
    _add_hitch_opts(d)

    r = sub.add_parser("report", help="full verdict: plots + verdict.json + report.md")
    r.add_argument("run_dir")
    r.add_argument("--out", default=None)
    r.add_argument("--no-plots", action="store_true")
    _add_hitch_opts(r)

    c = sub.add_parser("compare", help="A/B compare two sets of runs (A before -- B after)")
    c.add_argument("-a", dest="a", nargs="+", required=True)
    c.add_argument("-b", dest="b", nargs="+", required=True)
    c.add_argument("--out", default=None)
    c.add_argument("--effect-threshold", type=float, default=compare_mod.EFFECT_THRESHOLD)
    _add_hitch_opts(c)

    f = sub.add_parser("fixed", help="check runs against the 'fixed' definition")
    f.add_argument("runs", nargs="+")
    f.add_argument("--def-file", dest="def_path", default=None, help="path to fixed_def.json")
    f.add_argument("--out", default=None)
    _add_hitch_opts(f)

    s = sub.add_parser("selftest", help="synthetic ground-truth validation")
    s.add_argument("--seeds", type=int, default=50, help="clean-trace seeds (false-positive rate)")
    s.add_argument("--scenario-seeds", type=int, default=10, help="seeds per truth scenario")
    s.add_argument("--workdir", default=None)
    s.add_argument("--keep", action="store_true")
    s.add_argument("--out", default=None)
    _add_hitch_opts(s)

    y = sub.add_parser("synth", help="generate a synthetic run-dir (dev/testing)")
    y.add_argument("--kind", choices=["periodic", "sparse", "mixed", "clean"], default="periodic")
    y.add_argument("--seed", type=int, default=0)
    y.add_argument("--duration", type=float, default=None)
    y.add_argument("--period", type=float, default=None, help="periodic/sparse period seconds")
    y.add_argument("--out", required=True, help="output run-dir path")
    return p


def _load(args):
    return load_rundir(args.run_dir)


def cmd_detect(args) -> int:
    rd = _load(args)
    cfg = _cfg(args)
    verdict = reporting.analyze_run(rd, cfg, n_perm=args.n_perm, seed=args.seed)
    out = args.out or os.path.join(rd.path, "out")
    reporting.write_outputs(rd, verdict, out, plots=False)
    print(json.dumps({
        "run_id": verdict["run_id"], "out": out,
        "hitches": verdict["hitches"], "frametime": verdict["frametime"],
        "periodicity_kind": verdict["periodicity"]["kind"],
        "steady": verdict["periodicity"]["steady"],
        "sparse": verdict["periodicity"]["sparse"],
    }, indent=2, default=str))
    return 0


def cmd_report(args) -> int:
    rd = _load(args)
    cfg = _cfg(args)
    verdict = reporting.analyze_run(rd, cfg, n_perm=args.n_perm, seed=args.seed)
    out = args.out or os.path.join(rd.path, "out")
    arts = reporting.write_outputs(rd, verdict, out, plots=not args.no_plots)
    print(json.dumps({"run_id": verdict["run_id"], "out": out, "artifacts": arts,
                      "verdict": verdict["periodicity"]["kind"],
                      "hitches_per_min": verdict["hitches"]["per_min"]}, indent=2, default=str))
    return 0


def cmd_compare(args) -> int:
    cfg = _cfg(args)
    va, vb = [], []
    for pth in args.a:
        va.append(reporting.analyze_run(load_rundir(pth), cfg, n_perm=args.n_perm, seed=args.seed))
    for pth in args.b:
        vb.append(reporting.analyze_run(load_rundir(pth), cfg, n_perm=args.n_perm, seed=args.seed))
    cmp = compare_mod.compare_runs(va, vb, effect_threshold=args.effect_threshold)
    out = args.out or "compare-out"
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "compare.json"), "w") as fh:
        json.dump(cmp, fh, indent=2, default=str)
    md = compare_mod.render_compare_md(cmp)
    with open(os.path.join(out, "compare.md"), "w") as fh:
        fh.write(md)
    print(md)
    print(f"[compare] wrote {out}/compare.json and {out}/compare.md")
    return 0


def cmd_fixed(args) -> int:
    cfg = _cfg(args)
    vs = [reporting.analyze_run(load_rundir(pth), cfg, n_perm=args.n_perm, seed=args.seed)
          for pth in args.runs]
    defn = fixed_mod.load_def(args.def_path)
    res = fixed_mod.check_fixed(vs, defn)
    out = args.out or "fixed-out"
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "fixed.json"), "w") as fh:
        json.dump(res, fh, indent=2, default=str)
    md = fixed_mod.render_fixed_md(res)
    with open(os.path.join(out, "fixed.md"), "w") as fh:
        fh.write(md)
    print(md)
    print(f"[fixed] wrote {out}/fixed.json and {out}/fixed.md")
    return 0 if res["passed"] else 2


def cmd_selftest(args) -> int:
    cfg = _cfg(args)
    res = selftest_mod.run_selftest(workdir=args.workdir, n_seeds=args.seeds,
                                    scenario_seeds=args.scenario_seeds,
                                    n_perm=args.n_perm or 250, cfg=cfg, keep=args.keep)
    if args.out:
        os.makedirs(args.out, exist_ok=True)
        with open(os.path.join(args.out, "selftest.json"), "w") as fh:
            json.dump(res, fh, indent=2, default=str)
        print(f"[selftest] wrote {args.out}/selftest.json")
    return 0 if res["passed"] else 1


def cmd_synth(args) -> int:
    kwargs = dict(seed=args.seed)
    if args.duration:
        kwargs["duration_s"] = args.duration
    if args.kind == "periodic":
        spec = synth_mod.periodic_spec(**kwargs)
        if args.period:
            spec.periodic_s = args.period
    elif args.kind == "sparse":
        spec = synth_mod.sparse_spec(**kwargs)
        if args.period:
            spec.sparse_s = args.period
    elif args.kind == "mixed":
        spec = synth_mod.mixed_spec(**kwargs)
    else:
        spec = synth_mod.clean_spec(**kwargs)
    gt = synth_mod.generate(spec, args.out)
    print(json.dumps({"out": args.out, "n_gt_hitches": len(gt["hitches"]),
                      "periodic_s": gt["periodic_s"], "sparse_s": gt["sparse_s"]}, indent=2))
    return 0


COMMANDS = {"detect": cmd_detect, "report": cmd_report, "compare": cmd_compare,
            "fixed": cmd_fixed, "selftest": cmd_selftest, "synth": cmd_synth}


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "compare" and "--" in argv:
        i = argv.index("--")
        argv = ["compare", "-a"] + argv[1:i] + ["-b"] + argv[i + 1:]
    parser = build_parser()
    args = parser.parse_args(argv)
    return COMMANDS[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
