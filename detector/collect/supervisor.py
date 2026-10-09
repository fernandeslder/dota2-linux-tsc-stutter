"""Collector supervisor: one process, one clock, many sampler threads.

Started (detached) by `stutter collect start`; stopped by `stutter collect stop`
(SIGTERM).  It owns every child process (journalctl) and tears them all down, so
no orphans survive a stop.  It writes the run-dir contract files.
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
import threading
import time
from typing import List, Optional

from . import mangohud, profiles, util
from .rundir import CsvWriter, LogWriter, RunDir
from .collectors import Sampler
from .collectors import hwmon as m_hwmon
from .collectors import nvidia as m_nvidia
from .collectors import offcpu as m_offcpu
from .collectors import procfs as m_procfs
from .collectors import subproc as m_subproc
from .collectors import threads as m_threads


def build_samplers(run_dir: RunDir, profile: dict, game_pid: Optional[int]) -> List[Sampler]:
    """Instantiate the samplers selected by the profile, with their intervals."""
    out: List[Sampler] = []

    def want(name: str) -> bool:
        return profiles.sampler_enabled(profile, name)

    def iv(name: str) -> float:
        return profiles.sampler_interval(profile, name)

    if want("gpu"):
        s = m_nvidia.GpuSampler()
        s.interval = iv("gpu")
        out.append(s)
    if want("cpu"):
        s = m_procfs.CpuUtil()
        s.interval = iv("cpu")
        out.append(s)
    if want("cpufreq"):
        s = m_procfs.CpuFreq()
        s.interval = iv("cpufreq")
        out.append(s)
    if want("sys"):
        s = m_procfs.SysStats()
        s.interval = iv("sys")
        out.append(s)
    if want("mem"):
        s = m_procfs.MemStats()
        s.interval = iv("mem")
        out.append(s)
    if want("disk"):
        s = m_procfs.DiskStats()
        s.interval = iv("disk")
        out.append(s)
    if want("net"):
        s = m_procfs.NetDev()
        s.interval = iv("net")
        out.append(s)
    if want("threads"):
        s = m_threads.ThreadSampler(pid=game_pid)
        s.interval = iv("threads")
        out.append(s)
    if want("hwmon"):
        s = m_hwmon.HwmonSampler()
        s.interval = iv("hwmon")
        out.append(s)
    if want("net_tcp"):
        s = m_subproc.TcpInfo(raw_path=os.path.join(run_dir.raw, "net_tcp_ss.log"))
        s.interval = iv("net_tcp")
        out.append(s)
    if want("pipewire"):
        s = m_subproc.PipeWire()
        s.interval = iv("pipewire")
        out.append(s)
    if want("kwin"):
        s = m_subproc.KWinState()
        s.interval = iv("kwin")
        out.append(s)
    return out


class Supervisor:
    def __init__(self, run_dir: RunDir, profile: dict, game_pid: Optional[int] = None,
                 duration: float = 0.0, mangohud_offset: float = 0.0,
                 mangohud_enabled: bool = True, offcpu_enabled: bool = True,
                 offcpu_hz: Optional[float] = None, offcpu_stacks: bool = False,
                 offcpu_native: bool = True, deep: bool = False):
        self.run_dir = run_dir
        self.profile = profile
        self.game_pid = game_pid
        self.duration = duration
        self.mangohud_offset = mangohud_offset
        self.mangohud_enabled = mangohud_enabled
        self.offcpu_enabled = offcpu_enabled
        self.offcpu_hz = offcpu_hz
        self.offcpu_stacks = offcpu_stacks
        self.offcpu_native = offcpu_native
        self.deep = deep
        self.offcpu: Optional[m_offcpu.OffCpuSampler] = None
        self.deep_runner = None
        self.stop_event = threading.Event()
        self.samplers: List[Sampler] = []
        self._threads: List[threading.Thread] = []
        self._writers = {}
        self.mh: Optional[mangohud.MangoHudWatcher] = None
        self.tailers = []
        self._log_writers = {}
        self._active_samplers: List[str] = []
        self._skipped: dict = {}
        self._started_epoch = util.epoch()
        self._pinned: Optional[list] = None

    # -- setup ------------------------------------------------------------
    def _apply_priority(self) -> None:
        util.set_low_priority(int(self.profile.get("nice", 19)))
        util.set_io_priority(self.profile.get("ionice", "idle"))

    def _apply_affinity(self) -> None:
        if self.profile.get("affinity") != "avoid-game":
            return
        pid = self.game_pid or m_threads.find_game_pid()
        if not pid:
            return
        g = util.process_cpus(pid)
        allc = set(util.all_cpus())
        comp = sorted(allc - g)
        if not comp or comp == sorted(allc):
            return
        if util.set_affinity(comp):
            self._pinned = comp
            self.run_dir.append_event("collectors_pinned", f"cpus={comp} game_pid={pid}")

    def _start_offcpu(self) -> None:
        """Start the off-CPU sampler (+ optional D-state stacks / deep profile)."""
        oc = self.profile.get("samplers", {}).get("offcpu", {})
        if self.offcpu_enabled and oc.get("enabled", True):
            hz = self.offcpu_hz or float(oc.get("hz", 100.0))
            self.offcpu = m_offcpu.OffCpuSampler(
                self.run_dir, pid=self.game_pid, hz=hz,
                keepalive_ms=float(oc.get("keepalive_ms", 1000.0)),
                duration=self.duration, native=self.offcpu_native,
                capture_stacks=self.offcpu_stacks or bool(oc.get("stacks", False)))
            self.offcpu.start()
            if self.offcpu.mode == "python" and self.offcpu_native:
                self.run_dir.append_event(
                    "offcpu_fallback", "no C compiler; using the Python sampler")
            self.run_dir.append_event(
                "offcpu_start",
                f"mode={self.offcpu.mode} hz={hz} pid={self.game_pid or 0}")
        if self.deep:
            from . import deep as m_deep
            self.deep_runner = m_deep.DeepOffCpu(self.run_dir, lambda: self.game_pid)
            self.deep_runner.start()

    def _monitor_loop(self) -> None:
        """Periodically re-discover the game and re-apply affinity."""
        while not self.stop_event.wait(5.0):
            if self.game_pid is None:
                pid = m_threads.find_game_pid()
                if pid:
                    self.game_pid = pid
                    for s in self.samplers:
                        if isinstance(s, m_threads.ThreadSampler) and not s.pid:
                            s.pid = pid
                    if self.offcpu is not None and not self.offcpu.pid:
                        self.offcpu.pid = pid
                    self.run_dir.append_event("game_detected", f"pid={pid}")
                    self.run_dir.update_meta(game_pid=pid)
                    self._apply_affinity()
            elif self._pinned is None:
                self._apply_affinity()

    # -- run --------------------------------------------------------------
    def run(self) -> int:
        rd = self.run_dir
        rd.create()
        self._apply_priority()
        self._apply_affinity()

        # meta: collector identity + gpu info + game pid
        gpu = m_nvidia.gpu_info()
        procs = m_nvidia.running_processes()
        meta = rd.read_meta()
        if self.game_pid is None:
            self.game_pid = m_threads.find_game_pid()
        rd.write_meta({
            **meta,
            "collector_pid": os.getpid(),
            "collector_start_epoch": self._started_epoch,
            "collector_profile": self.profile["profile"],
            "gpu": gpu or meta.get("gpu", {}),
            "gpu_processes_at_start": procs,
            "game_pid": self.game_pid,
            "collector_priority": {"nice": self.profile.get("nice"),
                                   "ionice": self.profile.get("ionice"),
                                   "affinity": self.profile.get("affinity")},
        })
        rd.write_collector_state({
            "pid": os.getpid(),
            "profile": self.profile["profile"],
            "started_epoch": self._started_epoch,
            "run_dir": rd.root,
            "state": "running",
        })
        rd.append_event("collectors_start", f"pid={os.getpid()} profile={self.profile['profile']}")

        self.samplers = build_samplers(rd, self.profile, self.game_pid)

        for s in self.samplers:
            th = threading.Thread(target=self._sampler_loop, args=(s,),
                                  name=f"s-{s.name}", daemon=True)
            self._threads.append(th)
            th.start()

        self._start_offcpu()

        # MangoHud frametime watcher (per-frame CSV)
        if self.mangohud_enabled:
            fwriter = CsvWriter(rd.frametimes_path, ["frametime_ms"])
            self._writers["__frametimes__"] = fwriter
            self.mh = mangohud.MangoHudWatcher(
                mangohud.raw_dir(rd.root), fwriter, offset_s=self.mangohud_offset)
            self.mh.start()

        # text log streams
        self._start_logs()

        monitor = threading.Thread(target=self._monitor_loop, name="game-monitor", daemon=True)
        monitor.start()
        self._threads.append(monitor)

        # write the list of active samplers into meta
        rd.update_meta(collector_samplers=sorted(self._active_samplers),
                       collector_skipped=self._skipped)

        if self.duration and self.duration > 0:
            def _timer():
                if not self.stop_event.wait(self.duration):
                    self.request_stop("duration_reached")
            threading.Thread(target=_timer, daemon=True).start()

        # main thread waits for a stop request
        while not self.stop_event.wait(0.5):
            pass
        return self._shutdown()

    def _sampler_loop(self, s: Sampler) -> None:
        # prepare() may discover variable columns (disk devices, hwmon sensors,
        # net interfaces), so the CSV writer is created only after it runs.
        try:
            s.prepare()
        except Exception as exc:  # pragma: no cover - environment dependent
            self._skipped[s.name] = str(exc)
            return
        self._active_samplers.append(s.name)
        writer = CsvWriter(self.run_dir.signal_path(s.name), s.columns)
        self._writers[s.name] = writer
        writer.open()
        interval = max(1e-3, float(getattr(s, "interval", 1.0)))
        next_t = time.monotonic()
        while not self.stop_event.is_set():
            t = util.epoch()
            try:
                row = s.sample(t)
                if row is not None:
                    writer.write(t, row)
            except Exception as exc:  # pragma: no cover
                self._skipped[s.name] = f"sample error: {exc}"
            next_t += interval
            delay = next_t - time.monotonic()
            if delay > 0:
                self.stop_event.wait(delay)
            else:
                next_t = time.monotonic()
        try:
            s.teardown()
        finally:
            writer.close()

    def _start_logs(self) -> None:
        wanted = set(self.profile.get("logs", []))
        specs = {
            "journal": ["-o", "short-unix"],
            "kwin": ["-t", "kwin_wayland"],
            "pipewire": ["--user-unit", "pipewire", "--user-unit", "wireplumber",
                         "--user-unit", "pipewire-pulse"],
            "dmesg": ["-k"],
        }
        for name in wanted:
            extra = specs.get(name)
            if extra is None:
                continue
            lw = LogWriter(self.run_dir.log_path(name))
            lw.open()
            self._log_writers[name] = lw
            t = m_subproc.JournalTailer(name, lw, extra)
            t.start()
            self.tailers.append(t)
        # Dota's own console.log (if a path is known / exists)
        meta = self.run_dir.read_meta()
        console = meta.get("dota_console_log")
        if console and os.path.exists(console):
            lw = LogWriter(self.run_dir.log_path("dota-console"))
            lw.open()
            self._log_writers["dota-console"] = lw
            t = m_subproc.FileTailer("dota-console", console, lw)
            t.start()
            self.tailers.append(t)

    def request_stop(self, reason: str = "") -> None:
        if reason:
            self.run_dir.append_event("stop_requested", reason)
        self.stop_event.set()

    def _shutdown(self) -> int:
        # stop tailers first, then samplers, then flush frametimes
        for t in self.tailers:
            try:
                t.stop()
            except Exception:
                pass
        # the off-CPU sampler keeps its own clock so it can be stopped first
        if self.offcpu is not None:
            try:
                self.offcpu.stop()
            except Exception:
                pass
        if self.deep_runner is not None:
            try:
                self.deep_runner.stop()
            except Exception:
                pass
        for th in self._threads:
            th.join(timeout=5)
        if self.mh is not None:
            self.mh.stop()
        for w in self._writers.values():
            try:
                w.close()
            except Exception:
                pass
        for lw in self._log_writers.values():
            try:
                lw.close()
            except Exception:
                pass

        end = util.epoch()
        mh_info = self.mh.info() if self.mh else {}
        offcpu_info = self.offcpu.info() if self.offcpu is not None else None
        deep_info = self.deep_runner.info() if self.deep_runner is not None else None
        self.run_dir.update_meta(
            collector_end_epoch=end,
            collector_duration_s=round(end - self._started_epoch, 3),
            mangohud_log=mh_info.get("log_file"),
            mangohud_birth_ns=mh_info.get("birth_ns"),
            mangohud_t0_epoch=mh_info.get("t0_epoch"),
            mangohud_offset_s=mh_info.get("offset_s"),
            mangohud_n_frames=mh_info.get("n_frames"),
            collector_samplers=sorted(self._active_samplers),
            collector_skipped=self._skipped,
            collector_pinned_cpus=self._pinned,
            offcpu=offcpu_info,
            deep=deep_info,
        )
        self.run_dir.append_event("collectors_stop", f"pid={os.getpid()}")
        state = self.run_dir.read_collector_state()
        state.update({"state": "stopped", "stopped_epoch": end})
        self.run_dir.write_collector_state(state)
        return 0


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(prog="detector.collect.supervisor")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--profile", default="full")
    ap.add_argument("--game-pid", type=int, default=None)
    ap.add_argument("--duration", type=float, default=0.0)
    ap.add_argument("--mangohud-offset", type=float, default=0.0)
    ap.add_argument("--no-mangohud", action="store_true")
    ap.add_argument("--no-offcpu", action="store_true", help="disable the off-CPU sampler")
    ap.add_argument("--offcpu-hz", type=float, default=None, help="off-CPU scan rate (default 100)")
    ap.add_argument("--offcpu-stacks", action="store_true",
                    help="capture kernel stacks of D-state threads (sudo -n, rate-limited)")
    ap.add_argument("--offcpu-no-native", action="store_true",
                    help="force the Python off-CPU fallback (do not build/use the C helper)")
    ap.add_argument("--deep", action="store_true",
                    help="also run the bpftrace off-CPU/sched-switch profile (needs sudo -n)")
    args = ap.parse_args(argv)

    sup = Supervisor(
        RunDir(args.run_dir),
        profiles.get(args.profile),
        game_pid=args.game_pid,
        duration=args.duration,
        mangohud_offset=args.mangohud_offset,
        mangohud_enabled=not args.no_mangohud,
        offcpu_enabled=not args.no_offcpu,
        offcpu_hz=args.offcpu_hz,
        offcpu_stacks=args.offcpu_stacks,
        offcpu_native=not args.offcpu_no_native,
        deep=args.deep,
    )

    def _handler(signum, frame):
        sup.request_stop(f"signal {signum}")

    signal.signal(signal.SIGTERM, _handler)
    signal.signal(signal.SIGINT, _handler)
    try:
        return sup.run()
    except Exception as exc:  # pragma: no cover
        sys.stderr.write(f"supervisor error: {exc}\n")
        try:
            sup.run_dir.append_event("collector_error", str(exc))
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
