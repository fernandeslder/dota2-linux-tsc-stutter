"""Profile and CLI-helper tests."""

from detector.collect import cli, profiles


def test_profiles_shape():
    for name in ("full", "lite"):
        p = profiles.get(name)
        assert p["profile"] == name
        assert "samplers" in p and "logs" in p
        for s in p["samplers"].values():
            if "interval" in s:
                assert s["interval"] > 0
    assert profiles.sampler_enabled(profiles.get("full"), "gpu")
    assert not profiles.sampler_enabled(profiles.get("lite"), "net_tcp")


def test_sampler_rate_ordering():
    full, lite = profiles.get("full"), profiles.get("lite")
    # lite must sample no faster than full for every shared sampler
    for name, cfg in full["samplers"].items():
        if "interval" not in cfg or name not in lite["samplers"]:
            continue
        if "interval" in lite["samplers"][name]:
            assert lite["samplers"][name]["interval"] >= cfg["interval"]


def test_full_meets_minimum_rate():
    # spec: >= 10 Hz for most signals; GPU up to 50 Hz
    full = profiles.get("full")
    assert full["samplers"]["gpu"]["interval"] <= 0.05
    assert full["samplers"]["cpu"]["interval"] <= 0.1
    assert full["samplers"]["sys"]["interval"] <= 0.1


def test_run_id_slug():
    rid = cli.new_run_id("warmup A/B test!")
    assert "/" not in rid and " " not in rid
    assert cli._slug("a b/c") == "a-b-c"
    assert cli._slug("") == "run"


def test_have_and_cmdline():
    from detector.collect import util
    assert util.have("python3")
    assert not util.have("definitely-not-a-real-binary-xyz")
