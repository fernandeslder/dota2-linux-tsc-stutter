"""GPU sampler via NVML (python-nvidia-ml-py / pynvml).

In-process NVML calls (no `nvidia-smi` subprocess) -- the spec calls out
nvidia-smi spawns as a known hitch source, so we deliberately avoid them.
Every field is fetched defensively: a single unsupported query must not kill
the whole row.
"""

from __future__ import annotations

from typing import List, Optional

from . import Sampler

try:  # pragma: no cover - import guarded for test environments
    import pynvml  # type: ignore
except Exception:  # pragma: no cover
    pynvml = None


def available() -> bool:
    if pynvml is None:
        return False
    try:
        pynvml.nvmlInit()
        pynvml.nvmlShutdown()
        return True
    except Exception:
        return False


def gpu_info() -> dict:
    """Static device description for meta.json."""
    info = {}
    if pynvml is None:
        return info
    try:
        pynvml.nvmlInit()
        h = pynvml.nvmlDeviceGetHandleByIndex(0)
        info["name"] = _decode(pynvml.nvmlDeviceGetName(h))
        info["driver_version"] = _decode(pynvml.nvmlSystemGetDriverVersion())
        info["nvml_version"] = _decode(pynvml.nvmlSystemGetNVMLVersion())
        info["count"] = pynvml.nvmlDeviceGetCount()
        mem = pynvml.nvmlDeviceGetMemoryInfo(h)
        info["vram_total_mib"] = round(mem.total / 1048576.0, 1)
        pynvml.nvmlShutdown()
    except Exception:
        pass
    return info


def running_processes() -> List[dict]:
    """[{pid, name, used_mib, kind}] for processes on GPU 0 (graphics + compute)."""
    out = []
    if pynvml is None:
        return out
    try:
        pynvml.nvmlInit()
        h = pynvml.nvmlDeviceGetHandleByIndex(0)
        for kind, fn in (("graphics", pynvml.nvmlDeviceGetGraphicsRunningProcesses),
                         ("compute", pynvml.nvmlDeviceGetComputeRunningProcesses)):
            try:
                for p in fn(h):
                    used = getattr(p, "usedGpuMemory", None)
                    out.append({
                        "pid": p.pid,
                        "name": _decode(getattr(p, "name", "") or _proc_name(p.pid)),
                        "used_mib": round(used / 1048576.0, 1) if used else None,
                        "kind": kind,
                    })
            except Exception:
                continue
        pynvml.nvmlShutdown()
    except Exception:
        pass
    return out


def _decode(x) -> str:
    if isinstance(x, bytes):
        return x.decode("utf-8", "replace")
    return "" if x is None else str(x)


def _proc_name(pid: int) -> str:
    try:
        with open(f"/proc/{pid}/comm") as fh:
            return fh.read().strip()
    except OSError:
        return ""


class GpuSampler(Sampler):
    name = "gpu"
    columns = [
        "gpu_util", "mem_util",
        "sm_clock_mhz", "mem_clock_mhz", "graphics_clock_mhz", "video_clock_mhz",
        "power_w", "power_limit_w", "temp_c", "fan_pct",
        "vram_used_mib", "vram_total_mib", "vram_util_pct",
        "pstate", "throttle_reasons",
        "pcie_gen", "pcie_width",
        "enc_util", "dec_util",
    ]

    def __init__(self, index: int = 0):
        self.index = index
        self._h = None
        self._nvml = None

    def prepare(self) -> None:
        if pynvml is None:
            raise RuntimeError("pynvml not available")
        pynvml.nvmlInit()
        self._h = pynvml.nvmlDeviceGetHandleByIndex(self.index)
        self._nvml = pynvml

    def teardown(self) -> None:
        try:
            if pynvml is not None:
                pynvml.nvmlShutdown()
        except Exception:
            pass

    def _safe(self, fn, *a, **kw):
        try:
            return fn(*a, **kw)
        except Exception:
            return None

    def sample(self, t: float) -> Optional[list]:
        n = self._nvml
        h = self._h
        util = self._safe(n.nvmlDeviceGetUtilizationRates, h)
        mem = self._safe(n.nvmlDeviceGetMemoryInfo, h)
        enc = self._safe(n.nvmlDeviceGetEncoderUtilization, h)
        dec = self._safe(n.nvmlDeviceGetDecoderUtilization, h)
        vram_used = vram_total = vram_pct = None
        if mem is not None:
            vram_used = mem.used / 1048576.0
            vram_total = mem.total / 1048576.0
            if mem.total:
                vram_pct = mem.used / mem.total * 100.0
        return [
            getattr(util, "gpu", None),
            getattr(util, "memory", None),
            self._safe(n.nvmlDeviceGetClockInfo, h, n.NVML_CLOCK_SM),
            self._safe(n.nvmlDeviceGetClockInfo, h, n.NVML_CLOCK_MEM),
            self._safe(n.nvmlDeviceGetClockInfo, h, n.NVML_CLOCK_GRAPHICS),
            self._safe(n.nvmlDeviceGetClockInfo, h, n.NVML_CLOCK_VIDEO),
            _div(self._safe(n.nvmlDeviceGetPowerUsage, h), 1000.0),
            _div(self._safe(n.nvmlDeviceGetEnforcedPowerLimit, h), 1000.0),
            self._safe(n.nvmlDeviceGetTemperature, h, n.NVML_TEMPERATURE_GPU),
            self._safe(n.nvmlDeviceGetFanSpeed, h),
            vram_used, vram_total, vram_pct,
            self._safe(n.nvmlDeviceGetPerformanceState, h),
            self._safe(n.nvmlDeviceGetCurrentClocksThrottleReasons, h),
            self._safe(n.nvmlDeviceGetCurrPcieLinkGeneration, h),
            self._safe(n.nvmlDeviceGetCurrPcieLinkWidth, h),
            enc[0] if isinstance(enc, tuple) else None,
            dec[0] if isinstance(dec, tuple) else None,
        ]


def _div(v, d):
    return None if v is None else v / d
