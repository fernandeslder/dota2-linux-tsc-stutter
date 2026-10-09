"""procfs / sysfs samplers: CPU, cpufreq, PSI+ctxt, memory, disk, network."""

from __future__ import annotations

import os
from typing import List, Optional

from .. import util
from . import Sampler


class CpuUtil(Sampler):
    name = "cpu"

    def __init__(self, ncpu: int = 0):
        self.ncpu = ncpu or (max(util.all_cpus()) + 1 if util.all_cpus() else 1)
        self.columns = [f"cpu{i}_util" for i in range(self.ncpu)] + ["cpu_util_avg"]
        self._prev = {}

    def _snapshot(self):
        per_cpu, agg, _ = util.parse_proc_stat()
        return per_cpu, agg

    def prepare(self) -> None:
        per_cpu, agg = self._snapshot()
        self._prev = {i: list(v) for i, v in per_cpu}
        self._prev_agg = list(agg) if agg else None

    def sample(self, t: float) -> Optional[list]:
        per_cpu, agg = self._snapshot()
        row = []
        busy_sum = 0.0
        tot_sum = 0.0
        cur = {}
        for i, vals in per_cpu:
            cur[i] = vals
            prev = self._prev.get(i)
            if prev is None or len(prev) != len(vals):
                row.append(0.0)
                continue
            dtot = sum(vals) - sum(prev)
            didle = (vals[3] - prev[3]) + (vals[4] - prev[4])
            util = (1.0 - didle / dtot) * 100.0 if dtot > 0 else 0.0
            row.append(max(0.0, min(100.0, util)))
            busy_sum += (dtot - didle)
            tot_sum += dtot
        self._prev = cur
        avg = (busy_sum / tot_sum * 100.0) if tot_sum > 0 else 0.0
        # keep row length stable even if CPUs hotplugged
        if len(row) < self.ncpu:
            row += [0.0] * (self.ncpu - len(row))
        row = row[: self.ncpu]
        row.append(avg)
        return row


class CpuFreq(Sampler):
    name = "cpufreq"

    def __init__(self, ncpu: int = 0):
        self.ncpu = ncpu or (max(util.all_cpus()) + 1 if util.all_cpus() else 1)
        self.columns = [f"cpu{i}_mhz" for i in range(self.ncpu)]
        self._paths = []

    def prepare(self) -> None:
        for i in range(self.ncpu):
            p = f"/sys/devices/system/cpu/cpu{i}/cpufreq/scaling_cur_freq"
            self._paths.append(p if os.path.exists(p) else None)

    def sample(self, t: float) -> Optional[list]:
        row = []
        for p in self._paths:
            v = util.read_float(p) if p else None
            row.append(v / 1000.0 if v else None)
        return row


class SysStats(Sampler):
    name = "sys"
    columns = [
        "psi_cpu_some_avg10", "psi_cpu_full_avg10",
        "psi_io_some_avg10", "psi_io_full_avg10",
        "psi_mem_some_avg10", "psi_mem_full_avg10",
        "psi_cpu_some_total", "psi_io_some_total", "psi_mem_some_total",
        "ctxt_per_s", "intr_per_s", "forks_per_s",
        "procs_running", "procs_blocked",
        "load1", "load5", "load15",
    ]

    def prepare(self) -> None:
        _, _, ex = util.parse_proc_stat()
        self._prev = ex
        self._prev_t = util.epoch()
        try:
            self._load = [float(x) for x in util.read_text("/proc/loadavg").split()[:3]]
        except (ValueError, IndexError):
            self._load = [0.0, 0.0, 0.0]

    def sample(self, t: float) -> Optional[list]:
        _, _, ex = util.parse_proc_stat()
        dt = max(1e-6, t - self._prev_t)
        p = self._prev

        def rate(key):
            if key in ex and key in p:
                return (ex[key] - p[key]) / dt
            return 0.0

        pc = util.read_pressure("cpu")
        pi = util.read_pressure("io")
        pm = util.read_pressure("memory")
        try:
            self._load = [float(x) for x in util.read_text("/proc/loadavg").split()[:3]]
        except (ValueError, IndexError):
            pass
        self._prev = ex
        self._prev_t = t
        return [
            pc.get("some_avg10", 0.0), pc.get("full_avg10", 0.0),
            pi.get("some_avg10", 0.0), pi.get("full_avg10", 0.0),
            pm.get("some_avg10", 0.0), pm.get("full_avg10", 0.0),
            pc.get("some_total", 0.0), pi.get("some_total", 0.0), pm.get("some_total", 0.0),
            rate("ctxt"), rate("intr"), rate("processes"),
            ex.get("procs_running", 0), ex.get("procs_blocked", 0),
            self._load[0], self._load[1], self._load[2],
        ]


class MemStats(Sampler):
    name = "mem"
    columns = [
        "mem_total_mib", "mem_available_mib", "mem_free_mib", "mem_cached_mib",
        "buffers_mib", "dirty_mib", "writeback_mib", "mem_slab_mib",
        "swap_total_mib", "swap_used_mib",
        "pgmajfault_per_s", "pswpin_per_s", "pswpout_per_s",
        "pgscan_kswapd_per_s", "pgscan_direct_per_s", "allocstall_per_s",
        "pgsteal_kswapd_per_s", "pgsteal_direct_per_s",
    ]
    _VM_KEYS = ["pgmajfault", "pswpin", "pswpout", "pgscan_kswapd", "pgscan_direct",
                "allocstall", "pgsteal_kswapd", "pgsteal_direct"]

    def prepare(self) -> None:
        self._prev = util.parse_vmstat()
        self._prev_t = util.epoch()

    def sample(self, t: float) -> Optional[list]:
        m = util.parse_meminfo()
        v = util.parse_vmstat()
        dt = max(1e-6, t - self._prev_t)

        def vrate(k):
            return (v.get(k, 0.0) - self._prev.get(k, 0.0)) / dt

        self._prev = v
        self._prev_t = t
        mib = 1024.0 * 1024.0
        sw_total = m.get("SwapTotal", 0.0)
        sw_free = m.get("SwapFree", 0.0)
        return [
            m.get("MemTotal", 0.0) / mib, m.get("MemAvailable", 0.0) / mib,
            m.get("MemFree", 0.0) / mib, m.get("Cached", 0.0) / mib,
            m.get("Buffers", 0.0) / mib, m.get("Dirty", 0.0) / mib,
            m.get("Writeback", 0.0) / mib, m.get("Slab", 0.0) / mib,
            sw_total / mib, (sw_total - sw_free) / mib,
            vrate("pgmajfault"), vrate("pswpin"), vrate("pswpout"),
            vrate("pgscan_kswapd"), vrate("pgscan_direct"), vrate("allocstall"),
            vrate("pgsteal_kswapd"), vrate("pgsteal_direct"),
        ]


def _is_partition(dev: str) -> bool:
    # nvme0n1p3, sda1, mmcblk0p1, dm-0 is whole, md0 whole
    if dev.startswith(("nvme", "mmcblk")):
        return "p" in dev.rsplit("n", 1)[-1]
    if dev.startswith(("sd", "vd", "hd", "xvd")):
        return dev[-1].isdigit()
    return False


class DiskStats(Sampler):
    name = "disk"
    _SECTOR = 512.0

    def __init__(self, devices: Optional[List[str]] = None):
        self._want = devices
        self.columns = []
        self.devices: List[str] = []

    def prepare(self) -> None:
        ds = util.parse_diskstats()
        if self._want:
            self.devices = [d for d in self._want if d in ds]
        else:
            self.devices = [d for d in ds if not _is_partition(d)
                            and not d.startswith(("loop", "ram", "zram"))]
            self.devices.sort()
        self.columns = []
        for d in self.devices:
            self.columns += [f"{d}_read_mbs", f"{d}_write_mbs",
                             f"{d}_read_iops", f"{d}_write_iops", f"{d}_util_pct"]
        self._prev = {k: dict(v) for k, v in ds.items() if k in self.devices}
        self._prev_t = util.epoch()

    def sample(self, t: float) -> Optional[list]:
        ds = util.parse_diskstats()
        dt = max(1e-6, t - self._prev_t)
        row = []
        for d in self.devices:
            cur = ds.get(d)
            prev = self._prev.get(d)
            if not cur or not prev:
                row += [None] * 5
                continue
            dr, dw = cur["reads"] - prev["reads"], cur["writes"] - prev["writes"]
            sr, sw = cur["sectors_read"] - prev["sectors_read"], cur["sectors_written"] - prev["sectors_written"]
            io_ms = cur["io_ms"] - prev["io_ms"]
            row += [
                sr * self._SECTOR / dt / 1e6,
                sw * self._SECTOR / dt / 1e6,
                dr / dt, dw / dt,
                min(100.0, io_ms / dt / 10.0),  # io_ms per second -> % busy
            ]
        self._prev = {k: dict(v) for k, v in ds.items() if k in self.devices}
        self._prev_t = t
        return row


class NetDev(Sampler):
    name = "net"

    def __init__(self, interfaces: Optional[List[str]] = None):
        self._want = interfaces
        self.interfaces: List[str] = []
        self.columns = []

    def prepare(self) -> None:
        nd = util.parse_netdev()
        if self._want:
            self.interfaces = [i for i in self._want if i in nd]
        else:
            # skip loopback and ephemeral container veths; keep real + tunnels
            self.interfaces = [i for i in nd if i != "lo" and not i.startswith("veth")]
            self.interfaces.sort()
        self.columns = []
        for i in self.interfaces:
            self.columns += [f"{i}_rx_mbps", f"{i}_tx_mbps", f"{i}_rx_pps", f"{i}_tx_pps",
                             f"{i}_rx_err_delta", f"{i}_rx_drop_delta"]
        self._prev = {k: dict(v) for k, v in nd.items() if k in self.interfaces}
        self._prev_t = util.epoch()

    def sample(self, t: float) -> Optional[list]:
        nd = util.parse_netdev()
        dt = max(1e-6, t - self._prev_t)
        row = []
        for i in self.interfaces:
            cur, prev = nd.get(i), self._prev.get(i)
            if not cur or not prev:
                row += [None] * 6
                continue
            row += [
                (cur["rx_bytes"] - prev["rx_bytes"]) * 8 / dt / 1e6,
                (cur["tx_bytes"] - prev["tx_bytes"]) * 8 / dt / 1e6,
                (cur["rx_packets"] - prev["rx_packets"]) / dt,
                (cur["tx_packets"] - prev["tx_packets"]) / dt,
                cur["rx_errs"] - prev["rx_errs"],
                cur["rx_drop"] - prev["rx_drop"],
            ]
        self._prev = {k: dict(v) for k, v in nd.items() if k in self.interfaces}
        self._prev_t = t
        return row
