"""E2E: the toy pack travels the REAL third-party path (acceptance evidence).

The scenario the extension contract sells (site #extend): a vendor ships
``acme-seo`` — one router + two ``context: fork`` workers, one
produces-contract, peer floors, provenance — and WITHOUT any garden PR:

  1. the conformance gate passes it (`node install.mjs pack check` — the
     exact command a pack author runs via ``npx wicked-garden pack check``),
  2. and FAILS the deliberately-broken variant with actionable errors,
  3. registration through the real CLI records provenance hashes,
  4. runtime discovery surfaces it in the catalog (`pack list --json`),
  5. crew's specialist resolution finds ``acme-seo-*`` workers,
  6. the SubagentStop engagement tracker accepts the pack's specialist
     domain (the crew routing seam end-to-end),
  7. the router fronts exactly the workers the resolver dispatches,
  8. declared peer floors are checked fail-open.

Runs the shipped entry points as subprocesses — not library shortcuts —
wherever a real user-facing command exists.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "scripts"))

FIXTURES = _REPO / "tests" / "fixtures" / "packs"
VALID = FIXTURES / "acme-seo"
BROKEN = FIXTURES / "acme-broken"

_NODE = shutil.which("node")
_PY = sys.executable


@pytest.fixture()
def pack_home(monkeypatch, tmp_path):
    """Isolated pack registry + no ambient pack env."""
    reg = tmp_path / "registered.json"
    monkeypatch.setenv("WICKED_PACK_REGISTRY", str(reg))
    monkeypatch.delenv("WICKED_PACK_PATH", raising=False)
    from crew.specialist_resolver import clear_cache
    clear_cache()
    yield reg
    clear_cache()


def _run(argv, env_extra=None):
    import os
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(argv, capture_output=True, text=True,
                          timeout=180, env=env, cwd=str(_REPO))


def test_toy_pack_end_to_end(pack_home):
    if _NODE is None:
        pytest.skip("node not available (CI installs it)")

    # 1. conformance gate PASSES the valid pack — the author's command
    check = _run([_NODE, str(_REPO / "install.mjs"), "pack", "check", str(VALID)])
    assert check.returncode == 0, check.stdout + check.stderr
    assert "PASS" in check.stdout

    # 2. the broken variant FAILS with actionable errors
    broken = _run([_NODE, str(_REPO / "install.mjs"), "pack", "check", str(BROKEN)])
    assert broken.returncode == 1
    for expected in ("PK014", "PK016", "PK030", "context: fork", "one router per domain"):
        assert expected in broken.stdout, f"missing {expected!r} in:\n{broken.stdout}"

    # 3. registration through the real CLI (the same code path
    #    wicked-installer's `pack add` invokes) records provenance
    reg = _run([_NODE, str(_REPO / "install.mjs"), "pack", "register", str(VALID),
                "--source", "https://github.com/acme/acme-seo-pack"])
    assert reg.returncode == 0, reg.stdout + reg.stderr
    record = json.loads(reg.stdout)
    assert record["name"] == "acme-seo"
    assert len(record["manifest_sha256"]) == 64
    assert len(record["skills_tree_sha256"]) == 64
    assert record["source_url"] == "https://github.com/acme/acme-seo-pack"

    # ...and the broken variant CANNOT register (fail-closed door)
    reg_broken = _run([_NODE, str(_REPO / "install.mjs"), "pack", "register", str(BROKEN)])
    assert reg_broken.returncode != 0
    assert "failed conformance" in reg_broken.stderr

    # 4. the catalog surfaces the pack — discovery, no garden file edited
    listing = _run([_NODE, str(_REPO / "install.mjs"), "pack", "list", "--json"])
    assert listing.returncode == 0, listing.stdout + listing.stderr
    catalog = json.loads(listing.stdout)
    entry = next(p for p in catalog["packs"] if p["name"] == "acme-seo")
    assert entry["domains"] == ["seo"]
    assert entry["specialists"] == ["acme-seo"]
    assert entry["produces"] == [{"pack": "acme-seo", "domain": "acme-seo",
                                  "archetype": "review", "produces": ["seo-audit"],
                                  "gate": "vault"}]
    assert entry["provenance"]["publisher"] == "acme"

    # 5. crew specialist resolution finds acme-seo-* (gap 2)
    from crew.specialist_resolver import build_resolver, clear_cache, resolve_role
    clear_cache()
    resolver = build_resolver(_REPO)
    assert resolve_role("acme-seo-keyword-analyst", resolver) == \
        ("acme-seo", "acme-seo-keyword-analyst")
    assert resolve_role("acme-seo-content-auditor", resolver) == \
        ("acme-seo", "acme-seo-content-auditor")
    assert "acme-seo" in resolver["domains"]

    # 6. the SubagentStop engagement tracker accepts the pack domain —
    #    the same functions the hook runs (crew routing seam end-to-end)
    import importlib
    import os
    os.environ["CLAUDE_PLUGIN_ROOT"] = str(_REPO)
    hooks_dir = _REPO / "hooks" / "scripts"
    sys.path.insert(0, str(hooks_dir))
    try:
        lifecycle = importlib.import_module("subagent_lifecycle")
        domains = lifecycle._load_specialist_domains()
        assert "acme-seo" in domains
        parsed = lifecycle._parse_specialist_from_agent_type(
            "acme-seo-content-auditor", domains)
        assert parsed == ("acme-seo", "content-auditor")
    finally:
        sys.path.remove(str(hooks_dir))
        os.environ.pop("CLAUDE_PLUGIN_ROOT", None)

    # 7. the router fronts exactly the workers crew can dispatch
    router_body = (VALID / "skills" / "acme-seo" / "SKILL.md").read_text(encoding="utf-8")
    for worker in ("acme-seo-keyword-analyst", "acme-seo-content-auditor"):
        assert worker in router_body
        domain, skill = resolve_role(worker, resolver)
        assert skill == worker and domain == "acme-seo"

    # 8. peer floors surface fail-open (gap 6)
    floors = _run([_NODE, str(_REPO / "install.mjs"), "pack", "floors", "--json"])
    assert floors.returncode == 0, floors.stdout + floors.stderr
    findings = json.loads(floors.stdout)["findings"]
    garden_floor = next(f for f in findings
                        if f["pack"] == "acme-seo" and f["peer"] == "wicked-garden")
    assert garden_floor["status"] == "ok"

    # 9. unregister removes it from the catalog
    unreg = _run([_NODE, str(_REPO / "install.mjs"), "pack", "unregister", "acme-seo"])
    assert unreg.returncode == 0
    listing2 = _run([_NODE, str(_REPO / "install.mjs"), "pack", "list", "--json"])
    assert all(p["name"] != "acme-seo"
               for p in json.loads(listing2.stdout)["packs"])
