"""hwmon / thermal / power samplers.

Dynamic columns: every `tempN_input` under /sys/class/hwmon is exposed as
`<hwmon_name>_tempN`, plus RAPL package/core power and battery power/charge.
This covers k10temp (CPU Tctl/Tccd), NVMe composites, the discrete GPU is
already handled by NVML, and RAPL on this AMD laptop is exposed under
/sys/class/powercap/intel-rapl.
"""

from __future__ import annotations

import glob
import os
from typing import List, Optional

from .. import util
from . import Sampler


class HwmonSampler(Sampler):
    name = "hwmon"

    def __init__(self):
        self.columns: List[str] = []
        self._temps = []          # (column, path)
        self._rapl = []           # (column, energy_path, max_range)
        self._rapl_prev = {}
        self._battery = []        # (column, path, scale)
        self._prev_t = None

    def prepare(self) -> None:
        # temperatures
        for entry in sorted(os.listdir("/sys/class/hwmon")):
            base = f"/sys/class/hwmon/{entry}"
            hname = util.read_text(os.path.join(base, "name")).strip() or entry
            for p in sorted(glob.glob(os.path.join(base, "temp*_input"))):
                n = os.path.basename(p).split("_")[0]  # temp1
                col = f"{hname}_{n}_c"
                self._temps.append((col, p))
                self.columns.append(col)
        # RAPL power
        for p in sorted(glob.glob("/sys/class/powercap/intel-rapl:*")):
            name = util.read_text(os.path.join(p, "name")).strip() or os.path.basename(p)
            energy = os.path.join(p, "energy_uj")
            if not os.path.exists(energy):
                continue
            maxr = util.read_float(os.path.join(p, "max_energy_range_uj")) or 0.0
            col = f"rapl_{_slug(name)}_w"
            self._rapl.append((col, energy, maxr))
            self.columns.append(col)
        # battery / AC
        for ps in sorted(glob.glob("/sys/class/power_supply/*")):
            name = util.read_text(os.path.join(ps, "type")).strip()
            if name == "Battery":
                label = _slug(os.path.basename(ps))
                pw = os.path.join(ps, "power_now")
                cap = os.path.join(ps, "capacity")
                if os.path.exists(pw):
                    self._battery.append((f"{label}_power_w", pw, 1e-6))
                    self.columns.append(f"{label}_power_w")
                if os.path.exists(cap):
                    self._battery.append((f"{label}_pct", cap, 1.0))
                    self.columns.append(f"{label}_pct")
        # prime RAPL
        for col, path, maxr in self._rapl:
            self._rapl_prev[col] = util.read_float(path)
        self._prev_t = util.epoch()

    def sample(self, t: float) -> Optional[list]:
        dt = max(1e-6, t - (self._prev_t or t))
        row = []
        for _col, path in self._temps:
            v = util.read_float(path)
            row.append(v / 1000.0 if v is not None else None)
        for col, path, maxr in self._rapl:
            cur = util.read_float(path)
            prev = self._rapl_prev.get(col)
            self._rapl_prev[col] = cur
            if cur is None or prev is None:
                row.append(None)
                continue
            delta = cur - prev
            if delta < 0 and maxr:
                delta += maxr
            row.append(delta / 1e6 / dt)  # uj -> W
        for _col, path, scale in self._battery:
            v = util.read_float(path)
            row.append(v * scale if v is not None else None)
        self._prev_t = t
        return row


def _slug(s: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in s).strip("_").lower()
