"""scripts/_skill_meta.py — the ONE reader of a skill's cross-CLI role (L6 B0, D-21).

The 25 fork-keyed consumers used to each re-derive "is this a worker?" from `context: fork`.
They now call `skill_role()`; these tests pin the helper's table and prove the two consumers
whose silent-drop / silent-register risk the design named behave: the registry finds a role-only
worker and never registers the floor, and pack check FAILS a role-less worker-shaped skill loud.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO / "scripts"))

from _skill_meta import (  # noqa: E402
    CLOSED_KEYS,
    ROLES,
    claude_only_keys,
    metadata_value,
    parse_frontmatter,
    read_frontmatter,
    skill_role,
    skill_role_of,
    split_frontmatter,
)

FLOOR = _REPO / "skills" / "governed-worker" / "SKILL.md"


@pytest.mark.parametrize(("fm", "role"), [
    # declared role wins
    ("name: x\nmetadata:\n  role: worker\n", "worker"),
    ("name: x\nmetadata:\n  role: router\n", "router"),
    ("name: x\nmetadata:\n  role: module\n", "module"),
    ("name: x\nmetadata:\n  role: floor\n", "floor"),
    ("name: x\nmetadata:\n  role: \"worker\"\n", "worker"),
    # declared + legacy: declared wins (a stub that still says context: fork is a module)
    ("name: x\ncontext: fork\nmetadata:\n  role: module\n", "module"),
    ("name: x\nuser-invocable: true\nmetadata:\n  role: floor\n", "floor"),
    # legacy only: crew's fallback order
    ("name: x\ncontext: fork\n", "worker"),
    ("name: x\ncontext: fork\nuser-invocable: true\n", "worker"),
    ("name: x\nuser-invocable: true\n", "router"),
    ("name: x\nuser-invocable: false\n", "module"),
    ("name: x\ndescription: d\n", "module"),
    # neither / odd shapes: never a silent worker
    ("", "module"),
    ("name: x\nmetadata:\n  role: subagent\n", "module"),
    ("name: x\nmetadata: worker\n", "module"),
    ("name: x\nmetadata:\n  phases: \"*\"\n", "module"),
])
def test_skill_role_table(fm, role):
    assert skill_role(fm) == role
    assert skill_role(parse_frontmatter(fm)) == role


def test_skill_role_none_is_module():
    assert skill_role(None) == "module"
    assert set(ROLES) == {"worker", "router", "module", "floor"}


def test_parse_frontmatter_shapes():
    fm = parse_frontmatter(
        'name: wicked-garden-x\ndescription: "a: b"\nallowed-tools:\n  - Read\n  - Grep\n'
        'body: |\n  line one\n  line two\nmetadata:\n  role: worker\n  phases: "build,review"\n'
        'archetype_relevance: ["build", "modernize"]\n'
    )
    assert fm["name"] == "wicked-garden-x"
    assert fm["description"] == "a: b"
    assert fm["allowed-tools"] == ["Read", "Grep"]
    assert fm["body"] == "line one\nline two"
    assert fm["metadata"] == {"role": "worker", "phases": "build,review"}
    assert claude_only_keys(fm) == ["allowed-tools", "archetype_relevance", "body"]
    assert metadata_value(fm, "phases") == "build,review"
    assert metadata_value(fm, "archetypes") == '"build", "modernize"'.replace('"', '"')  # legacy fallback, brackets stripped
    assert metadata_value(fm, "role") == "worker"
    assert metadata_value(fm, "missing") is None
    assert CLOSED_KEYS == {"name", "description", "license", "compatibility", "metadata", "mandates"}


def test_split_frontmatter_requires_a_closing_fence():
    assert split_frontmatter("---\nname: x\n") == (None, "---\nname: x\n")
    assert split_frontmatter("no frontmatter\n") == (None, "no frontmatter\n")
    block, body = split_frontmatter("---\nname: x\n---\n# t\n")
    assert (block, body) == ("name: x", "# t\n")


def test_governed_worker_is_the_floor():
    """The floor is handed to every governed unit; it is never a dispatchable worker."""
    assert skill_role_of(FLOOR) == "floor"
    fm = read_frontmatter(FLOOR)
    assert fm["metadata"]["role"] == "floor"
    assert claude_only_keys(fm) == [], "the floor is the closed-set exemplar"


def test_every_shipped_skill_has_a_role_and_the_catalog_shape_holds():
    """At HEAD every SKILL.md resolves to a role; workers are the top-level `<domain>-<role>` dirs
    (plus the one nested worker), the floor is exactly governed-worker, routers are top-level."""
    roles: dict[str, list[Path]] = {r: [] for r in ROLES}
    for p in sorted((_REPO / "skills").rglob("SKILL.md")):
        roles[skill_role_of(p)].append(p)
    assert [p.parent.name for p in roles["floor"]] == ["governed-worker"]
    assert len(roles["worker"]) >= 70, len(roles["worker"])
    assert sum(p.parent.parent.name == "skills" for p in roles["router"]) >= 15, len(roles["router"])
    # a nested router is one that declared itself (user-invocable / metadata.role) — the same
    # fallback order wicked-crew's skillKindOf applies; modules are the nested default
    for p in roles["router"]:
        if p.parent.parent.name != "skills":
            fm = read_frontmatter(p)
            assert fm.get("user-invocable") == "true" or (fm.get("metadata") or {}).get("role") == "router", p
    assert all(p.parent.parent.name == "skills" for p in roles["worker"] if p.parent.name != "debugging"), \
        "workers are the top-level <domain>-<role> dirs (plus engineering/debugging)"


# --------------------------------------------------------------------------- consumers

def _write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_registry_scan_finds_role_only_workers_and_never_the_floor(tmp_path):
    """`_validate_registry._scan_agents`: a worker declared ONLY by `metadata.role: worker` (no
    `context: fork`) is registered; the floor (governed-worker) and a router are not."""
    from _validate_registry import _scan_agents

    _write(tmp_path, "skills/qe-x-reviewer/SKILL.md",
           "---\nname: wicked-garden-qe-x-reviewer\ndescription: d\nmetadata:\n  role: worker\n---\n# w\n")
    _write(tmp_path, "skills/qe-legacy-worker/SKILL.md",
           "---\nname: wicked-garden-qe-legacy-worker\ndescription: d\ncontext: fork\n---\n# w\n")
    _write(tmp_path, "skills/governed-worker/SKILL.md", FLOOR.read_text(encoding="utf-8"))
    _write(tmp_path, "skills/qe/SKILL.md",
           "---\nname: wicked-garden-qe\ndescription: d\nuser-invocable: true\n---\n# r\n")
    by_id, findings = _scan_agents(tmp_path)
    assert findings == []
    assert "wicked-garden-qe-x-reviewer" in by_id and "x-reviewer" in by_id
    assert "wicked-garden-qe-legacy-worker" in by_id and "legacy-worker" in by_id
    assert "wicked-garden-governed-worker" not in by_id
    assert "governed-worker" not in by_id
    assert "wicked-garden-qe" not in by_id


def test_agent_loader_loads_workers_only(tmp_path):
    from _agents import AgentLoader

    _write(tmp_path, "skills/a-worker/SKILL.md",
           "---\nname: wicked-garden-a-worker\ndescription: d\nmetadata:\n  role: worker\n---\n# body\n")
    _write(tmp_path, "skills/governed-worker/SKILL.md", FLOOR.read_text(encoding="utf-8"))
    _write(tmp_path, "skills/a/SKILL.md",
           "---\nname: wicked-garden-a\ndescription: d\nuser-invocable: true\n---\n# r\n")
    _write(tmp_path, "skills/a/nested/SKILL.md",
           "---\nname: wicked-garden-a-nested\ndescription: d\n---\n# m\n")
    agents = AgentLoader().load_fork_skills(tmp_path / "skills")
    assert set(agents) == {"wicked-garden-a-worker"}


def test_specialist_resolver_indexes_workers_only(tmp_path, monkeypatch):
    from crew.specialist_resolver import build_resolver, clear_cache, resolve_role

    _write(tmp_path, "skills/qe-x-reviewer/SKILL.md",
           "---\nname: wicked-garden-qe-x-reviewer\ndescription: d\nmetadata:\n  role: worker\n---\n# w\n")
    _write(tmp_path, "skills/qe/SKILL.md",
           "---\nname: wicked-garden-qe\ndescription: d\nuser-invocable: true\n---\n# r\n")
    _write(tmp_path, "skills/governed-worker/SKILL.md", FLOOR.read_text(encoding="utf-8"))
    monkeypatch.setenv("WICKED_PACK_PATH", str(tmp_path / "no-packs"))
    monkeypatch.setenv("WICKED_PACK_REGISTRY", str(tmp_path / "registered.json"))
    clear_cache()
    try:
        resolver = build_resolver(tmp_path)
        assert resolve_role("x-reviewer", resolver) == ("qe", "wicked-garden-qe-x-reviewer")
        assert resolve_role("wicked-garden-qe", resolver) == (None, None)
        assert resolve_role("governed-worker", resolver) == (None, None)
    finally:
        clear_cache()


def _pack(root: Path, worker_frontmatter: str) -> Path:
    pack = root / "acme-seo"
    _write(pack, "wicked-pack.json", json.dumps({
        "spec": 1, "name": "acme-seo", "vendor": "acme", "version": "1.0.0",
        "domains": [{"name": "seo"}],
    }))
    _write(pack, "skills/acme-seo/SKILL.md",
           "---\nname: acme-seo\ndescription: router\nmetadata:\n  role: router\n---\n# r\n")
    _write(pack, "skills/acme-seo-keyword-analyst/SKILL.md",
           f"---\nname: acme-seo-keyword-analyst\ndescription: w\n{worker_frontmatter}---\n# w\n")
    return pack


def test_pack_check_pk016_fails_a_role_less_worker_loud(tmp_path):
    """A `{vendor}-{domain}-{role}`-named skill with no role is REFUSED (PK016) with a message that
    names the fix — never a silent drop from the resolver."""
    from pack.check import check_pack

    findings = check_pack(_pack(tmp_path, ""), garden_root=_REPO)
    pk016 = [f for f in findings if f.code == "PK016"]
    assert pk016 and pk016[0].level == "error"
    assert "must declare metadata.role: worker" in pk016[0].message
    assert "role 'module'" in pk016[0].message


@pytest.mark.parametrize("worker_fm", [
    "metadata:\n  role: worker\n",
    "context: fork\n",  # legacy shape still infers worker during the transition
])
def test_pack_check_accepts_a_declared_or_legacy_worker(tmp_path, worker_fm):
    from pack.check import check_pack

    findings = check_pack(_pack(tmp_path, worker_fm), garden_root=_REPO)
    assert not [f for f in findings if f.code in ("PK015", "PK016")], [f.render() for f in findings]


def test_pack_check_pk015_refuses_a_worker_router(tmp_path):
    from pack.check import check_pack

    pack = _pack(tmp_path, "metadata:\n  role: worker\n")
    _write(pack, "skills/acme-seo/SKILL.md",
           "---\nname: acme-seo\ndescription: router\nmetadata:\n  role: worker\n---\n# r\n")
    findings = check_pack(pack, garden_root=_REPO)
    assert [f.code for f in findings if f.code == "PK015"] == ["PK015"]


def test_pack_check_pk020_exempts_worker_and_floor(tmp_path):
    from pack.check import check_pack

    long_body = "line\n" * 300
    pack = _pack(tmp_path, "metadata:\n  role: worker\n")
    _write(pack, "skills/acme-seo-keyword-analyst/SKILL.md",
           "---\nname: acme-seo-keyword-analyst\ndescription: w\nmetadata:\n  role: worker\n---\n" + long_body)
    _write(pack, "skills/acme-seo-floor/SKILL.md",
           "---\nname: acme-seo-floor\ndescription: f\nmetadata:\n  role: floor\n---\n" + long_body)
    findings = check_pack(pack, garden_root=_REPO)
    assert "PK020" not in {f.code for f in findings if f.where.endswith("acme-seo-keyword-analyst/SKILL.md")}
    # the floor is not a worker-shaped name → PK016 (loud) but never PK020
    floor_codes = {f.code for f in findings if f.where.endswith("acme-seo-floor/SKILL.md")}
    assert "PK020" not in floor_codes and "PK016" in floor_codes
