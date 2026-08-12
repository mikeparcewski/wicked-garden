"""Pack discovery + registration (extension-contract gaps 1 and 4).

Covers: WICKED_PACK_PATH discovery (pack root + directory-of-packs),
registered.json discovery, dedupe priority, provenance hash recording,
registration fail-closed on non-conformant packs, and peer-floor checks
(gap 6) staying fail-open.
"""

import json
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "scripts"))

import _pack_registry as preg  # noqa: E402

FIXTURES = _REPO / "tests" / "fixtures" / "packs"
VALID = FIXTURES / "acme-seo"
BROKEN = FIXTURES / "acme-broken"


@pytest.fixture()
def isolated_registry(tmp_path, monkeypatch):
    """Point the registered-pack file at a temp location; no env packs."""
    reg = tmp_path / "registered.json"
    monkeypatch.setenv("WICKED_PACK_REGISTRY", str(reg))
    monkeypatch.delenv("WICKED_PACK_PATH", raising=False)
    return reg


def _discover_names(cwd=None):
    packs, errors = preg.discover_packs(cwd=cwd or Path.cwd())
    return {p.name for p in packs}, errors


def test_env_path_discovers_pack_root(isolated_registry, monkeypatch):
    monkeypatch.setenv("WICKED_PACK_PATH", str(VALID))
    names, _ = _discover_names()
    assert "acme-seo" in names


def test_env_path_discovers_directory_of_packs(isolated_registry, monkeypatch):
    monkeypatch.setenv("WICKED_PACK_PATH", str(FIXTURES))
    names, _ = _discover_names()
    # Both fixtures are STRUCTURALLY valid (the broken one fails only the
    # conformance gate), so a directory-of-packs surfaces both.
    assert {"acme-seo", "acme-broken"} <= names


def test_registered_pack_is_discovered(isolated_registry):
    preg.register_pack(VALID, source_url="https://example.test/acme-seo")
    names, _ = _discover_names()
    assert "acme-seo" in names
    packs, _ = preg.discover_packs()
    pack = next(p for p in packs if p.name == "acme-seo")
    assert pack.source == "registered"


def test_register_records_provenance_hashes(isolated_registry):
    record = preg.register_pack(VALID, source_url="https://example.test/acme-seo")
    assert record["source_url"] == "https://example.test/acme-seo"
    assert record["publisher"] == "acme"
    assert len(record["manifest_sha256"]) == 64
    assert len(record["skills_tree_sha256"]) == 64
    on_disk = json.loads(isolated_registry.read_text(encoding="utf-8"))
    assert on_disk["packs"][0]["manifest_sha256"] == record["manifest_sha256"]


def test_register_refuses_nonconformant_pack(isolated_registry):
    with pytest.raises(ValueError, match="failed conformance"):
        preg.register_pack(BROKEN)
    # fail-closed: nothing half-registered
    assert not preg.registered_records()


def test_register_force_overrides_conformance_gate(isolated_registry):
    record = preg.register_pack(BROKEN, force=True)
    assert record["name"] == "acme-broken"


def test_unregister_roundtrip(isolated_registry):
    preg.register_pack(VALID)
    assert preg.unregister_pack("acme-seo") is True
    assert preg.unregister_pack("acme-seo") is False
    names, _ = _discover_names()
    assert "acme-seo" not in names


def test_duplicate_name_first_source_wins(isolated_registry, monkeypatch, tmp_path):
    # env (priority 1) vs registered (priority 2) — env wins the dedupe.
    preg.register_pack(VALID)
    monkeypatch.setenv("WICKED_PACK_PATH", str(VALID))
    packs, _ = preg.discover_packs()
    matches = [p for p in packs if p.name == "acme-seo"]
    assert len(matches) == 1
    assert matches[0].source == "env"


def test_structurally_invalid_pack_reported_not_raised(isolated_registry, monkeypatch, tmp_path):
    bad = tmp_path / "bad-pack"
    bad.mkdir()
    (bad / "wicked-pack.json").write_text("{not json", encoding="utf-8")
    monkeypatch.setenv("WICKED_PACK_PATH", str(bad))
    packs, errors = preg.discover_packs()
    assert all(p.name != "bad-pack" for p in packs)
    assert any("invalid JSON" in e for e in errors)


def test_reserved_vendor_prefix_rejected(isolated_registry, monkeypatch, tmp_path):
    squatter = tmp_path / "wicked-fake"
    (squatter / "skills").mkdir(parents=True)
    (squatter / "wicked-pack.json").write_text(json.dumps({
        "spec": 1, "name": "wicked-fake", "vendor": "wicked-fake",
        "version": "1.0.0", "domains": [{"name": "fake"}],
    }), encoding="utf-8")
    monkeypatch.setenv("WICKED_PACK_PATH", str(squatter))
    packs, errors = preg.discover_packs()
    assert all(p.name != "wicked-fake" for p in packs)
    assert any("reserved prefix" in e for e in errors)


def test_specialist_entries_shape(isolated_registry, monkeypatch):
    monkeypatch.setenv("WICKED_PACK_PATH", str(VALID))
    packs, _ = preg.discover_packs()
    entries = preg.specialist_entries(packs)
    assert entries == [{
        "name": "acme-seo",
        "role": "seo-engineering",
        "description": ("SEO specialist — keyword strategy, content audits, "
                        "and crawlability review with recorded evidence."),
        "enhances": ["design", "build", "review"],
        "pack": "acme-seo",
    }]


def test_pack_produces_exposed(isolated_registry, monkeypatch):
    monkeypatch.setenv("WICKED_PACK_PATH", str(VALID))
    packs, _ = preg.discover_packs()
    produces = preg.pack_produces(packs)
    assert produces == [{
        "pack": "acme-seo", "domain": "acme-seo", "archetype": "review",
        "produces": ["seo-audit"], "gate": "vault",
    }]


# ---------------------------------------------------------------------------
# Peer floors (gap 6) — fail-open by contract
# ---------------------------------------------------------------------------

def test_peer_floors_garden_ok_without_probe(isolated_registry, monkeypatch):
    monkeypatch.setenv("WICKED_PACK_PATH", str(VALID))
    packs, _ = preg.discover_packs()
    findings = preg.check_peer_floors(packs, plugin_root=_REPO, probe=False)
    by_peer = {f["peer"]: f for f in findings}
    # garden's own version is comparable without any subprocess
    assert by_peer["wicked-garden"]["status"] == "ok"
    # probe=False leaves binary peers unknown — informational, never a block
    assert by_peer["wicked-vault"]["status"] == "unknown"


def test_peer_floor_violation_detected(isolated_registry, monkeypatch, tmp_path):
    demanding = tmp_path / "acme-future"
    (demanding / "skills" / "acme-future").mkdir(parents=True)
    (demanding / "skills" / "acme-future" / "SKILL.md").write_text(
        "---\nname: acme-future\ndescription: r\n---\n# r\n", encoding="utf-8")
    (demanding / "wicked-pack.json").write_text(json.dumps({
        "spec": 1, "name": "acme-future", "vendor": "acme", "version": "1.0.0",
        "domains": [{"name": "future"}],
        "peers": {"wicked-garden": ">=99999.0.0", "wicked-vault": "banana"},
    }), encoding="utf-8")
    monkeypatch.setenv("WICKED_PACK_PATH", str(demanding))
    packs, _ = preg.discover_packs()
    findings = preg.check_peer_floors(packs, plugin_root=_REPO, probe=False)
    statuses = {f["peer"]: f["status"] for f in findings}
    assert statuses["wicked-garden"] == "below-floor"
    assert statuses["wicked-vault"] == "bad-range"


def test_peer_floors_never_raise(isolated_registry):
    # No packs at all — empty findings, no exception.
    assert preg.check_peer_floors([], probe=False) == []
