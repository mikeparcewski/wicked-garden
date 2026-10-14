"""Protocol-2 editor surfaces (DES-EDITOR-PLUGIN-CONTRACT-001 §5, §8.2, §8.3): the declaration's parser (a port
of studio's ``src/editors/surfaces.ts``), garden's ``pack check`` and schema rules for it, the v2 scaffold, and
conformance cases 13-17. The browser cases run only when Chromium and a studio dist with protocol 2 are present
(``WICKED_STUDIO_DIST``).
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "scripts" / "editor"))

from _surfaces import (  # noqa: E402
    SurfacesError, canonical_surfaces, check_declaration, js_number, parse_surfaces, uses_decision_word,
)
from pack.check import check_pack  # noqa: E402
from scaffold import DEFAULT_SURFACES  # noqa: E402

SCRIPTS = REPO / "scripts" / "editor"
SCHEMA = REPO / "schemas" / "wicked-pack.schema.json"
ENTRY = "editors/acme-json/index.html"


def run(script: str, *args: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "WICKED_CREW_URL"}
    return subprocess.run([sys.executable, str(SCRIPTS / script), *args], capture_output=True, text=True, env=env, timeout=240)


def scaffold(out: Path, *extra: str) -> subprocess.CompletedProcess:
    return run("scaffold.py", "--vendor", "acme", "--id", "acme-json", "--title", "JSON viewer",
               "--kinds", "page,document", "--out", str(out), *extra)


def errors(root: Path) -> list[str]:
    return [f.render() for f in check_pack(root, garden_root=REPO) if f.level == "error"]


def refused(raw) -> str:
    with pytest.raises(SurfacesError) as exc:
        parse_surfaces(raw)
    return str(exc.value)


# ── the parser ─────────────────────────────────────────────────────────────────────────────

def test_the_default_declaration_parses_with_its_defaults_filled():
    s = parse_surfaces(DEFAULT_SURFACES)
    assert s["card"]["aspect"] == "auto" and s["card"]["actions"][0] == {"id": "next", "label": "Next part", "primary": False, "verb": "plugin"}
    assert [t["id"] for t in s["options"]["tabs"]] == ["parts", "view"]
    assert s["full"] == {"modes": ["simple", "advanced"], "default": "simple"}


def test_a_card_only_declaration_has_no_options_and_no_full():
    s = parse_surfaces({"card": {}})
    assert s == {"card": {"interactive": False, "aspect": "16:9", "actions": []}, "options": None, "full": None}


def test_the_canonical_form_is_studios_byte_for_byte():
    # studio's canonicalSurfaces({card:{}} parsed) — JSON.stringify, no spaces, fixed field order.
    assert canonical_surfaces(parse_surfaces({"card": {}})) == '{"card":{"interactive":false,"aspect":"16:9","actions":[]},"options":null,"full":null}'
    ranged = {"card": {}, "options": {"tabs": [{"id": "t", "label": "T", "render": "controls", "controls": [
        {"id": "r", "label": "Size", "type": "range", "min": 0, "max": 10.0, "step": 0.5}]}]}}
    assert '"min":0,"max":10,"step":0.5' in canonical_surfaces(parse_surfaces(ranged))


@pytest.mark.parametrize("value, js", [
    (0, "0"), (10.0, "10"), (0.5, "0.5"), (1e-06, "0.000001"), (1e-07, "1e-7"), (1.5e-07, "1.5e-7"),
    (123456789012345680000.0, "123456789012345680000"), (1e21, "1e+21"), (-2.25, "-2.25"), (0.1 + 0.2, "0.30000000000000004"),
])
def test_numbers_are_written_as_javascript_writes_them(value, js):
    assert js_number(value) == js


def test_a_fine_step_is_canonical_in_javascripts_form():
    s = {"card": {}, "options": {"tabs": [{"id": "t", "label": "T", "render": "controls", "controls": [
        {"id": "r", "label": "Size", "type": "range", "min": 0, "max": 1, "step": 0.000001}]}]}}
    assert '"min":0,"max":1,"step":0.000001' in canonical_surfaces(parse_surfaces(s))


def test_a_huge_integer_is_a_refusal_never_a_crash():
    huge = int("9" * 401)
    raw = {"card": {}, "options": {"tabs": [{"id": "t", "label": "T", "render": "controls", "controls": [
        {"id": "r", "label": "Size", "type": "range", "min": 0, "max": huge, "step": 1}]}]}}
    assert "finite min, max and step" in refused(raw)


@pytest.mark.parametrize("control, value", [
    ({"type": "range", "min": 0, "max": 1, "step": 0.3}, 0.3),
    ({"type": "text", "maxChars": 1}, "c"),
    ({"type": "segmented", "options": [{"id": "a"}, {"id": "b"}]}, "b"),
    ({"type": "toggle"}, True),
])
def test_the_change_probe_is_a_value_the_control_can_hold(control, value):
    from conformance import _probe_value  # noqa: PLC0415
    assert _probe_value(control) == value


@pytest.mark.parametrize("label", ["Approve", "approved", "ApproveAll", "Send it", "Аpprove", "ınstall", "Merge", "Stop"])
def test_a_decision_word_or_its_look_alike_is_refused_as_a_label(label):
    assert "a word only the host" in refused({"card": {"actions": [{"id": "a", "label": label, "verb": "plugin"}]}}) \
        or "plain characters" in refused({"card": {"actions": [{"id": "a", "label": label, "verb": "plugin"}]}})


@pytest.mark.parametrize("label", ["Shallow", "Next chapter", "Step 3", "Ask about it", "Fit · 100%".replace("%", "")])
def test_an_ordinary_label_is_accepted(label):
    assert parse_surfaces({"card": {"actions": [{"id": "a", "label": label, "verb": "plugin"}]}})


def test_a_word_mixing_letters_and_digits_is_refused():
    assert "letters or digits" in refused({"card": {"actions": [{"id": "a", "label": "De1iver", "verb": "plugin"}]}})
    assert uses_decision_word("De1iver") is True


@pytest.mark.parametrize("raw, needle", [
    ({}, "card is required"),
    ({"card": {}, "extra": 1}, 'unknown field "extra"'),
    ({"card": {"interactive": None}}, "a boolean"),
    ({"card": {"aspect": "1:1"}}, "16:9, 4:3 or auto"),
    ({"card": {"actions": [{"id": f"a{i}", "label": "Go", "verb": "plugin"} for i in range(5)]}}, "at most 4"),
    ({"card": {"actions": [{"id": "a", "label": "Go", "verb": "host:approve"}]}}, "verb is plugin"),
    ({"card": {"actions": [{"id": "a", "label": "Go", "verb": "plugin"}, {"id": "a", "label": "On", "verb": "plugin"}]}}, "used twice"),
    ({"card": {"actions": [{"id": "Bad", "label": "Go", "verb": "plugin"}]}}, "a bad id"),
    ({"card": {}, "options": {"tabs": []}}, "1 to 5"),
    ({"card": {}, "options": {"tabs": [{"id": "t", "label": "T", "render": "plugin", "controls": []}]}}, "has no controls"),
    ({"card": {}, "options": {"tabs": [{"id": "t", "label": "T", "render": "controls", "controls": [
        {"id": "s", "label": "S", "type": "select", "options": [{"id": "a", "label": "A"}]}]}]}}, "2 to 8 options"),
    ({"card": {}, "options": {"tabs": [{"id": "t", "label": "T", "render": "controls", "controls": [
        {"id": "r", "label": "R", "type": "range", "min": 5, "max": 1, "step": 1}]}]}}, "min < max"),
    ({"card": {}, "options": {"tabs": [{"id": "t", "label": "T", "render": "controls", "controls": [
        {"id": "x", "label": "X", "type": "text", "maxChars": 201}]}]}}, "maxChars is 1 to 200"),
    ({"card": {}, "options": {"tabs": [{"id": "t", "label": "T", "render": "controls", "controls": [
        {"id": "x", "label": "X", "type": "toggle", "min": 1}]}]}}, "only range takes"),
    ({"card": {}, "full": {"modes": ["advanced", "simple"]}}, 'exactly ["simple","advanced"]'),
    ({"card": {}, "full": {"default": "advanced"}}, "default needs modes"),
])
def test_each_rule_refuses_the_whole_declaration_with_its_reason(raw, needle):
    assert needle in refused(raw)


def test_surfaces_are_required_on_protocol_2_and_refused_on_protocol_1():
    assert "declares its surfaces" in check_declaration([1, 2], None, False)
    assert "protocol-2 field" in check_declaration([1], {"card": {}}, True)
    assert check_declaration([1], None, False) is None and check_declaration([2], {"card": {}}, True) is None


# ── pack check + schema ────────────────────────────────────────────────────────────────────

def test_the_v2_scaffold_passes_pack_check_and_echoes_its_surfaces_in_plugin_ready(tmp_path):
    out = tmp_path / "pack"
    done = scaffold(out)
    assert done.returncode == 0, done.stderr
    editor = json.loads((out / "wicked-pack.json").read_text())["editors"][0]
    assert editor["protocol"] == [1, 2] and editor["surfaces"] == DEFAULT_SURFACES
    html = (out / ENTRY).read_text()
    literal = html.split("const SURFACES = ", 1)[1].split(";\n", 1)[0]
    assert json.loads(literal) == editor["surfaces"]
    assert "protocol: [1, 2], surfaces: SURFACES" in html and "__EDITOR" not in html
    assert errors(out) == []


def test_the_scaffold_takes_a_custom_declaration_and_refuses_a_bad_one(tmp_path):
    custom = tmp_path / "s.json"
    custom.write_text(json.dumps({"card": {"aspect": "4:3"}, "full": {}}))
    assert scaffold(tmp_path / "ok", "--surfaces", str(custom)).returncode == 0
    assert json.loads((tmp_path / "ok" / "wicked-pack.json").read_text())["editors"][0]["surfaces"] == {"card": {"aspect": "4:3"}, "full": {}}
    custom.write_text(json.dumps({"card": {"actions": [{"id": "a", "label": "Approve", "verb": "plugin"}]}}))
    bad = scaffold(tmp_path / "bad", "--surfaces", str(custom))
    assert bad.returncode == 2 and "--surfaces refused" in bad.stderr and not (tmp_path / "bad").exists()
    custom.write_text(json.dumps({"card": {"actions": [{"id": "x", "label": "Export", "verb": "host:export"}]}}))
    assert "artifact.export" in scaffold(tmp_path / "x", "--surfaces", str(custom)).stderr


@pytest.mark.parametrize("change, needle", [
    (lambda e: e.pop("surfaces"), "declares its surfaces"),
    (lambda e: e.update(protocol=[1]), "protocol-2 field"),
    (lambda e: e["surfaces"]["card"]["actions"][0].update(label="Deliver"), "a word only the host"),
    (lambda e: e["surfaces"].update(extra=True), 'unknown field "extra"'),
])
def test_pack_check_refuses_a_bad_declaration_under_pk069(tmp_path, change, needle):
    out = tmp_path / "pack"
    assert scaffold(out).returncode == 0
    m = json.loads((out / "wicked-pack.json").read_text())
    change(m["editors"][0])
    (out / "wicked-pack.json").write_text(json.dumps(m))
    found = [e for e in errors(out) if "PK069" in e]
    assert found and needle in found[0]


def test_artifact_theme_is_a_known_permission_with_its_words(tmp_path):
    done = scaffold(tmp_path / "pack", "--permissions", "artifact.read,artifact.theme")
    assert done.returncode == 0, done.stderr
    perms = json.loads((tmp_path / "pack" / "wicked-pack.json").read_text())["editors"][0]["permissions"]
    assert {"id": "artifact.theme", "why": "to change its theme, as new versions you can undo"} in perms
    assert errors(tmp_path / "pack") == []


def _validator():
    jsonschema = pytest.importorskip("jsonschema")
    return jsonschema.Draft7Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))


def test_the_schema_accepts_the_v2_scaffold_and_refuses_the_structural_violations(tmp_path):
    out = tmp_path / "pack"
    assert scaffold(out).returncode == 0
    m = json.loads((out / "wicked-pack.json").read_text())
    v = _validator()
    assert [e.message for e in v.iter_errors(m)] == []
    for mutate in (lambda e: e.pop("surfaces"), lambda e: e.update(protocol=[1]),
                   lambda e: e["surfaces"]["card"].update(aspect="1:1"),
                   lambda e: e["surfaces"]["options"]["tabs"][0].update(render="html")):
        bad = copy.deepcopy(m)
        mutate(bad["editors"][0])
        assert list(v.iter_errors(bad)), "the schema accepted a declaration pack check refuses"


# ── conformance 13-17 (browser) ────────────────────────────────────────────────────────────

def _browser_ready() -> bool:
    try:
        import playwright.sync_api  # noqa: F401, PLC0415
    except ImportError:
        return False
    dist = os.environ.get("WICKED_STUDIO_DIST")
    return bool(dist) and (Path(dist) / "index.html").is_file()


needs_browser = pytest.mark.skipif(not _browser_ready(), reason="needs playwright + chromium and WICKED_STUDIO_DIST (a protocol-2 studio dist)")


def conform(pack: Path) -> tuple[int, dict]:
    done = run("conformance.py", "--pack", str(pack), "--studio-dist", os.environ["WICKED_STUDIO_DIST"])
    return done.returncode, json.loads(done.stdout)


@needs_browser
def test_a_freshly_scaffolded_plugin_passes_every_case_including_13_to_16(tmp_path):
    assert scaffold(tmp_path / "pack").returncode == 0
    code, report = conform(tmp_path / "pack")
    cases = report["editors"][0]["cases"]
    assert code == 0, json.dumps(cases, indent=1)[-3000:]
    assert {"13-surfaces", "14-card", "15-options", "16-full"} <= set(cases) and "17-v1-compat" not in cases


@needs_browser
def test_a_card_only_plugin_passes_with_no_options_or_full_to_probe(tmp_path):
    custom = tmp_path / "s.json"
    custom.write_text(json.dumps({"card": {"interactive": True, "aspect": "16:9"}}))
    assert scaffold(tmp_path / "pack", "--surfaces", str(custom)).returncode == 0
    code, report = conform(tmp_path / "pack")
    cases = report["editors"][0]["cases"]
    assert code == 0, json.dumps(cases, indent=1)[-2000:]
    assert cases["16-full"]["note"] == "no full surface declared" and cases["15-options"]["tabs"] == 0


def _mutated(tmp_path: Path, old: str, new: str) -> Path:
    pack = tmp_path / "pack"
    assert scaffold(pack).returncode == 0
    entry = pack / ENTRY
    text = entry.read_text()
    assert old in text, old
    entry.write_text(text.replace(old, new))
    assert run("pin.py", str(pack)).returncode == 0
    return pack


HEIGHT = "send('ui.height', { px: Math.ceil(document.body.scrollHeight) });"


@needs_browser
def test_a_first_height_later_than_2_s_fails_case_14(tmp_path):
    pack = _mutated(tmp_path, HEIGHT, "setTimeout(() => send('ui.height', { px: Math.ceil(document.body.scrollHeight) }), 2600);")
    code, report = conform(pack)
    assert code == 1 and report["editors"][0]["cases"]["14-card"]["ok"] is False


@needs_browser
def test_an_action_reply_without_a_boolean_handled_fails_case_14(tmp_path):
    pack = _mutated(tmp_path, "answer(d.id, onAction(String(p.id)));", "answer(d.id, {});")
    code, report = conform(pack)
    card = report["editors"][0]["cases"]["14-card"]
    assert code == 1 and card["ok"] is False and card["actions"][0]["reply"]["valid"] is False


@needs_browser
@pytest.mark.parametrize("reply", [
    # what is transmitted (a class instance clones to {}) is what counts, never what toJSON says
    "answer(d.id, new (class { toJSON() { return { handled: true }; } })());",
    # a wrong envelope is not an answer, however right its payload
    "port.postMessage({ p: 'wrong', v: 1, re: d.id, ok: true, payload: { handled: true } });",
])
def test_a_reply_the_host_would_not_accept_fails_case_14(tmp_path, reply):
    pack = _mutated(tmp_path, "answer(d.id, onAction(String(p.id)));", reply)
    code, report = conform(pack)
    assert code == 1 and report["editors"][0]["cases"]["14-card"]["ok"] is False


@needs_browser
def test_an_editor_that_refuses_a_change_still_answers_case_15(tmp_path):
    pack = _mutated(tmp_path, "if (!ok) return {", "if (ok || !ok) return {")
    code, report = conform(pack)
    cases = report["editors"][0]["cases"]
    assert code == 0, json.dumps(cases, indent=1)[-2000:]
    assert all(c["applied"] is False and c["answered"] for c in cases["15-options"]["tabs"][0]["changes"])


@needs_browser
def test_snapshots_that_arrive_late_still_pass_case_15(tmp_path):
    pack = _mutated(tmp_path, "if (surface === 'options') for (const id of Object.keys(values)) send('options.values', { tab: id, rev: revs[id], values: values[id] });",
                    "if (surface === 'options') setTimeout(() => { for (const id of Object.keys(values)) send('options.values', { tab: id, rev: revs[id], values: values[id] }); }, 1500);")
    code, report = conform(pack)
    assert code == 0, json.dumps(report["editors"][0]["cases"], indent=1)[-2000:]


@needs_browser
def test_a_plugin_whose_ready_disagrees_with_its_manifest_fails_case_13(tmp_path):
    pack = tmp_path / "pack"
    assert scaffold(pack).returncode == 0
    entry = pack / ENTRY
    entry.write_text(entry.read_text().replace('"label": "Next part"', '"label": "Next item"'))
    assert run("pin.py", str(pack)).returncode == 0
    code, report = conform(pack)
    assert code == 1 and report["editors"][0]["cases"]["13-surfaces"]["ok"] is False


@needs_browser
def test_a_protocol_1_plugin_passes_case_17_under_the_v2_host(tmp_path):
    pack = tmp_path / "pack"
    assert scaffold(pack).returncode == 0
    entry = pack / ENTRY
    entry.write_text(entry.read_text().replace("protocol: [1, 2], surfaces: SURFACES", "protocol: [1]"))
    m = json.loads((pack / "wicked-pack.json").read_text())
    m["editors"][0]["protocol"] = [1]
    del m["editors"][0]["surfaces"]
    (pack / "wicked-pack.json").write_text(json.dumps(m))
    assert run("pin.py", str(pack)).returncode == 0
    code, report = conform(pack)
    cases = report["editors"][0]["cases"]
    assert code == 0, json.dumps(cases, indent=1)[-2000:]
    assert cases["17-v1-compat"] == {"ok": True, "negotiated": 1} and "13-surfaces" not in cases
