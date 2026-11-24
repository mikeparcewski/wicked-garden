"""wicked-pack.json spec 2: plugins[] (CS7, DESIGN §2.b, CONTRACT-CS7 §C1 & §C2).

Pinned here:
- a valid plugin-only spec-2 pack passes check_pack, structural_errors, discover_packs, and the JSON schema;
- spec 1 refuses plugins[];
- each §C2 valid topic pattern passes and each §C2 invalid example fails (PK086 + schema);
- duplicate topics, missing/oversized why fail (PK086);
- a permissions key on a plugin entry is refused (PK080 + schema);
- editor and plugin ids share one namespace: a duplicate id across an editor and a plugin fails (PK080);
- reserved wicked / wicked-* plugin ids are refused (PK081 + structural_errors);
- entry path, size cap, sha256 mismatch (PK084), and external references (PK085) are enforced;
- panels rules (PK087) and visuals.icon / samples files and caps (PK088) are enforced.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "scripts"))

from _pack_registry import discover_packs, register_pack, structural_errors  # noqa: E402
from editor._pack import ICON_CAP, SAMPLES_CAP, valid_topic_pattern  # noqa: E402
from pack.check import check_pack  # noqa: E402

SCHEMA = _REPO / "schemas" / "wicked-pack.schema.json"

ENTRY_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Phase spend</title></head>
<body><main id="events"></main>
<script>
(() => {
  'use strict';
  let port = null;
  window.addEventListener('message', (e) => {
    if (port || !e.data || e.data.p !== 'wicked.editor' || e.data.type !== 'host.hello' || !e.ports || !e.ports[0]) return;
    port = e.ports[0];
    port.onmessage = (m) => {
      const d = m.data;
      if (d && d.p === 'wicked.editor' && d.v === 1 && d.type === 'host.ping') {
        port.postMessage({ p: 'wicked.editor', v: 1, re: d.id, ok: true, payload: {} });
      }
    };
  });
  parent.postMessage({ p: 'wicked.editor', v: 1, type: 'plugin.ready', payload: { editor: 'acme-spend', version: '0.1.0', protocol: [3] } }, '*');
})();
</script></body></html>
"""

SAMPLE_NDJSON = (
    '{"type":"sessionStarted","session":"conformance-run","seq":1,"ts":1767225601000}\n'
    '{"type":"cliUsage","session":"conformance-run","seq":2,"ts":1767225602000,"inputTokens":100}\n'
)

ICON_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><circle cx="8" cy="8" r="6"/></svg>\n'


def _make_plugin_pack(tmp_path: Path, name: str = "acme-spend") -> Path:
    root = tmp_path / name
    entry_rel = "plugins/acme-spend/index.html"
    samples_rel = "samples/events.ndjson"
    icon_rel = "plugins/acme-spend/icon.svg"
    (root / "plugins" / "acme-spend").mkdir(parents=True, exist_ok=True)
    (root / "samples").mkdir(parents=True, exist_ok=True)
    entry_file = root / entry_rel
    entry_file.write_text(ENTRY_HTML, encoding="utf-8")
    (root / samples_rel).write_text(SAMPLE_NDJSON, encoding="utf-8")
    (root / icon_rel).write_text(ICON_SVG, encoding="utf-8")
    sha = hashlib.sha256(entry_file.read_bytes()).hexdigest()
    manifest = {
        "spec": 2,
        "name": "acme-spend",
        "vendor": "acme",
        "version": "0.1.0",
        "description": "Phase spend run plugin for wicked-studio.",
        "plugins": [{
            "id": "acme-spend",
            "title": "Phase spend",
            "version": "0.1.0",
            "protocol": [3],
            "inline": "run-thread",
            "entry": entry_rel,
            "sha256": sha,
            "description": "Shows each phase's elapsed time and token spend.",
            "observe": [
                {"topic": "wicked.run.phase.*", "why": "to show when each phase starts and finishes"},
                {"topic": "wicked.run.usage.reported", "why": "to sum token usage per phase"},
            ],
            "panels": [{
                "slot": "run.details",
                "id": "acme-spend",
                "title": "Spend · {phase}",
                "instances": "per-phase",
                "order": 40,
                "defaultOpen": "while-live",
                "summary": "plugin",
            }],
            "visuals": {"color": "#224a5e", "icon": icon_rel},
            "samples": samples_rel,
        }],
    }
    (root / "wicked-pack.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return root


def _manifest(root: Path) -> dict:
    return json.loads((root / "wicked-pack.json").read_text(encoding="utf-8"))


def _write(root: Path, manifest: dict) -> None:
    (root / "wicked-pack.json").write_text(json.dumps(manifest), encoding="utf-8")


def _plugin(root: Path, **changes) -> Path:
    m = _manifest(root)
    m["plugins"][0].update(changes)
    _write(root, m)
    return root


def _errors(findings):
    return [f for f in findings if f.level == "error"]


def _rendered(root: Path) -> str:
    return "\n".join(f.render() for f in _errors(check_pack(root, garden_root=_REPO)))


# ---- valid plugin-only pack -------------------------------------------------------------------------------------

def test_a_valid_plugin_only_pack_passes_check_and_discovery(tmp_path, monkeypatch):
    root = _make_plugin_pack(tmp_path)
    m = _manifest(root)
    assert structural_errors(m, root) == []
    assert _rendered(root) == ""
    monkeypatch.setenv("WICKED_PACK_PATH", str(root))
    monkeypatch.setenv("WICKED_PACK_REGISTRY", str(tmp_path / "registered.json"))
    monkeypatch.chdir(tmp_path)
    packs, errs = discover_packs()
    assert [p.name for p in packs if p.name == "acme-spend"] == ["acme-spend"], errs


def test_plugins_need_spec_2(tmp_path):
    root = _make_plugin_pack(tmp_path)
    m = _manifest(root)
    m["spec"] = 1
    _write(root, m)
    assert any("spec 2" in e for e in structural_errors(m, root))
    assert "PK002" in _rendered(root)


# ---- §C2 topic pattern rules ------------------------------------------------------------------------------------

@pytest.mark.parametrize("topic", [
    "wicked.run.unit.*",
    "wicked.run.usage.reported",
    "wicked.run.**",
    "wicked.run.phase.started",
    "wicked.run.*.completed",
    "wicked.run.a_1-2.**",
])
def test_valid_c2_topic_patterns_pass(tmp_path, topic):
    assert valid_topic_pattern(topic) is True
    root = _make_plugin_pack(tmp_path)
    _plugin(root, observe=[{"topic": topic, "why": "to observe events"}])
    assert _rendered(root) == ""


@pytest.mark.parametrize("topic", [
    "wicked.**",
    "wicked.bus.x",
    "wicked.run",
    "Wicked.run.x",
    "wicked.run.**.x",
    "",
    "wicked.run.",
    "wicked.run..x",
    "wicked.run.1bad",
    "wicked.run." + "a" * 42,
    "wicked.run." + "a." * 60 + "b",
])
def test_invalid_c2_topic_patterns_fail(tmp_path, topic):
    assert valid_topic_pattern(topic) is False
    root = _make_plugin_pack(tmp_path)
    _plugin(root, observe=[{"topic": topic, "why": "to observe events"}])
    out = _rendered(root)
    assert "PK086" in out, out


def test_duplicate_observe_topics_and_invalid_why_fail(tmp_path):
    root = _make_plugin_pack(tmp_path)
    _plugin(root, observe=[
        {"topic": "wicked.run.unit.*", "why": "first"},
        {"topic": "wicked.run.unit.*", "why": "second"},
    ])
    assert "PK086" in _rendered(root) and "duplicate" in _rendered(root)

    _plugin(root, observe=[{"topic": "wicked.run.unit.*", "why": "   "}])
    assert "PK086" in _rendered(root)

    _plugin(root, observe=[{"topic": "wicked.run.unit.*", "why": "x" * 201}])
    assert "PK086" in _rendered(root)


# ---- permissions refused & shared id namespace ------------------------------------------------------------------

def test_a_permissions_key_on_a_plugin_is_refused(tmp_path):
    root = _make_plugin_pack(tmp_path)
    _plugin(root, permissions=[{"id": "artifact.read", "why": "not allowed on a run plugin"}])
    out = _rendered(root)
    assert "PK080" in out and "permissions" in out, out


def test_duplicate_id_across_an_editor_and_a_plugin_fails(tmp_path):
    root = _make_plugin_pack(tmp_path)
    m = _manifest(root)
    entry_sha = m["plugins"][0]["sha256"]
    m["editors"] = [{
        "id": "acme-spend",
        "title": "Spend editor",
        "version": "0.1.0",
        "protocol": [1],
        "kinds": ["page"],
        "entry": m["plugins"][0]["entry"],
        "sha256": entry_sha,
        "sizes": ["inline", "pane", "full"],
        "permissions": [{"id": "artifact.read", "why": "to read it"}],
    }]
    _write(root, m)
    out = _rendered(root)
    assert "PK080" in out and "duplicate id 'acme-spend'" in out, out


@pytest.mark.parametrize("plugin_id", ["wicked", "wicked-spend", "wicked-run"])
def test_a_wicked_plugin_id_is_refused_in_every_pack(tmp_path, plugin_id):
    root = _plugin(_make_plugin_pack(tmp_path), id=plugin_id)
    out = _rendered(root)
    assert "PK081" in out and "reserved" in out, out
    errs = structural_errors(_manifest(root), root)
    assert any(f"plugin id {plugin_id!r}" in e for e in errs), errs
    with pytest.raises(ValueError, match="reserved"):
        register_pack(root, force=True)


# ---- entry, sha256, panels, visuals, samples --------------------------------------------------------------------

def test_plugin_entry_hash_mismatch_fails(tmp_path):
    root = _plugin(_make_plugin_pack(tmp_path), sha256="0" * 64)
    out = _rendered(root)
    assert "PK084" in out and "sha256" in out and "does not match" in out, out


def test_plugin_entry_external_script_or_outside_path_fails(tmp_path):
    root = _make_plugin_pack(tmp_path)
    _plugin(root, entry="../outside.html")
    assert "PK082" in _rendered(root)

    root2 = _make_plugin_pack(tmp_path / "ext")
    entry = root2 / "plugins" / "acme-spend" / "index.html"
    entry.write_text(ENTRY_HTML.replace("</body>", '<script src="https://evil.example/x.js"></script></body>'), encoding="utf-8")
    _plugin(root2, sha256=hashlib.sha256(entry.read_bytes()).hexdigest())
    assert "PK085" in _rendered(root2)


@pytest.mark.parametrize("change,code", [
    ({"protocol": [1, 2]}, "PK080"),
    ({"inline": "card"}, "PK080"),
    ({"title": "Bad <title>"}, "PK080"),
    ({"title": "x" * 41}, "PK080"),
    ({"description": "d" * 161}, "PK080"),
    ({"panels": [{"slot": "other", "id": "p", "title": "T", "order": 1}]}, "PK087"),
    ({"panels": [{"slot": "run.details", "id": "Bad_Id", "title": "T", "order": 1}]}, "PK087"),
    ({"panels": [{"slot": "run.details", "id": "p", "title": "T", "order": 0}]}, "PK087"),
    ({"panels": [{"slot": "run.details", "id": "p", "title": "T", "order": 100}]}, "PK087"),
    ({"panels": [{"slot": "run.details", "id": "p", "title": "T", "order": 1, "instances": "all"}]}, "PK087"),
    ({"panels": [{"slot": "run.details", "id": "p", "title": "T", "order": 1, "defaultOpen": "sometimes"}]}, "PK087"),
    ({"panels": [{"slot": "run.details", "id": "p", "title": "T", "order": 1, "summary": "host"}]}, "PK087"),
    ({"visuals": {"color": "red"}}, "PK088"),
    ({"visuals": {"icon": "plugins/acme-spend/missing.svg"}}, "PK088"),
    ({"samples": "samples/missing.ndjson"}, "PK088"),
])
def test_plugin_field_panel_visual_and_sample_rules(tmp_path, change, code):
    root = _plugin(_make_plugin_pack(tmp_path), **change)
    out = _rendered(root)
    assert code in out, out


def test_oversized_icon_and_samples_are_refused(tmp_path):
    root = _make_plugin_pack(tmp_path)
    (root / "plugins" / "acme-spend" / "icon.svg").write_bytes(b"<svg>" + b"x" * (ICON_CAP + 10))
    assert "PK088" in _rendered(root)

    root2 = _make_plugin_pack(tmp_path / "s")
    (root2 / "samples" / "events.ndjson").write_bytes(b'{"type":"X"}\n' * (SAMPLES_CAP // 10 + 100))
    assert "PK088" in _rendered(root2)


@pytest.mark.parametrize("field,code", [("entry", "PK082"), ("icon", "PK088"), ("samples", "PK088")])
@pytest.mark.parametrize("link_kind", ["file", "ancestor"])
def test_plugin_assets_refuse_symlinks_even_to_matching_files_inside_pack(tmp_path, field, code, link_kind):
    root = _make_plugin_pack(tmp_path)
    m = _manifest(root)
    plugin = m["plugins"][0]
    rel = plugin["visuals"]["icon"] if field == "icon" else plugin[field]
    asset = root / rel
    try:
        if link_kind == "file":
            target = asset.with_name("real-" + asset.name)
            asset.rename(target)
            asset.symlink_to(target.name)
        else:
            link = root / "linked-assets"
            link.symlink_to(asset.parent.relative_to(root), target_is_directory=True)
            linked_rel = str(Path("linked-assets") / asset.name)
            if field == "icon":
                plugin["visuals"]["icon"] = linked_rel
            else:
                plugin[field] = linked_rel
            _write(root, m)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlinks unavailable: {exc}")
    # Content and hash remain valid; admission must reject the lexical link itself.
    out = _rendered(root)
    assert code in out, out


@pytest.mark.parametrize("resource", [
    '<img src="https://evil.example/leak">',
    '<img src="images/local.png">',
    '<img srcset="https://evil.example/a.png 1x, https://evil.example/b.png 2x">',
    '<img srcset="data:image/png;base64,aGVsbG8= 1x, https://evil.example/x.png 2x">',
    '<video poster="https://evil.example/poster.png"></video>',
    '<style>@font-face { font-family: remote; src: url(https://evil.example/font.woff2); }</style>',
    '<style>body { background: url("https://evil.example/background.png"); }</style>',
    '<div style="background: url(https://evil.example/background.png)"></div>',
    '<script type="module">import "https://evil.example/module.js";</script>',
    '<script type="module">import value from "https://evil.example/module.js";</script>',
    '<script type="module">import {\n value\n} from "https://evil.example/module.js";</script>',
    '<style>body { background: image-set("https://evil.example/x.png" 1x); }</style>',
    '<script type="module">export { value } from "https://evil.example/module.js";</script>',
    '<script type="module">import("https://evil.example/module.js");</script>',
    '<iframe srcdoc="&lt;img src=&quot;https://evil.example/leak&quot;&gt;"></iframe>',
])
def test_plugin_entry_refuses_external_resources_with_correct_hash(tmp_path, resource):
    root = _make_plugin_pack(tmp_path)
    entry = root / _manifest(root)["plugins"][0]["entry"]
    entry.write_text(ENTRY_HTML.replace("</body>", resource + "</body>"), encoding="utf-8")
    _plugin(root, sha256=hashlib.sha256(entry.read_bytes()).hexdigest())
    out = _rendered(root)
    assert "PK085" in out, out
    assert "PK084" not in out, out


def test_plugin_entry_allows_embedded_images_and_fonts(tmp_path):
    root = _make_plugin_pack(tmp_path)
    entry = root / _manifest(root)["plugins"][0]["entry"]
    embedded = (
        '<img src="data:image/png;base64,aGVsbG8=">'
        '<style>@font-face { font-family: embedded; src: url(data:font/woff2;base64,aGVsbG8=); }</style>'
        '<a href="#events">Events</a><div data="row">Row</div>'
        '<img srcset="data:image/png;base64,aGVsbG8= 1x, data:image/png;base64,aGVsbG8= 2x">'
    )
    entry.write_text(ENTRY_HTML.replace("</body>", embedded + "</body>"), encoding="utf-8")
    _plugin(root, sha256=hashlib.sha256(entry.read_bytes()).hexdigest())
    assert _rendered(root) == ""


@pytest.mark.parametrize("sample", [
    {},
    [],
    {"type": 7, "session": "conformance-run", "seq": 2, "ts": 1767225602000},
    {"type": "", "session": "conformance-run", "seq": 2, "ts": 1767225602000},
    {"type": "  ", "session": "conformance-run", "seq": 2, "ts": 1767225602000},
    {"type": "unitExecuting", "seq": 2, "ts": 1767225602000},
    {"type": "unitExecuting", "session": 7, "seq": 2, "ts": 1767225602000},
    {"type": "unitExecuting", "session": "", "seq": 2, "ts": 1767225602000},
    {"type": "unitExecuting", "session": "conformance-run", "ts": 1767225602000},
    {"type": "unitExecuting", "session": "conformance-run", "seq": "2", "ts": 1767225602000},
    {"type": "unitExecuting", "session": "conformance-run", "seq": True, "ts": 1767225602000},
    {"type": "unitExecuting", "session": "conformance-run", "seq": float("inf"), "ts": 1767225602000},
    {"type": "unitExecuting", "session": "conformance-run", "seq": 10**400, "ts": 1767225602000},
    {"type": "unitExecuting", "session": "conformance-run", "seq": 2},
    {"type": "unitExecuting", "session": "conformance-run", "seq": 2, "ts": "2026-01-01T00:00:02Z"},
    {"type": "unitExecuting", "session": "conformance-run", "seq": 2, "ts": False},
    {"type": "unitExecuting", "session": "conformance-run", "seq": 2, "ts": float("nan")},
])
def test_plugin_samples_need_core_event_shape_and_report_line(tmp_path, sample):
    root = _make_plugin_pack(tmp_path)
    samples = root / _manifest(root)["plugins"][0]["samples"]
    first = SAMPLE_NDJSON.splitlines()[0]
    samples.write_text(first + "\n\n" + json.dumps(sample) + "\n", encoding="utf-8")
    out = _rendered(root)
    assert "PK088" in out and "line 3" in out, out


def test_plugin_samples_invalid_json_reports_line(tmp_path):
    root = _make_plugin_pack(tmp_path)
    samples = root / _manifest(root)["plugins"][0]["samples"]
    samples.write_text(SAMPLE_NDJSON.splitlines()[0] + "\n{broken\n", encoding="utf-8")
    out = _rendered(root)
    assert "PK088" in out and "line 2" in out, out


@pytest.mark.parametrize("field", ["visuals", "samples"])
def test_present_null_plugin_fields_are_refused(tmp_path, field):
    root = _plugin(_make_plugin_pack(tmp_path), **{field: None})
    assert "PK088" in _rendered(root)


@pytest.mark.parametrize("control", ["\n", "\r", "\t", "\x00"])
def test_topic_panel_id_and_color_refuse_trailing_controls(tmp_path, control):
    topic = "wicked.run.unit.started" + control
    assert valid_topic_pattern(topic) is False
    root = _make_plugin_pack(tmp_path)
    m = _manifest(root)
    m["plugins"][0]["observe"][0]["topic"] = topic
    m["plugins"][0]["panels"][0]["id"] += control
    m["plugins"][0]["visuals"]["color"] += control
    _write(root, m)
    out = _rendered(root)
    assert all(code in out for code in ("PK086", "PK087", "PK088")), out


# ---- JSON schema agreement --------------------------------------------------------------------------------------

def test_the_schema_structure_and_patterns_match_c1_and_c2():
    import re
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert "plugins[]" in schema["description"]
    assert "plugins[]" in schema["properties"]["spec"]["description"]
    pl_item = schema["properties"]["plugins"]["items"]
    assert pl_item["additionalProperties"] is False
    assert "permissions" not in pl_item["properties"]
    assert set(pl_item["required"]) == {
        "id", "title", "version", "protocol", "inline", "entry", "sha256", "observe", "panels"
    }
    topic_rx = re.compile(pl_item["properties"]["observe"]["items"]["properties"]["topic"]["pattern"])
    for good in ("wicked.run.unit.*", "wicked.run.usage.reported", "wicked.run.**"):
        assert topic_rx.fullmatch(good), good
    for bad in ("wicked.**", "wicked.bus.x", "wicked.run", "Wicked.run.x", "wicked.run.**.x"):
        assert not topic_rx.fullmatch(bad), bad
    spec1_not = schema["allOf"][0]["then"]["not"]["anyOf"]
    assert {"required": ["plugins"]} in spec1_not
    spec2_any = schema["allOf"][1]["then"]["anyOf"]
    assert {"required": ["plugins"]} in spec2_any


def _validator():
    jsonschema = pytest.importorskip("jsonschema")
    return jsonschema.Draft7Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))


def test_the_schema_accepts_a_valid_plugin_only_pack_and_refuses_invalid_ones(tmp_path):
    v = _validator()
    root = _make_plugin_pack(tmp_path)
    m = _manifest(root)
    assert [e.message for e in v.iter_errors(m)] == []

    for bad_topic in ("wicked.**", "wicked.bus.x", "wicked.run", "Wicked.run.x", "wicked.run.**.x"):
        m_bad = json.loads(json.dumps(m))
        m_bad["plugins"][0]["observe"][0]["topic"] = bad_topic
        assert list(v.iter_errors(m_bad)), f"schema accepted invalid topic {bad_topic!r}"

    m_perm = json.loads(json.dumps(m))
    m_perm["plugins"][0]["permissions"] = [{"id": "artifact.read", "why": "no"}]
    assert list(v.iter_errors(m_perm)), "schema accepted permissions on a plugin"

    m_spec1 = json.loads(json.dumps(m))
    m_spec1["spec"] = 1
    m_spec1["domains"] = [{"name": "spend"}]
    assert list(v.iter_errors(m_spec1)), "schema accepted plugins in spec 1"


def test_plugin_samples_read_failure_is_a_finding(tmp_path, monkeypatch):
    root = _make_plugin_pack(tmp_path)
    samples = root / _manifest(root)["plugins"][0]["samples"]
    original = Path.read_text

    def read_text(path, *args, **kwargs):
        if path == samples:
            raise OSError("sample could not be read")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)
    assert "PK088" in _rendered(root)
