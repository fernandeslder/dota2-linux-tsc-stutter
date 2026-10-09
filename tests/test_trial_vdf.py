"""Unit tests for the VDF reader / surgical editor (detector/trial/vdf.py)."""

import pytest

from detector.trial import vdf
from detector.trial.vdf import VdfBinaryError, VdfDocument, VdfError

SAMPLE = '''\
"UserLocalConfigStore"
{
\t"Software"
\t{
\t\t"Valve"
\t\t{
\t\t\t"Steam"
\t\t\t{
\t\t\t\t"apps"
\t\t\t\t{
\t\t\t\t\t"570"
\t\t\t\t\t{
\t\t\t\t\t\t"LastPlayed"\t\t"1790896190"
\t\t\t\t\t\t"LaunchOptions"\t\t"LD_PRELOAD=\\"\\" -vulkan +fps_max 144"
\t\t\t\t\t\t"cloud"
\t\t\t\t\t\t{
\t\t\t\t\t\t\t"last_sync_state"\t\t"synchronized"
\t\t\t\t\t\t}
\t\t\t\t\t}
\t\t\t\t}
\t\t\t}
\t\t}
\t}
}
'''


def test_parse_and_get_suffix():
    d = VdfDocument.loads(SAMPLE)
    assert d.get_suffix(["Software", "Valve", "Steam", "apps", "570", "LaunchOptions"]) \
        == 'LD_PRELOAD="" -vulkan +fps_max 144'
    node = d.node(["UserLocalConfigStore", "Software", "Valve", "Steam", "apps", "570"])
    assert "cloud" in node
    assert node.get_node("cloud").get("last_sync_state") == "synchronized"


def test_root_wrapper_is_optional_for_suffix_lookup():
    d = VdfDocument.loads(SAMPLE)
    # suffix lookup works whether or not you prefix the wrapper key
    p = d.find_path_by_suffix(["Software", "Valve", "Steam", "apps", "570"])
    assert p == ("UserLocalConfigStore", "Software", "Valve", "Steam", "apps", "570")


def test_set_existing_replaces_one_line_only():
    d = VdfDocument.loads(SAMPLE)
    before = d.dumps().decode().splitlines()
    d.set_suffix(["Software", "Valve", "Steam", "apps", "570", "LaunchOptions"],
                 'NEW %command% "quoted"')
    after = d.dumps().decode().splitlines()
    assert d.get_suffix(["Software", "Valve", "Steam", "apps", "570", "LaunchOptions"]) \
        == 'NEW %command% "quoted"'
    assert len(before) == len(after)
    changed = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
    assert len(changed) == 1
    assert "LaunchOptions" in after[changed[0]]
    assert '\\"quoted\\"' in after[changed[0]]  # quotes re-escaped on write


def test_set_inserts_absent_key_with_indentation():
    d = VdfDocument.loads(SAMPLE)
    d.delete_suffix(["Software", "Valve", "Steam", "apps", "570", "LaunchOptions"])
    assert d.get_suffix(["Software", "Valve", "Steam", "apps", "570", "LaunchOptions"]) is None
    d.set_suffix(["Software", "Valve", "Steam", "apps", "570", "LaunchOptions"], "INS %command%")
    assert d.get_suffix(["Software", "Valve", "Steam", "apps", "570", "LaunchOptions"]) == "INS %command%"
    line = [l for l in d.dumps().decode().splitlines() if "LaunchOptions" in l][0]
    assert line.startswith('\t\t\t\t\t\t"LaunchOptions"')  # same depth as siblings


def test_delete_removes_whole_line():
    d = VdfDocument.loads(SAMPLE)
    assert d.delete_suffix(["Software", "Valve", "Steam", "apps", "570", "LaunchOptions"]) is True
    assert "LaunchOptions" not in d.dumps().decode()
    # idempotent
    assert d.delete_suffix(["Software", "Valve", "Steam", "apps", "570", "LaunchOptions"]) is False


def test_comments_and_escapes_are_handled():
    text = '// leading comment\n"root"\n{\n\t"a"\t\t"line\\nwith\\ttabs"\n\t"b" "quote\\"here"\n}\n'
    d = VdfDocument.loads(text)
    inner = d.root.get_node("root")
    assert inner.get("a") == "line\nwith\ttabs"
    assert inner.get("b") == 'quote"here'


def test_render_canonical_output_is_parseable():
    d = VdfDocument.loads(SAMPLE)
    again = VdfDocument.loads(d.render())
    assert again.get_suffix(["Software", "Valve", "Steam", "apps", "570", "LaunchOptions"]) \
        == 'LD_PRELOAD="" -vulkan +fps_max 144'


def test_binary_vdf_is_rejected_clearly():
    with pytest.raises(VdfBinaryError):
        VdfDocument.loads(b"\x00UserLocalConfigStore\x00")
    with pytest.raises(VdfBinaryError):
        VdfDocument.loads("\x00binary")


def test_malformed_input_raises():
    with pytest.raises(VdfError):
        VdfDocument.loads('"root"\n{\n\t"k"\n}\n')          # key with no value
    with pytest.raises(VdfError):
        VdfDocument.loads('"root"\n{\n\t"k"\t\t"v"\n')       # unterminated node
    with pytest.raises(VdfError):
        VdfDocument.loads('"root"\n{\n\t"k"\t\t"unterminated\n}\n')


def test_missing_path_returns_none():
    d = VdfDocument.loads(SAMPLE)
    assert d.get_suffix(["Software", "Valve", "Steam", "apps", "999", "LaunchOptions"]) is None
    assert d.find_path_by_suffix(["nope", "nope"]) is None


def test_quote_roundtrip():
    d = VdfDocument.loads('"r"\n{\n\t"k"\t\t""\n}\n')
    for val in ['a b', 'q"q', "back\\slash", "tab\there", "nl\nhere"]:
        d.set_suffix(["r", "k"], val)
        assert d.get_suffix(["r", "k"]) == val
