"""specialist_resolver resolves pack workers (extension-contract gap 2).

Crew dispatch by ``{vendor}-{domain}-{role}`` must resolve a pack worker
exactly like a first-party one; garden always wins name collisions; a
broken pack can never break first-party resolution.
"""

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "scripts"))

from crew.specialist_resolver import build_resolver, clear_cache, resolve_role  # noqa: E402

FIXTURES = _REPO / "tests" / "fixtures" / "packs"
VALID = FIXTURES / "acme-seo"


@pytest.fixture()
def pack_env(monkeypatch, tmp_path):
    monkeypatch.setenv("WICKED_PACK_PATH", str(VALID))
    monkeypatch.setenv("WICKED_PACK_REGISTRY", str(tmp_path / "registered.json"))
    clear_cache()
    yield
    clear_cache()


@pytest.fixture()
def no_pack_env(monkeypatch, tmp_path):
    monkeypatch.delenv("WICKED_PACK_PATH", raising=False)
    monkeypatch.setenv("WICKED_PACK_REGISTRY", str(tmp_path / "registered.json"))
    clear_cache()
    yield
    clear_cache()


def test_pack_worker_resolves_by_full_skill_name(pack_env):
    resolver = build_resolver(_REPO)
    assert resolve_role("acme-seo-keyword-analyst", resolver) == \
        ("acme-seo", "acme-seo-keyword-analyst")
    assert resolve_role("acme-seo-content-auditor", resolver) == \
        ("acme-seo", "acme-seo-content-auditor")


def test_pack_worker_resolves_by_bare_role(pack_env):
    resolver = build_resolver(_REPO)
    domain, skill = resolve_role("keyword-analyst", resolver)
    assert (domain, skill) == ("acme-seo", "acme-seo-keyword-analyst")


def test_pack_router_is_not_a_dispatchable_worker(pack_env):
    resolver = build_resolver(_REPO)
    # the router is user-invocable, not context:fork — it must NOT resolve
    assert resolve_role("acme-seo", resolver) == (None, None)


def test_pack_specialist_domain_listed(pack_env):
    resolver = build_resolver(_REPO)
    assert "acme-seo" in resolver["domains"]
    assert "acme-seo" in resolver["packs"]
    # first-party domains still present
    assert "engineering" in resolver["domains"]


def test_first_party_resolution_unchanged_by_pack(pack_env):
    resolver = build_resolver(_REPO)
    domain, skill = resolve_role("wicked-garden-crew-reviewer", resolver)
    assert (domain, skill) == ("crew", "wicked-garden-crew-reviewer")


def test_garden_wins_role_collision(monkeypatch, tmp_path):
    """A pack shipping a worker whose bare role collides with a first-party
    role (``reviewer`` = wicked-garden-crew-reviewer's bare role) must lose
    the bare-role slot (garden indexed first) but still be dispatchable by
    its full name."""
    import json
    pack = tmp_path / "acme-rivals"
    (pack / "skills" / "acme-rivals").mkdir(parents=True)
    (pack / "skills" / "acme-rivals-reviewer").mkdir(parents=True)
    (pack / "wicked-pack.json").write_text(json.dumps({
        "spec": 1, "name": "acme-rivals", "vendor": "acme", "version": "1.0.0",
        "domains": [{"name": "rivals"}],
    }), encoding="utf-8")
    (pack / "skills" / "acme-rivals" / "SKILL.md").write_text(
        "---\nname: acme-rivals\ndescription: router\n---\n# r\n", encoding="utf-8")
    (pack / "skills" / "acme-rivals-reviewer" / "SKILL.md").write_text(
        "---\nname: acme-rivals-reviewer\ncontext: fork\ndescription: w\n---\n# w\n",
        encoding="utf-8")
    monkeypatch.setenv("WICKED_PACK_PATH", str(pack))
    monkeypatch.setenv("WICKED_PACK_REGISTRY", str(tmp_path / "registered.json"))
    clear_cache()
    try:
        resolver = build_resolver(_REPO)
        # bare role: first-party keeps it
        assert resolve_role("reviewer", resolver) == \
            ("crew", "wicked-garden-crew-reviewer")
        # full name: the pack worker still resolves, to ITSELF
        assert resolve_role("acme-rivals-reviewer", resolver) == \
            ("acme-rivals", "acme-rivals-reviewer")
        assert any("collision" in w for w in resolver["warnings"])
    finally:
        clear_cache()


def test_no_packs_resolver_shape_intact(no_pack_env):
    resolver = build_resolver(_REPO)
    assert resolver["packs"] == []
    assert resolve_role("reviewer", resolver) == \
        ("crew", "wicked-garden-crew-reviewer")


def test_broken_discovery_fails_open(monkeypatch, tmp_path, no_pack_env):
    """A garbage WICKED_PACK_PATH must not break first-party resolution."""
    monkeypatch.setenv("WICKED_PACK_PATH", str(tmp_path / "does-not-exist"))
    clear_cache()
    try:
        resolver = build_resolver(_REPO)
        assert resolve_role("wicked-garden-crew-implementer", resolver) == \
            ("crew", "wicked-garden-crew-implementer")
    finally:
        clear_cache()
