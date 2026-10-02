"""wicked-pack.json spec 2: editors[] and blocks[] (EP-G1, DES-artifact-editor-plugins §5.2).

A spec-2 manifest keeps every spec-1 field and adds `editors[]` (an artifact editor: one self-contained HTML
entry pinned by sha256) and `blocks[]` (the preset that produces the pack's kind). `domains` becomes optional
when `editors` is present. Spec-1 packs stay valid. No pack may declare a `wicked` or `wicked-*` editor id
(a name that merely starts with the letters, like `wickedly-terms`, is allowed, as for vendors): first-party
editors ship inside studio, never as packs.

Pinned here: every spec-1 fixture still validates (check + schema), the spec-2 fixture validates, each §5.2
refusal has its own code and message, a `wicked`/`wicked-*` editor id is refused in every pack (even registered
with --force), and the vendor pattern is unchanged.
"""

from __future__ import annotations

import hashlib
import html
import json
import shutil
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "scripts"))

from _pack_registry import discover_packs, register_pack, structural_errors  # noqa: E402
from pack.check import check_pack  # noqa: E402

FIXTURES = _REPO / "tests" / "fixtures" / "packs"
SPEC2 = FIXTURES / "acme-terms"
SCHEMA = _REPO / "schemas" / "wicked-pack.schema.json"


def _errors(findings):
    return [f for f in findings if f.level == "error"]


def _copy(tmp_path: Path) -> Path:
    root = tmp_path / "acme-terms"
    shutil.copytree(SPEC2, root)
    return root


def _manifest(root: Path) -> dict:
    return json.loads((root / "wicked-pack.json").read_text(encoding="utf-8"))


def _write(root: Path, manifest: dict) -> None:
    (root / "wicked-pack.json").write_text(json.dumps(manifest), encoding="utf-8")


def _editor(root: Path, **changes) -> Path:
    m = _manifest(root)
    m["editors"][0].update(changes)
    _write(root, m)
    return root


def _rendered(root: Path) -> str:
    return "\n".join(f.render() for f in _errors(check_pack(root, garden_root=_REPO)))


def _nested_srcdoc(levels: int) -> str:
    inner = '<script src="https://cdn.example.com/x.js"></script>'
    for _ in range(levels):
        inner = '<iframe srcdoc="' + html.escape(inner, quote=True) + '"></iframe>'
    return inner


# ---- what passes ------------------------------------------------------------------------------------------------

def test_the_spec2_fixture_with_an_editor_and_a_block_passes_clean():
    findings = check_pack(SPEC2, garden_root=_REPO)
    assert _errors(findings) == [], [f.render() for f in findings]


@pytest.mark.parametrize("fixture", ["acme-seo"])
def test_every_valid_spec1_fixture_still_passes(fixture):
    assert _errors(check_pack(FIXTURES / fixture, garden_root=_REPO)) == []


def test_an_editor_only_pack_needs_no_domains_and_no_skills(tmp_path):
    root = _copy(tmp_path)
    m = _manifest(root)
    del m["domains"], m["blocks"]
    _write(root, m)
    shutil.rmtree(root / "skills")
    assert structural_errors(m, root) == []
    assert _rendered(root) == ""


def test_a_spec2_pack_without_editors_still_needs_domains(tmp_path):
    root = _copy(tmp_path)
    m = _manifest(root)
    del m["domains"], m["editors"], m["blocks"]
    _write(root, m)
    assert "domains must be a non-empty array" in "; ".join(structural_errors(m, root))


def test_editors_need_spec_2(tmp_path):
    root = _copy(tmp_path)
    m = _manifest(root)
    m["spec"] = 1
    _write(root, m)
    assert any("spec 2" in e for e in structural_errors(m, root)), structural_errors(m, root)


def test_an_unknown_spec_is_refused(tmp_path):
    root = _copy(tmp_path)
    m = _manifest(root)
    m["spec"] = 3
    assert any("spec must be 1 or 2" in e for e in structural_errors(m, root))


def test_discovery_finds_a_spec2_pack(tmp_path, monkeypatch):
    root = _copy(tmp_path)
    monkeypatch.setenv("WICKED_PACK_PATH", str(root))
    monkeypatch.setenv("WICKED_PACK_REGISTRY", str(tmp_path / "registered.json"))
    monkeypatch.chdir(tmp_path)
    packs, errors = discover_packs()
    assert [p.name for p in packs if p.name == "acme-terms"] == ["acme-terms"], errors


# ---- each §5.2 refusal, with its message --------------------------------------------------------------------------

@pytest.mark.parametrize("editor_id", ["wicked", "wicked-page", "wicked-terms"])
def test_a_wicked_editor_id_is_refused_in_every_pack(tmp_path, editor_id):
    root = _editor(_copy(tmp_path), id=editor_id)
    assert "PK061" in _rendered(root) and "reserved" in _rendered(root)
    # Structural, so even `pack register --force` (which skips conformance) refuses it.
    errs = structural_errors(_manifest(root), root)
    assert any(f"editor id {editor_id!r}" in e for e in errs), errs
    with pytest.raises(ValueError, match="reserved"):
        register_pack(root, force=True)


def test_a_vendor_that_merely_starts_with_wicked_letters_is_still_allowed(tmp_path):
    """The vendor pattern is unchanged: exactly `wicked` and `wicked-*` are reserved."""
    root = _copy(tmp_path)
    m = _manifest(root)
    m["vendor"], m["name"] = "wickedly", "wickedly-terms"
    m["editors"][0]["id"] = "wickedly-terms"
    _write(root, m)
    assert not any("reserved" in e for e in structural_errors(m, root))


@pytest.mark.parametrize("entry,needle", [
    ("../outside.html", "inside the pack"),
    ("/etc/passwd.html", "inside the pack"),
    ("editors/acme-terms/missing.html", "not found"),
    ("presets/terms-review.json", "single .html file"),
])
def test_the_entry_must_be_one_html_file_inside_the_pack(tmp_path, entry, needle):
    root = _editor(_copy(tmp_path), entry=entry)
    out = _rendered(root)
    assert "PK062" in out and needle in out, out


def test_an_entry_symlinked_out_of_the_pack_is_refused(tmp_path):
    root = _copy(tmp_path)
    outside = tmp_path / "outside.html"
    outside.write_text("<!doctype html><p>x</p>", encoding="utf-8")
    link = root / "editors" / "acme-terms" / "link.html"
    link.symlink_to(outside)
    _editor(root, entry="editors/acme-terms/link.html")
    assert "PK062" in _rendered(root) and "inside the pack" in _rendered(root)


def test_the_entry_hash_must_match(tmp_path):
    root = _editor(_copy(tmp_path), sha256="0" * 64)
    out = _rendered(root)
    assert "PK064" in out and "sha256" in out and "does not match" in out, out


def test_the_entry_must_fit_its_own_limit_and_the_hosts(tmp_path):
    root = _editor(_copy(tmp_path), limits={"bundleBytes": 10})
    assert "PK063" in _rendered(root) and "bundleBytes" in _rendered(root)
    root2 = _editor(_copy(tmp_path / "b"), limits={"bundleBytes": 6_000_000})
    assert "PK063" in _rendered(root2) and "host" in _rendered(root2)


@pytest.mark.parametrize("tag", [
    '<script src="https://cdn.example.com/x.js"></script>',
    '<link rel="stylesheet" href="https://cdn.example.com/x.css">',
    '<iframe src="https://example.com/"></iframe>',
    "<script src='app.js'></script>",
    "<style>@import url(https://cdn.example.com/x.css);</style>",
    '<div style="background: red; @import url(x.css)"></div>',
    '<iframe srcdoc="&lt;script src=https://cdn.example.com/x.js&gt;&lt;/script&gt;"></iframe>',
    '<link rel="modulepreload" href="https://cdn.example.com/m.js">',
    '<object data="https://example.com/x.swf"></object>',
    '<embed src="https://example.com/x.pdf">',
    '<script src="https://cdn.example.com/x.js" src=""></script>',  # the browser uses the FIRST src
    _nested_srcdoc(5),  # nested deeper than the check inspects: it fails closed
])
def test_an_entry_that_loads_anything_outside_itself_is_refused(tmp_path, tag):
    root = _copy(tmp_path)
    entry = root / "editors" / "acme-terms" / "index.html"
    html = entry.read_text(encoding="utf-8").replace("</body>", tag + "\n</body>")
    entry.write_text(html, encoding="utf-8")
    _editor(root, sha256=hashlib.sha256(entry.read_bytes()).hexdigest())
    out = _rendered(root)
    assert "PK065" in out and "self-contained" in out, out


@pytest.mark.parametrize("kinds", [["Document"], ["d"], ["page_view"], []])
def test_kinds_must_be_artifact_kinds(tmp_path, kinds):
    root = _editor(_copy(tmp_path), kinds=kinds)
    assert "PK066" in _rendered(root)


@pytest.mark.parametrize("sizes,needle", [(["pane", "full"], 'must include "inline"'), (["inline", "huge"], "unknown size")])
def test_sizes_must_include_inline(tmp_path, sizes, needle):
    root = _editor(_copy(tmp_path), sizes=sizes)
    out = _rendered(root)
    assert "PK067" in out and needle in out, out


@pytest.mark.parametrize("perm,needle", [
    ({"id": "network.fetch", "why": "to call home"}, "unknown permission"),
    ({"id": "artifact.read"}, 'needs a "why"'),
    ({"id": "artifact.read", "why": "  "}, 'needs a "why"'),
])
def test_permissions_must_be_known_and_explained(tmp_path, perm, needle):
    root = _editor(_copy(tmp_path), permissions=[perm])
    out = _rendered(root)
    assert "PK068" in out and needle in out, out


def test_an_oversized_entry_is_refused_without_being_read(tmp_path, monkeypatch):
    root = _copy(tmp_path)
    entry = root / "editors" / "acme-terms" / "index.html"
    with entry.open("ab") as fh:
        fh.truncate(6 * 1024 * 1024)  # sparse: over the host cap
    _editor(root, limits=None)
    m = _manifest(root)
    del m["editors"][0]["limits"]
    _write(root, m)
    read = []
    real = Path.read_bytes
    monkeypatch.setattr(Path, "read_bytes", lambda self: read.append(self.name) or real(self))
    out = _rendered(root)
    assert "PK063" in out and "host cap" in out, out
    assert "index.html" not in read, "an entry over the cap must not be read into memory"


def test_a_permission_with_an_unknown_field_is_refused(tmp_path):
    root = _editor(_copy(tmp_path), permissions=[{"id": "artifact.read", "why": "to read it", "reason": "typo"}])
    out = _rendered(root)
    assert "PK068" in out and "unknown field" in out, out


def test_the_entry_suffix_is_lowercase_html_as_in_the_schema(tmp_path):
    root = _copy(tmp_path)
    (root / "editors" / "acme-terms" / "index.html").rename(root / "editors" / "acme-terms" / "index.HTML")
    _editor(root, entry="editors/acme-terms/index.HTML")
    assert "PK062" in _rendered(root)


@pytest.mark.parametrize("field,value", [
    ("title", ""), ("version", "one"), ("protocol", []), ("protocol", ["1"]),
    ("panels", ["comments"]), ("sha256", "abc"),
])
def test_a_malformed_editor_field_is_refused(tmp_path, field, value):
    root = _editor(_copy(tmp_path), **{field: value})
    out = _rendered(root)
    assert "PK060" in out and field in out, out


def test_duplicate_editor_ids_are_refused(tmp_path):
    root = _copy(tmp_path)
    m = _manifest(root)
    m["editors"].append(dict(m["editors"][0]))
    _write(root, m)
    assert "PK060" in _rendered(root) and "duplicate" in _rendered(root)


@pytest.mark.parametrize("change,code,needle", [
    ({"preset": "../x.json"}, "PK070", "inside the pack"),
    ({"preset": "presets/missing.json"}, "PK070", "not found"),
    ({"produces_kind": "Doc"}, "PK070", "produces_kind"),
    ({"label": ""}, "PK070", "label"),
    ({"skills": ["acme-terms-ghost"]}, "PK071", "not a skill in this pack"),
    ({"id": "wicked-terms-review"}, "PK072", "reserved"),
])
def test_each_block_refusal_has_its_message(tmp_path, change, code, needle):
    root = _copy(tmp_path)
    m = _manifest(root)
    m["blocks"][0].update(change)
    _write(root, m)
    out = _rendered(root)
    assert code in out and needle in out, out


@pytest.mark.parametrize("skills", [[{}], [None], [["acme-terms-checker"]], "acme-terms-checker"])
def test_a_malformed_block_skills_value_is_a_finding_not_a_crash(tmp_path, skills):
    root = _copy(tmp_path)
    m = _manifest(root)
    m["blocks"][0]["skills"] = skills
    _write(root, m)
    out = _rendered(root)
    assert "PK070" in out or "PK071" in out, out


@pytest.mark.parametrize("field,value", [("editors", [None, "x"]), ("blocks", [None])])
def test_non_object_entries_are_findings_not_crashes(tmp_path, field, value):
    root = _copy(tmp_path)
    m = _manifest(root)
    m[field] = value
    _write(root, m)
    assert ("PK060" if field == "editors" else "PK070") in _rendered(root)


@pytest.mark.parametrize("domains", [42, "terms", {"name": "terms"}])
def test_a_non_list_domains_value_is_a_finding_not_a_crash(tmp_path, domains):
    root = _copy(tmp_path)
    m = _manifest(root)
    m["domains"] = domains
    _write(root, m)
    assert "domains must be a non-empty array" in _rendered(root)


def test_a_preset_that_is_not_a_json_object_is_refused(tmp_path):
    root = _copy(tmp_path)
    (root / "presets" / "terms-review.json").write_text("[1, 2]", encoding="utf-8")
    assert "PK070" in _rendered(root) and "JSON object" in _rendered(root)


# ---- the JSON schema agrees ----------------------------------------------------------------------------------------

def _validator():
    jsonschema = pytest.importorskip("jsonschema")
    return jsonschema.Draft7Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))


@pytest.mark.parametrize("fixture", ["acme-seo", "acme-terms"])
def test_the_schema_accepts_the_valid_spec1_and_spec2_fixtures(fixture):
    v = _validator()
    errors = [e.message for e in v.iter_errors(json.loads((FIXTURES / fixture / "wicked-pack.json").read_text()))]
    assert errors == []


def test_the_schema_accepts_an_editor_only_spec2_pack():
    m = json.loads((SPEC2 / "wicked-pack.json").read_text())
    del m["domains"], m["blocks"]
    assert list(_validator().iter_errors(m)) == []


@pytest.mark.parametrize("mutate", [
    lambda m: m["editors"][0].update(id="wicked-page"),
    lambda m: m.update(spec=1),                                   # editors need spec 2
    lambda m: (m.pop("domains"), m.pop("editors"), m.pop("blocks")),  # spec 2 without editors needs domains
    lambda m: m["editors"][0].update(sizes=["pane"]),
    lambda m: m["editors"][0]["permissions"].append({"id": "network.fetch", "why": "x"}),
    lambda m: m["blocks"][0].update(id="wicked-review"),
])
def test_the_schema_refuses_what_pack_check_refuses(mutate):
    m = json.loads((SPEC2 / "wicked-pack.json").read_text())
    mutate(m)
    assert list(_validator().iter_errors(m)), "the schema accepted a manifest pack check refuses"
