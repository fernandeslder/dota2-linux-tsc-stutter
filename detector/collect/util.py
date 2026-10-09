"""Low-level helpers shared by every collector.

Everything here is stdlib-only and safe to import without a running collector.
The single clock for the whole detector is CLOCK_REALTIME expressed as epoch
seconds (float).  `epoch()` / `epoch_ns()` are the only time sources used.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import os
import shutil
import subprocess
import time
from typing import Iterable, Optional

# --------------------------------------------------------------------------
# Clock
# --------------------------------------------------------------------------


def epoch() -> float:
    """CLOCK_REALTIME epoch seconds as a float (microsecond+ resolution)."""
    return time.clock_gettime(time.CLOCK_REALTIME)


def epoch_ns() -> int:
    return time.clock_gettime_ns(time.CLOCK_REALTIME)


# --------------------------------------------------------------------------
# statx: nanosecond file birth time (MangoHud epoch anchor)
# --------------------------------------------------------------------------

_AT_FDCWD = -100
_AT_SYMLINK_NOFOLLOW = 0x100
_STATX_BTIME = 0x800
_STATX_BASIC_STATS = 0x7FF
_STATX_ALL = 0xFFF


class _statx_ts(ctypes.Structure):
    _fields_ = [
        ("tv_sec", ctypes.c_int64),
        ("tv_nsec", ctypes.c_uint32),
        ("__reserved", ctypes.c_int32),
    ]


class _statx(ctypes.Structure):
    _fields_ = [
        ("stx_mask", ctypes.c_uint32),
        ("stx_blksize", ctypes.c_uint32),
        ("stx_attributes", ctypes.c_uint64),
        ("stx_nlink", ctypes.c_uint32),
        ("stx_uid", ctypes.c_uint32),
        ("stx_gid", ctypes.c_uint32),
        ("stx_mode", ctypes.c_uint16),
        ("__spare0", ctypes.c_uint16 * 1),
        ("stx_ino", ctypes.c_uint64),
        ("stx_size", ctypes.c_uint64),
        ("stx_blocks", ctypes.c_uint64),
        ("stx_attributes_mask", ctypes.c_uint64),
        ("stx_atime", _statx_ts),
        ("stx_btime", _statx_ts),
        ("stx_ctime", _statx_ts),
        ("stx_mtime", _statx_ts),
        ("stx_rdev_major", ctypes.c_uint32),
        ("stx_rdev_minor", ctypes.c_uint32),
        ("stx_dev_major", ctypes.c_uint32),
        ("stx_dev_minor", ctypes.c_uint32),
        ("__spare2", ctypes.c_uint64 * 14),
    ]


def _libc():
    name = ctypes.util.find_library("c") or "libc.so.6"
    return ctypes.CDLL(name, use_errno=True)


def birthtime_ns(path: str) -> Optional[int]:
    """Return stx_btime of *path* in nanoseconds since the epoch.

    Returns None when the filesystem does not expose a birth time (e.g. tmpfs).
    The result is queried per path; a filesystem lacking btime does not disable
    the query for other paths.
    """
    try:
        libc = _libc()
        fn = libc.statx
    except Exception:  # pragma: no cover - very old libc
        return None
    fn.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_uint,
        ctypes.POINTER(_statx),
    ]
    fn.restype = ctypes.c_int
    buf = _statx()
    rc = fn(_AT_FDCWD, os.fsencode(path), _AT_SYMLINK_NOFOLLOW,
            _STATX_BTIME | _STATX_BASIC_STATS, ctypes.byref(buf))
    if rc != 0:
        return None
    if not (buf.stx_mask & _STATX_BTIME):
        return None
    return buf.stx_btime.tv_sec * 1_000_000_000 + buf.stx_btime.tv_nsec


def file_times_ns(path: str) -> dict:
    """{'btime': int|None, 'mtime': int, 'ctime': int, 'size': int}"""
    st = os.stat(path)
    return {
        "btime": birthtime_ns(path),
        "mtime": st.st_mtime_ns,
        "ctime": st.st_ctime_ns,
        "size": st.st_size,
    }


# --------------------------------------------------------------------------
# Scheduling / priority
# --------------------------------------------------------------------------


def set_low_priority(nice: int = 19) -> None:
    """Best-effort renice of the current process."""
    try:
        os.setpriority(os.PRIO_PROCESS, 0, int(nice))
    except (OSError, AttributeError):
        pass


_IOPRIO_WHO_PROCESS = 1
_IOPRIO_CLASS_IDLE = 3
_IOPRIO_CLASS_BE = 2
_SYS_ioprio_set = 251  # x86_64 / aarch64


def set_io_priority(cls: str = "idle", level: int = 7) -> bool:
    """Best-effort ioprio_set on the current process. Returns True on success."""
    if cls == "idle":
        class_id = _IOPRIO_CLASS_IDLE
        data = 0
    else:
        class_id = _IOPRIO_CLASS_BE
        data = max(0, min(7, level))
    ioprio = (class_id << 13) | data
    try:
        libc = _libc()
        libc.syscall.argtypes = [ctypes.c_long, ctypes.c_int, ctypes.c_int, ctypes.c_int]
        libc.syscall.restype = ctypes.c_long
        rc = libc.syscall(_SYS_ioprio_set, _IOPRIO_WHO_PROCESS, 0, ioprio)
        return rc == 0
    except Exception:
        return False


def set_affinity(cpus: Iterable[int]) -> bool:
    cpus = sorted(set(int(c) for c in cpus))
    if not cpus:
        return False
    try:
        os.sched_setaffinity(0, cpus)
        return True
    except OSError:
        return False


def all_cpus() -> list:
    try:
        return sorted(os.sched_getaffinity(0))
    except (OSError, AttributeError):
        return list(range(os.cpu_count() or 1))


def process_cpus(pid: int) -> set:
    """CPUs a pid's threads are allowed to run on (union of Cpus_allowed_list)."""
    cpus = set()
    taskdir = f"/proc/{pid}/task"
    try:
        tids = os.listdir(taskdir)
    except OSError:
        return cpus
    for tid in tids:
        try:
            with open(f"{taskdir}/{tid}/status", "r") as fh:
                for line in fh:
                    if line.startswith("Cpus_allowed_list:"):
                        cpus |= parse_cpu_list(line.split(":", 1)[1].strip())
                        break
        except OSError:
            continue
    return cpus


def parse_cpu_list(spec: str) -> set:
    """Parse a Linux cpu-list like '0-7,16-23' into a set of ints."""
    out = set()
    spec = spec.strip()
    if not spec:
        return out
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(part))
    return out


def ccd_of_cpu(cpu: int, ccd_map: Optional[dict] = None) -> int:
    """Map a CPU to its L3/CCD index. Uses the cached L3 shared_cpu_list map."""
    if ccd_map is None:
        ccd_map = ccd_map_for_cpus()
    return ccd_map.get(int(cpu), -1)


_CCD_MAP = None


def ccd_map_for_cpus() -> dict:
    """cpu -> ccd index, derived from L3 (index3) shared_cpu_list.

    On the 7945HX this yields {0..15: 0, 16..31: 1} (verified on this machine),
    which differs from the older docs' 'taskset -c 0-7,16-23' assumption.
    """
    global _CCD_MAP
    if _CCD_MAP is not None:
        return _CCD_MAP
    mapping = {}
    sysdir = "/sys/devices/system/cpu"
    try:
        cpus = sorted(int(c[3:]) for c in os.listdir(sysdir) if c.startswith("cpu") and c[3:].isdigit())
    except OSError:
        cpus = []
    ccd = 0
    seen = set()
    for cpu in cpus:
        if cpu in seen:
            continue
        try:
            with open(f"{sysdir}/cpu{cpu}/cache/index3/shared_cpu_list") as fh:
                group = parse_cpu_list(fh.read())
        except OSError:
            group = {cpu}
        for c in group:
            mapping[c] = ccd
        seen |= group
        ccd += 1
    if not mapping:
        mapping = {c: 0 for c in cpus}
    _CCD_MAP = mapping
    return mapping


# --------------------------------------------------------------------------
# /proc parsing helpers
# --------------------------------------------------------------------------


def read_text(path: str, default: str = "") -> str:
    try:
        with open(path, "r") as fh:
            return fh.read()
    except OSError:
        return default


def parse_proc_stat(text: Optional[str] = None):
    """Return (per_cpu, aggregate, extras).

    per_cpu: list of (cpu_index, [user,nice,system,idle,iowait,irq,softirq,steal,...])
    aggregate: same list for the 'cpu ' line
    extras: dict with ctxt, btime, processes, procs_running, procs_blocked, intr
    """
    if text is None:
        text = read_text("/proc/stat")
    per_cpu = []
    aggregate = None
    extras = {}
    for line in text.splitlines():
        if line.startswith("cpu"):
            parts = line.split()
            key = parts[0]
            vals = [int(x) for x in parts[1:]]
            if key == "cpu":
                aggregate = vals
            else:
                per_cpu.append((int(key[3:]), vals))
        elif line.startswith("ctxt"):
            extras["ctxt"] = int(line.split()[1])
        elif line.startswith("btime"):
            extras["btime"] = int(line.split()[1])
        elif line.startswith("processes"):
            extras["processes"] = int(line.split()[1])
        elif line.startswith("procs_running"):
            extras["procs_running"] = int(line.split()[1])
        elif line.startswith("procs_blocked"):
            extras["procs_blocked"] = int(line.split()[1])
        elif line.startswith("intr"):
            extras["intr"] = int(line.split()[1])
    per_cpu.sort(key=lambda kv: kv[0])
    return per_cpu, aggregate, extras


def parse_pressure(text: str) -> dict:
    """Parse one /proc/pressure/* file into {some_avg10, some_total, full_avg10, full_total}."""
    out = {}
    for line in text.splitlines():
        parts = line.split()
        if not parts:
            continue
        kind = parts[0]
        vals = {}
        for tok in parts[1:]:
            if "=" in tok:
                k, v = tok.split("=", 1)
                try:
                    vals[k] = float(v)
                except ValueError:
                    pass
        for k in ("avg10", "avg60", "avg300", "total"):
            if k in vals:
                out[f"{kind}_{k}"] = vals[k]
    return out


def read_pressure(name: str) -> dict:
    return parse_pressure(read_text(f"/proc/pressure/{name}"))


def parse_meminfo(text: Optional[str] = None) -> dict:
    if text is None:
        text = read_text("/proc/meminfo")
    out = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        v = v.strip().split()
        if not v:
            continue
        try:
            val = float(v[0])
        except ValueError:
            continue
        if len(v) > 1 and v[1].lower() == "kb":
            val *= 1024.0
        out[k] = val
    return out


def parse_vmstat(text: Optional[str] = None) -> dict:
    if text is None:
        text = read_text("/proc/vmstat")
    out = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2:
            try:
                out[parts[0]] = float(parts[1])
            except ValueError:
                pass
    return out


def parse_diskstats(text: Optional[str] = None) -> dict:
    """Return {dev: {...}} from /proc/diskstats (fields 1..11+)."""
    if text is None:
        text = read_text("/proc/diskstats")
    out = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 14:
            continue
        dev = parts[2]
        try:
            vals = [int(x) for x in parts[3:14]]
        except ValueError:
            continue
        out[dev] = {
            "reads": vals[0],
            "reads_merged": vals[1],
            "sectors_read": vals[2],
            "read_ms": vals[3],
            "writes": vals[4],
            "writes_merged": vals[5],
            "sectors_written": vals[6],
            "write_ms": vals[7],
            "in_flight": vals[8],
            "io_ms": vals[9],
            "weighted_io_ms": vals[10],
        }
    return out


def parse_netdev(text: Optional[str] = None) -> dict:
    """{iface: {...rx_bytes...}} from /proc/net/dev."""
    if text is None:
        text = read_text("/proc/net/dev")
    out = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        name, rest = line.split(":", 1)
        name = name.strip()
        if not name:
            continue
        f = rest.split()
        if len(f) < 16:
            continue
        try:
            v = [int(x) for x in f[:16]]
        except ValueError:
            continue
        out[name] = {
            "rx_bytes": v[0], "rx_packets": v[1], "rx_errs": v[2], "rx_drop": v[3],
            "rx_fifo": v[4], "rx_frame": v[5], "rx_compressed": v[6], "rx_multicast": v[7],
            "tx_bytes": v[8], "tx_packets": v[9], "tx_errs": v[10], "tx_drop": v[11],
            "tx_fifo": v[12], "tx_colls": v[13], "tx_carrier": v[14], "tx_compressed": v[15],
        }
    return out


def read_float(path: str) -> Optional[float]:
    try:
        with open(path, "r") as fh:
            return float(fh.read().strip())
    except (OSError, ValueError):
        return None


# --------------------------------------------------------------------------
# subprocess helpers
# --------------------------------------------------------------------------


def run_capture(cmd: list, timeout: float = 5.0) -> tuple:
    """Run a command, returning (rc, stdout, stderr). Never raises."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except FileNotFoundError:
        return 127, "", f"not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except Exception as exc:  # pragma: no cover - defensive
        return 1, "", str(exc)


def have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def preexec_pdeathsig(sig: int = 15):
    """Return a preexec_fn that makes a child die if the parent does.

    Used for the journalctl tailers so a SIGKILL of the supervisor cannot leave
    orphaned children behind.
    """
    def _set():
        try:
            libc = _libc()
            libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong,
                                   ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
            libc.prctl(1, sig, 0, 0, 0)  # PR_SET_PDEATHSIG
        except Exception:
            pass
    return _set


# --------------------------------------------------------------------------
# /proc/<pid>/stat parsing (comm may contain spaces/parens)
# --------------------------------------------------------------------------


def parse_pid_stat(text: str) -> Optional[dict]:
    """Parse one /proc/<pid>/stat line. Returns dict with the fields we need."""
    rp = text.rfind(")")
    lp = text.find("(")
    if lp < 0 or rp < 0 or rp < lp:
        return None
    comm = text[lp + 1:rp]
    rest = text[rp + 2:].split()
    # rest[0] is state (field 3); utime is field 14 -> rest[11]
    try:
        d = {
            "comm": comm,
            "state": rest[0],
            "utime": int(rest[11]),
            "stime": int(rest[12]),
            "num_threads": int(rest[17]),
            "processor": int(rest[36]) if len(rest) > 36 else -1,
            "rss_pages": int(rest[21]) if len(rest) > 21 else -1,
        }
    except (IndexError, ValueError):
        return None
    return d


def proc_cmdline(pid: int) -> str:
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as fh:
            return fh.read().replace(b"\x00", b" ").decode("utf-8", "replace").strip()
    except OSError:
        return ""
