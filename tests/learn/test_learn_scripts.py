"""The learn scripts (scripts/learn/): check.py's provenance + skill lint and index.py's scope-replace."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts" / "learn"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(REPO / "scripts"))

from _knowledge import claim_id  # noqa: E402

GOVERNED = ("WICKED_GOVERNED", "WICKED_RUN_ID", "WICKED_GATE_SCOPE", "WICKED_WRITE_ROOTS")


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"learn_{name}", SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


check = _load("check")
index = _load("index")

TEXT_A = "In WAL mode, readers do not block writers and a writer does not block readers."
TEXT_B = "WAL mode does not work on a network filesystem because the wal-index needs shared memory."
NOW = "2026-10-11T04:10:00Z"


def claim(text: str, **over) -> dict:
    c = {"id": claim_id(text), "text": text, "status": "active", "first_seen": NOW, "last_verified": NOW,
         "sources": [{"url": "https://sqlite.org/wal.html", "title": "Write-Ahead Logging", "observed_at": NOW}]}
    c.update(over)
    return c


def write_topic(repo: Path, claims: list[dict], readme: str | None = None, slug: str = "sqlite-wal", **meta) -> Path:
    d = repo / ".wicked" / "knowledge" / slug
    d.mkdir(parents=True, exist_ok=True)
    topic = {"schema": 1, "slug": slug, "title": "SQLite WAL mode", "kind": "topic", "questions": [], **meta}
    (d / "topic.json").write_text(json.dumps(topic), encoding="utf-8")
    (d / "claims.jsonl").write_text("".join(json.dumps(c) + "\n" for c in claims), encoding="utf-8")
    if readme is None:
        cites = " ".join(f"[{c['id']}]" for c in claims if c.get("status") == "active")
        readme = f"# SQLite WAL mode\n\n## Concurrency\nReaders and writers {cites}.\n\n## Sources\n- https://sqlite.org/wal.html\n"
    (d / "README.md").write_text(readme, encoding="utf-8")
    return d


def write_skill(repo: Path, body: str, name: str = "sqlite-wal-setup", topic: str = "sqlite-wal",
                extra_fm: str = "", base: str = ".agents/skills") -> Path:
    d = repo / base / name
    d.mkdir(parents=True, exist_ok=True)
    fm = f"---\nname: {name}\ndescription: |\n  Configure SQLite WAL for many readers.\n{extra_fm}metadata:\n  learn-topic: {topic}\n---\n"
    (d / "SKILL.md").write_text(fm + body, encoding="utf-8")
    return d


def rules(out: dict) -> set[str]:
    found = [f["rule"] for t in out.get("topics", []) for f in t["findings"]]
    found += [f["rule"] for s in out.get("skills", []) for f in s["findings"]]
    return set(found)


# ── check: topics + claims ────────────────────────────────────────────────────────────────


def test_a_well_formed_topic_and_skill_pass(tmp_path):
    a, b = claim(TEXT_A), claim(TEXT_B)
    write_topic(tmp_path, [a, b])
    write_skill(tmp_path, f"# Setup\n1. Enable WAL [{a['id']}].\n\n## Sources\n{a['id']}\n")
    code, out = check.run(tmp_path, None)
    assert out["findings"] == 0, out
    assert code == 0 and out["topics"][0]["active"] == 2 and len(out["skills"]) == 1


def test_no_topic_is_exit_2(tmp_path):
    code, out = check.run(tmp_path, None)
    assert code == 2 and out["ok"] is False


@pytest.mark.parametrize(
    "mutate, rule",
    [
        (lambda c: c.update(sources=[]), "claim-sources"),
        (lambda c: c["sources"][0].update(url="sqlite.org/wal.html"), "source-url"),
        (lambda c: c["sources"][0].pop("observed_at"), "source-observed-at"),
        (lambda c: c["sources"][0].update(observed_at="yesterday"), "source-observed-at"),
        (lambda c: c.update(id="c-XYZ"), "claim-id"),
        (lambda c: c.update(status="stale"), "claim-status"),
        (lambda c: c.update(status="retired"), "status-reason"),
        (lambda c: c.update(status="retired", reason="gone"), "status-evidence"),
        (lambda c: c.update(status="superseded", reason="new", evidence=[{"url": "https://x.org", "observed_at": NOW}]),
         "superseded-by"),
        (lambda c: c.update(text="WAL is fast."), "durability-short"),
    ],
)
def test_each_provenance_rule_refuses(tmp_path, mutate, rule):
    c = claim(TEXT_A)
    mutate(c)
    write_topic(tmp_path, [c, claim(TEXT_B)])
    code, out = check.run(tmp_path, None)
    assert code == 1 and rule in rules(out), out


def test_an_event_claim_states_its_date(tmp_path):
    write_topic(tmp_path, [claim(TEXT_A)], kind="event")
    assert "durability-undated" in rules(check.run(tmp_path, None)[1])
    write_topic(tmp_path, [claim("As of 2026-10-11, " + TEXT_A)], kind="event")
    assert "durability-undated" not in rules(check.run(tmp_path, None)[1])


def test_a_retired_claim_with_evidence_passes_and_must_leave_the_readme(tmp_path):
    a, b = claim(TEXT_A), claim(TEXT_B)
    b.update(status="retired", reason="unverifiable", evidence=[{"url": "https://sqlite.org/wal.html", "observed_at": NOW}])
    write_topic(tmp_path, [a, b])  # the default README cites active claims only
    assert check.run(tmp_path, None)[1]["findings"] == 0
    write_topic(tmp_path, [a, b], readme=f"# T\nx [{a['id']}] y [{b['id']}]\n")
    assert "readme-inactive-claim" in rules(check.run(tmp_path, None)[1])


def test_readme_citations_are_checked_both_ways(tmp_path):
    a, b = claim(TEXT_A), claim(TEXT_B)
    write_topic(tmp_path, [a, b], readme=f"# T\nonly a [{a['id']}] and a ghost [c-00000000]\n")
    found = rules(check.run(tmp_path, None)[1])
    assert {"readme-unknown-claim", "readme-uncited-claim"} <= found


def test_duplicate_ids_and_a_slug_mismatch_refuse(tmp_path):
    a = claim(TEXT_A)
    d = write_topic(tmp_path, [a, dict(a)])
    meta = json.loads((d / "topic.json").read_text())
    meta["slug"] = "other"
    (d / "topic.json").write_text(json.dumps(meta))
    found = rules(check.run(tmp_path, None)[1])
    assert {"claim-duplicate", "topic-slug"} <= found


# ── check: skills ─────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "body, rule",
    [
        ("Use the Bash tool to run it.\n\n## Sources\n", "claude-only-prose"),
        ("Run `Read(\"x\")` first.\n\n## Sources\n", "claude-tool-call"),
        ("Dispatch Task(subagent_type=x).\n\n## Sources\n", "claude-dispatch"),
        ("See wicked-brain for more.\n\n## Sources\n", "retired-product-ref"),
        ("No sources section here.\n", "skill-sources"),
        ("Cite a ghost [c-00000000].\n\n## Sources\nc-00000000\n", "skill-claim"),
    ],
)
def test_each_skill_rule_refuses(tmp_path, body, rule):
    write_topic(tmp_path, [claim(TEXT_A)])
    write_skill(tmp_path, body)
    assert rule in rules(check.run(tmp_path, None)[1])


def test_a_skill_is_text_only_and_uses_closed_frontmatter(tmp_path):
    write_topic(tmp_path, [claim(TEXT_A)])
    d = write_skill(tmp_path, "x\n\n## Sources\n", extra_fm="allowed-tools: Bash\n")
    (d / "run.sh").write_text("echo hi\n")
    found = rules(check.run(tmp_path, None)[1])
    assert {"skill-not-text", "claude-frontmatter-key"} <= found


def test_a_skill_naming_no_topic_and_a_skill_without_learn_topic(tmp_path):
    write_topic(tmp_path, [claim(TEXT_A)])
    write_skill(tmp_path, "x\n\n## Sources\n", topic="nope")
    other = tmp_path / ".agents" / "skills" / "unrelated"
    other.mkdir(parents=True)
    (other / "SKILL.md").write_text("---\nname: unrelated\ndescription: x\n---\nUse the Bash tool.\n")
    code, out = check.run(tmp_path, None)
    assert "skill-topic" in rules(out)
    assert [s["path"] for s in out["skills"]] == [".agents/skills/sqlite-wal-setup/SKILL.md"]  # unrelated: not ours


def test_the_cross_cli_regexes_equal_gardens_rules_file():
    garden = json.loads((REPO / "tests" / "portability_rules.garden.json").read_text(encoding="utf-8"))["cross_cli"]
    for key, rx in check.CROSS_CLI.items():
        assert rx == garden[key], key
    assert check.DESCRIPTION_MAX == garden["description_max_chars"]
    assert check.SKILL_MAX_BYTES == garden["skill_max_bytes"]
    assert check.SKILL_MAX_LINES == garden["skill_max_lines"]


def test_the_cli_flags(tmp_path):
    env = {k: v for k, v in os.environ.items() if k not in GOVERNED}
    r = subprocess.run([sys.executable, str(SCRIPTS / "check.py"), "--claim-id", TEXT_A], capture_output=True, text=True, env=env)
    assert r.stdout.strip() == claim_id(TEXT_A)
    (tmp_path / "skills").mkdir()
    r = subprocess.run([sys.executable, str(SCRIPTS / "check.py"), "--skill-dir", "--repo", str(tmp_path)],
                       capture_output=True, text=True, env=env)
    assert r.stdout.strip() == "skills"


# ── index ─────────────────────────────────────────────────────────────────────────────────


class FakeEstate:
    def __init__(self, forget: bool = True):
        self.forget = forget
        self.calls: list[tuple[str, dict]] = []

    def list_tools(self):
        return ["knowledge.ingest", "knowledge.recall"] + (["knowledge.forget"] if self.forget else [])

    def call(self, tool, arguments=None, timeout=8.0):
        self.calls.append((tool, arguments))
        if tool == "knowledge.forget":
            return {"deleted_count": 3}
        if tool == "knowledge.ingest":
            return {"content": "ingested"}
        return None


def test_index_replaces_the_topic_scope_with_active_claims_and_sections(tmp_path):
    a, b = claim(TEXT_A), claim(TEXT_B)
    b.update(status="retired", reason="unverifiable", evidence=[{"url": "https://sqlite.org/wal.html", "observed_at": NOW}])
    write_topic(tmp_path, [a, b])
    p = index.topic_payload(tmp_path, "demo", tmp_path / ".wicked" / "knowledge" / "sqlite-wal")
    fake = FakeEstate()
    out = index.index_topic(fake, p)
    assert [t for t, _ in fake.calls] == ["knowledge.ingest"]
    ingest = fake.calls[0][1]
    assert ingest["scope"] == "learn:demo/topic:sqlite-wal" and ingest["source"] == "repo:demo/.wicked/knowledge/sqlite-wal"
    assert ingest["replace_source"] is True and ingest["source_rev"] == p["tree_hash"]
    assert any(a["id"] in c and "https://sqlite.org/wal.html (observed 2026-10-11T04:10:00Z)" in c for c in ingest["chunks"])
    assert not any(b["id"] in c for c in ingest["chunks"]), "a retired claim leaves recall"
    assert out["replace"] == "replaced" and out["ingested"] is True


def test_index_without_erase_uses_a_per_revision_scope(tmp_path):
    write_topic(tmp_path, [claim(TEXT_A)])
    p = index.topic_payload(tmp_path, "demo", tmp_path / ".wicked" / "knowledge" / "sqlite-wal")
    fake = FakeEstate(forget=False)
    out = index.index_topic(fake, p)
    assert out["replace"] == "unavailable"
    assert fake.calls[0][1]["scope"] == f"learn:demo/topic:sqlite-wal/rev:{p['tree_hash']}"
    assert "replace_source" not in fake.calls[0][1], "an estate that cannot replace is never told to"


def test_index_refuses_inside_a_governed_run(tmp_path):
    write_topic(tmp_path, [claim(TEXT_A)])
    env = {k: v for k, v in os.environ.items() if k not in GOVERNED}
    env["WICKED_RUN_ID"] = "r-1"
    r = subprocess.run([sys.executable, str(SCRIPTS / "index.py"), "--repo", str(tmp_path), "--name", "demo"],
                       capture_output=True, text=True, env=env, timeout=60)
    assert r.returncode == 2 and "governed run" in json.loads(r.stdout)["reason"]


def test_index_dry_run_touches_no_store(tmp_path):
    write_topic(tmp_path, [claim(TEXT_A)])
    env = {k: v for k, v in os.environ.items() if k not in GOVERNED}
    r = subprocess.run([sys.executable, str(SCRIPTS / "index.py"), "--repo", str(tmp_path), "--name", "demo", "--dry-run"],
                       capture_output=True, text=True, env=env, timeout=60)
    out = json.loads(r.stdout)
    assert r.returncode == 0 and out["dry_run"] and out["topics"][0]["scope"] == "learn:demo/topic:sqlite-wal"


def test_review_fixes_codex_r1(tmp_path):
    # an empty topic.json and an empty README are findings, not a silent pass
    d = write_topic(tmp_path, [claim(TEXT_A)], readme="")
    (d / "topic.json").write_text("{}")
    found = rules(check.run(tmp_path, None)[1])
    assert {"topic-schema", "topic-slug", "topic-kind", "topic-title", "readme-empty"} <= found
    # a malformed authority is a finding, not a crash
    c = claim(TEXT_A)
    c["sources"][0]["url"] = "https://[invalid"
    write_topic(tmp_path, [c])
    assert "source-url" in rules(check.run(tmp_path, None)[1])
    # invalid UTF-8 is a read error
    (d / "claims.jsonl").write_bytes(b"\xff\xfe\n")
    assert "topic-read" in rules(check.run(tmp_path, None)[1])


def test_index_leaves_a_topic_it_cannot_read_and_skips_malformed_claims(tmp_path):
    d = write_topic(tmp_path, [claim(TEXT_A)])
    (d / "claims.jsonl").write_text("{not json\n")
    fake = FakeEstate()
    out = index.index_topic(fake, index.topic_payload(tmp_path, "demo", d))
    assert fake.calls == [] and out["ingested"] is False
    bad_a, bad_b = claim(TEXT_A), claim(TEXT_B)
    bad_a["text"], bad_b["sources"] = None, 123
    write_topic(tmp_path, [bad_a, bad_b])
    p = index.topic_payload(tmp_path, "demo", d)
    assert p["chunks"] and all("\nSources: " not in c for c in p["chunks"])  # only README sections remain


def test_erasing_one_topic_scope_does_not_name_a_sibling(tmp_path):
    write_topic(tmp_path, [claim(TEXT_A)], slug="sqlite")
    write_topic(tmp_path, [claim(TEXT_A)], slug="sqlite-wal")
    a = index.topic_payload(tmp_path, "demo", tmp_path / ".wicked" / "knowledge" / "sqlite")
    b = index.topic_payload(tmp_path, "demo", tmp_path / ".wicked" / "knowledge" / "sqlite-wal")
    # estate matches a scope prefix by whole kind:id segments; the slug is its own segment
    assert a["scope"] == "learn:demo/topic:sqlite" and b["scope"] == "learn:demo/topic:sqlite-wal"


def test_index_carries_observed_at_and_forgets_an_emptied_topic(tmp_path):
    d = write_topic(tmp_path, [claim(TEXT_A)], refreshed_at="2026-10-11T04:10:00Z")
    fake = FakeEstate()
    index.index_topic(fake, index.topic_payload(tmp_path, "demo", d))
    assert fake.calls[0][1]["observed_at"] == "2026-10-11T04:10:00Z"
    b = claim(TEXT_A, status="retired", reason="gone", evidence=[{"url": "https://sqlite.org/wal.html", "observed_at": NOW}])
    d = write_topic(tmp_path, [b], readme="")
    fake = FakeEstate()
    out = index.index_topic(fake, index.topic_payload(tmp_path, "demo", d))
    assert fake.calls == [("knowledge.forget", {"source": "repo:demo/.wicked/knowledge/sqlite-wal"})]
    assert out["replace"] == "forgotten"


def test_a_failed_forget_of_an_emptied_topic_is_a_failure(tmp_path):
    b = claim(TEXT_A, status="retired", reason="gone", evidence=[{"url": "https://sqlite.org/wal.html", "observed_at": NOW}])
    d = write_topic(tmp_path, [b], readme="")

    class Down(FakeEstate):
        def call(self, tool, arguments=None, timeout=8.0):
            self.calls.append((tool, arguments))
            return None

    out = index.index_topic(Down(), index.topic_payload(tmp_path, "demo", d))
    assert out["replace"] == "forget-failed" and out["ok"] is False
