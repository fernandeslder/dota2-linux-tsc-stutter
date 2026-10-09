"""Unit tests for the MangoHud parser, epoch mapping and launch options."""

import os
import time

from detector.collect import mangohud
from detector.collect.rundir import CsvWriter

HEADER = ("fps,frametime,cpu_load,cpu_power,gpu_load,cpu_temp,gpu_temp,"
          "gpu_core_clock,gpu_mem_clock,gpu_vram_used,gpu_power,ram_used,"
          "swap_used,process_rss,cpu_mhz,elapsed")


def _write_csv(path, frames):
    with open(path, "w") as fh:
        fh.write("os,cpu,gpu,ram,kernel,driver,cpuscheduler\n")
        fh.write("CachyOS,AMD Ryzen,NVIDIA,100,6.18,,performance\n")
        fh.write(HEADER + "\n")
        for i, (ft, el) in enumerate(frames):
            fh.write(f"{1000.0/ft:.3f},{ft},{0},0,10,50,55,2000,9000,100,50,"
                     f"9,1,0,5000,{el}\n")


def test_find_header_and_read_frames(tmp_path):
    p = str(tmp_path / "vkcube_test.csv")
    _write_csv(p, [(6.9, 13_000_000), (7.1, 20_000_000)])
    idx, cols = mangohud.find_header_and_cols(p)
    assert idx == 2
    assert cols["frametime"] == 1
    assert cols["elapsed"] == 15
    frames = mangohud.read_frames(p)
    assert frames == [(13_000_000, 6.9), (20_000_000, 7.1)]


def test_iter_frames_does_not_consume_partial_line(tmp_path):
    p = str(tmp_path / "partial.csv")
    _write_csv(p, [(6.9, 1_000_000)])
    with open(p, "a") as fh:
        fh.write("100.0,7.0,0,0,10,50,55,2000,9000,100,50,9,1,0,5000,2")  # no newline
    idx, cols = mangohud.find_header_and_cols(p)
    got = []
    off = 0
    for pos, fr in mangohud.iter_frames_from(p, 0, idx, cols):
        got.append(fr)
        off = pos
    assert got == [(1_000_000, 6.9)]  # partial line withheld
    with open(p, "a") as fh:
        fh.write("000000\n")
    got2 = [fr for _, fr in mangohud.iter_frames_from(p, off, idx, cols)]
    assert got2 == [(2_000_000, 7.0)]


def test_config_and_launch_options(tmp_path):
    cfg = mangohud.default_config(str(tmp_path / "mh"))
    assert cfg["fps_only"] == "0"
    assert cfg["autostart_log"] == "1"
    assert cfg["log_duration"] == "0"
    assert "output_folder=" in mangohud.config_env(cfg)
    conf = str(tmp_path / "mangohud.conf")
    mangohud.write_config_file(conf, cfg)
    assert os.path.exists(conf)
    opts = mangohud.launch_options(conf)
    assert "MANGOHUD=1" in opts["native_vulkan_layer"]
    assert "VK_LAYER" not in opts["native_vulkan_layer"]  # implicit layer, no explicit var
    assert conf in opts["native_vulkan_layer"]
    assert "mangohud %command%" in opts["wrapper"]
    assert "-vulkan" in opts["native_vulkan_layer"]


def test_mapping_residuals():
    frames = [(1_000_000_000, 7.0), (2_000_000_000, 7.0)]
    t0 = 1000.0
    # mapped epochs: 1001.0, 1002.0
    res = mangohud.mapping_residuals(frames, t0, [1001.02, 1001.98])
    assert abs(res[0] - (-20.0)) < 1e-6
    assert abs(res[1] - 20.0) < 1e-6


def test_plausible_frametime_rejects_the_real_corrupt_value():
    assert mangohud.plausible_frametime(6.9)
    assert not mangohud.plausible_frametime(9.96739e7)   # real MangoHud glitch
    assert not mangohud.plausible_frametime(0.0)
    assert not mangohud.plausible_frametime(-1.0)
    assert not mangohud.plausible_frametime(float("nan"))


def test_watcher_drops_implausible_frames(tmp_path):
    p = str(tmp_path / "vkcube_corrupt.csv")
    _write_csv(p, [(6.9, 1_000_000), (9.96739e7, 2_000_000), (7.0, 3_000_000)])
    out = str(tmp_path / "frametimes.csv")
    w = CsvWriter(out, ["frametime_ms"])
    w.open()
    watcher = mangohud.MangoHudWatcher(str(tmp_path), w, poll=0.02, timeout=5.0)
    watcher.start()
    deadline = time.time() + 3
    while watcher.n_frames < 2 and time.time() < deadline:
        time.sleep(0.02)
    watcher.stop()
    w.close()
    assert watcher.n_frames == 2
    assert watcher.n_rejected == 1
    with open(out) as fh:
        vals = [float(l.split(",")[1]) for l in fh.read().strip().splitlines()[1:]]
    assert max(vals) < 10000.0


def test_watcher_writes_epoch_frametimes(tmp_path):
    p = str(tmp_path / "vkcube_live.csv")
    _write_csv(p, [(6.9, 5_000_000), (7.0, 12_000_000), (8.0, 19_000_000)])
    out = str(tmp_path / "frametimes.csv")
    w = CsvWriter(out, ["frametime_ms"])
    w.open()
    watcher = mangohud.MangoHudWatcher(str(tmp_path), w, poll=0.02, timeout=5.0)
    watcher.start()
    deadline = time.time() + 3
    while watcher.n_frames < 3 and time.time() < deadline:
        time.sleep(0.02)
    watcher.stop()
    w.close()
    assert watcher.n_frames == 3
    assert watcher.t0_epoch is not None
    with open(out) as fh:
        lines = fh.read().strip().splitlines()
    assert lines[0] == "t_epoch,frametime_ms"
    assert len(lines) == 4
    # first frame epoch == t0 + 0.0050 s
    t_first = float(lines[1].split(",")[0])
    assert abs(t_first - (watcher.t0_epoch + 0.005)) < 1e-3
