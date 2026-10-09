"""Unit tests for the launch-option builder (detector/trial/launchopts.py)."""

import os

from detector.trial import launchopts


def test_build_without_mangohud_is_plain(tmp_path):
    b = launchopts.build("-threads 8", mangohud_on=False,
                         output_folder=str(tmp_path), native=True, proton=True)
    assert b["native"] == "%command% -threads 8 -vulkan"
    assert b["proton"] == "%command% -threads 8"
    assert b["mangohud_env"] == ""


def test_build_native_forces_vulkan_once(tmp_path):
    b1 = launchopts.build("-threads 8", mangohud_on=False, output_folder=str(tmp_path))
    assert b1["native"].endswith("-vulkan")
    b2 = launchopts.build("-vulkan -threads 8", mangohud_on=False, output_folder=str(tmp_path))
    assert b2["native"].count("-vulkan") == 1


def test_build_with_mangohud_writes_config_and_env(tmp_path):
    out = tmp_path / "mh"
    b = launchopts.build("-threads 8", mangohud_on=True, output_folder=str(out))
    assert 'LD_PRELOAD=""' in b["native"]
    assert "MANGOHUD=1" in b["native"]
    assert "MANGOHUD_CONFIGFILE=" in b["native"]
    assert "%command% -threads 8 -vulkan" in b["native"]
    assert "mangohud %command%" in b["wrapper"]
    # config file contents carry the frametime-logging keys
    assert os.path.exists(b["config_file"])
    body = open(b["config_file"]).read()
    assert "fps_only=0" in body
    assert "autostart_log=1" in body
    assert "log_duration=0" in body
    assert f"output_folder={out}" in body


def test_build_inline_config_mode(tmp_path):
    b = launchopts.build("-threads 8", mangohud_on=True, output_folder=str(tmp_path),
                         config_mode="inline")
    assert "MANGOHUD_CONFIG=" in b["native"]
    assert "fps_only=0" in b["native"]
    assert "config_file" not in b


def test_build_proton_only(tmp_path):
    b = launchopts.build("-threads 8", mangohud_on=False, output_folder=str(tmp_path),
                         native=False, proton=True)
    assert "native" not in b
    assert b["proton"] == "%command% -threads 8"
