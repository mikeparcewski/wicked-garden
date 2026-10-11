#!/usr/bin/env python3
"""Check a repository's learned knowledge and learn-authored skills (DES-learn-workflow §2).

    wicked-garden run scripts/learn/check.py [--repo <dir>] [--slug <slug>]

Deterministic, read-only. Prints one JSON object ``{ok, repo, topics: [{slug, claims, active,
findings}], skills: [{path, topic, findings}], findings}`` and exits 0 when there are no findings,
1 when there are, 2 when the repository has no ``.wicked/knowledge/`` topic at all (or ``--slug``
names none). A finding is ``{where, rule, message}``. What it refuses:

- topic.json: not an object, schema != 1, slug != its directory, bad kind, no title;
- claims: bad or duplicate id, empty text, unknown status, no sources, a source without an
  http(s) url or an ISO-8601 ``observed_at``, a non-active claim with no ``reason`` or no
  ``evidence``, ``superseded`` without ``superseded_by``; the mechanical half of the durability test
  (text under 40 characters; an ``event`` topic's claim with no year in its text);
- README.md: a citation of an unknown or non-active claim, an active claim nobody cites;
- skills (``metadata.learn-topic`` names a topic): frontmatter keys outside the closed set, a name
  that is not kebab-case or differs from its directory, a description over 1024 characters, a body
  over 500 lines or 24576 bytes, harness-only prose or tool-call/dispatch shapes (garden's
  cross-CLI lint), a retired product name, any file beside SKILL.md that is not markdown (a learn
  skill is text only), no ``## Sources`` section, a cited claim id that is unknown or non-active.

Standard library only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _knowledge import (  # noqa: E402
    CITATION_RE,
    CLAIM_ID_RE,
    CLAIM_STATUSES,
    ISO_RE,
    SKILL_DIRS,
    SLUG_RE,
    TOPIC_KINDS,
    claim_id,
    read_topic,
    skill_dir,
    topic_dirs,
)
from _skill_meta import CLOSED_KEYS, parse_frontmatter, split_frontmatter  # noqa: E402

# garden's cross-CLI lint (tests/portability_rules.garden.json "cross_cli"), restated because tests/
# does not ship; tests/learn/test_learn_scripts.py pins these equal to the rules file.
CROSS_CLI = {
    "dispatch_regex": r"""(?<!= )(?<!=)(?<!new )(?<!: )(?<!:)\b(?:Task|Agent)\((?=\s*(?:["'`{]|\.\.\.|…|[A-Za-z_][A-Za-z0-9_]*\s*=|[A-Z][A-Za-z]*\s*,|$))|\b(?:Skill|TaskCreate|TaskUpdate|TodoWrite)\((?=\s*(?:["'`{]|\.\.\.|…|[A-Za-z_][A-Za-z0-9_]*\s*=|[A-Z][A-Za-z]*\s*,|$))|\bsubagent_type\b|\bAskUserQuestion\b""",
    "tool_call_regex": r"""\b(?:Read|Write|Edit|MultiEdit|Bash|Glob|Grep|WebFetch|WebSearch|NotebookEdit)\((?=\s*(?:["'`{]|\.\.\.|…|[A-Za-z_][A-Za-z0-9_]*\s*=|[A-Z][A-Za-z]*\s*,|$))""",
    "prose_regex": r"""Claude Code|\.claude/|\b(?:Read|Write|Edit|MultiEdit|Bash|Glob|Grep|WebFetch|WebSearch|NotebookEdit)\s+tool\b|\bthe\s+(?:Task|Skill|Agent)\s+tool\b""",
    "retired_product_regex": r"""\bwicked-(?:testing|brain|signals|loom)\b""",
}
CROSS_CLI_RULES = {
    "dispatch_regex": "claude-dispatch",
    "tool_call_regex": "claude-tool-call",
    "prose_regex": "claude-only-prose",
    "retired_product_regex": "retired-product-ref",
}
DESCRIPTION_MAX = 1024
SKILL_MAX_BYTES = 24576
SKILL_MAX_LINES = 500
CLAIM_MIN_CHARS = 40
YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")


def _f(where: str, rule: str, message: str) -> dict:
    return {"where": where, "rule": rule, "message": message}


def _url_ok(url: object) -> bool:
    if not isinstance(url, str):
        return False
    try:
        p = urlparse(url)
        p.port  # noqa: B018  (raises ValueError on a malformed authority)
    except ValueError:
        return False
    return p.scheme in ("http", "https") and bool(p.netloc)


def check_claim(c: object, n: int, kind: str, where: str) -> list[dict]:
    w = f"{where}#{n}"
    if not isinstance(c, dict):
        return [_f(w, "claim-shape", "a claim is a JSON object")]
    out = []
    cid = c.get("id")
    if not isinstance(cid, str) or not CLAIM_ID_RE.match(cid):
        out.append(_f(w, "claim-id", "id must be c- plus 8 lowercase hex characters"))
    else:
        w = f"{where}#{cid}"
    text = c.get("text")
    status = c.get("status")
    if not isinstance(text, str) or not text.strip():
        out.append(_f(w, "claim-text", "text is empty"))
        text = ""
    if status not in CLAIM_STATUSES:
        out.append(_f(w, "claim-status", f"status must be one of {', '.join(CLAIM_STATUSES)}"))
    sources = c.get("sources")
    if not isinstance(sources, list) or not sources:
        out.append(_f(w, "claim-sources", "a claim needs at least one source"))
    else:
        for i, s in enumerate(sources):
            if not isinstance(s, dict) or not _url_ok(s.get("url")):
                out.append(_f(w, "source-url", f"source {i} needs an http(s) url"))
            if not isinstance(s, dict) or not isinstance(s.get("observed_at"), str) or not ISO_RE.match(s["observed_at"]):
                out.append(_f(w, "source-observed-at", f"source {i} needs an ISO-8601 observed_at (UTC fetch time)"))
    if status in CLAIM_STATUSES and status != "active":
        if not isinstance(c.get("reason"), str) or not c["reason"].strip():
            out.append(_f(w, "status-reason", f"a {status} claim needs a reason"))
        ev = c.get("evidence")
        if not isinstance(ev, list) or not ev or not all(isinstance(e, dict) and _url_ok(e.get("url")) for e in ev):
            out.append(_f(w, "status-evidence", f"a {status} claim needs evidence: [{{url, observed_at}}]"))
        if status == "superseded" and not (isinstance(c.get("superseded_by"), str) and CLAIM_ID_RE.match(c["superseded_by"])):
            out.append(_f(w, "superseded-by", "a superseded claim names the claim that replaces it (superseded_by)"))
    if status == "active" and text:
        if len(text.strip()) < CLAIM_MIN_CHARS:
            out.append(_f(w, "durability-short", f"under {CLAIM_MIN_CHARS} characters: too thin to help a fresh session in 3 months"))
        if kind == "event" and not YEAR_RE.search(text):
            out.append(_f(w, "durability-undated", "an event claim states its date in its text (\"as of <date>\")"))
    return out


def check_topic(d: Path, repo: Path) -> tuple[dict, dict]:
    t = read_topic(d)
    where = str(d.relative_to(repo))
    findings = [_f(where, "topic-read", e) for e in t.errors]
    m = t.meta
    if not any(e.startswith("topic.json") for e in t.errors):  # it parsed: judge every field, {} included
        if m.get("schema") != 1:
            findings.append(_f(f"{where}/topic.json", "topic-schema", "schema must be 1"))
        if m.get("slug") != t.slug or not SLUG_RE.match(t.slug):
            findings.append(_f(f"{where}/topic.json", "topic-slug", "slug is kebab-case and equals its directory name"))
        if m.get("kind") not in TOPIC_KINDS:
            findings.append(_f(f"{where}/topic.json", "topic-kind", "kind is topic or event"))
        if not isinstance(m.get("title"), str) or not m["title"].strip():
            findings.append(_f(f"{where}/topic.json", "topic-title", "title is required"))
    kind = m.get("kind", "topic") if m else "topic"
    seen: dict[str, dict] = {}
    for n, c in enumerate(t.claims, 1):
        findings += check_claim(c, n, kind, f"{where}/claims.jsonl")
        cid = c.get("id") if isinstance(c, dict) else None
        if isinstance(cid, str):
            if cid in seen:
                findings.append(_f(f"{where}/claims.jsonl#{cid}", "claim-duplicate", "duplicate claim id"))
            seen[cid] = c
    active = {cid for cid, c in seen.items() if c.get("status") == "active"}
    if not t.readme.strip() and not any("README.md" in e for e in t.errors):
        findings.append(_f(f"{where}/README.md", "readme-empty", "README.md is empty: it is the synthesis that cites every active claim"))
    if t.readme.strip():
        cited = set(CITATION_RE.findall(t.readme))
        for cid in sorted(cited - set(seen)):
            findings.append(_f(f"{where}/README.md", "readme-unknown-claim", f"cites {cid}, which claims.jsonl does not hold"))
        for cid in sorted((cited & set(seen)) - active):
            findings.append(_f(f"{where}/README.md", "readme-inactive-claim", f"cites {cid}, which is {seen[cid].get('status')}"))
        for cid in sorted(active - cited):
            findings.append(_f(f"{where}/README.md", "readme-uncited-claim", f"active claim {cid} is not cited"))
    summary = {"slug": t.slug, "claims": len(t.claims), "active": len(active), "findings": findings}
    return summary, {cid: c.get("status") for cid, c in seen.items()}


def _skill_files(repo: Path):
    for rel in SKILL_DIRS:
        base = repo / rel
        if base.is_dir():
            yield from sorted(base.glob("*/SKILL.md"))


def check_skill(path: Path, repo: Path, statuses: dict[str, dict]) -> dict | None:
    """Findings for one skill whose ``metadata.learn-topic`` names a topic; ``None`` for other skills."""
    text = path.read_text(encoding="utf-8")
    block, body = split_frontmatter(text)
    fm = parse_frontmatter(block)
    topic = (fm.get("metadata") or {}).get("learn-topic") if isinstance(fm.get("metadata"), dict) else None
    if not topic:
        return None
    where = str(path.relative_to(repo))
    out = []
    for key in sorted(set(fm) - set(CLOSED_KEYS)):
        out.append(_f(where, "claude-frontmatter-key", f"frontmatter key {key!r} is outside the closed set"))
    name = fm.get("name")
    if not isinstance(name, str) or not NAME_RE.match(name) or name != path.parent.name:
        out.append(_f(where, "skill-name", "name is kebab-case and equals the skill's directory name"))
    desc = fm.get("description")
    if not isinstance(desc, str) or not desc.strip():
        out.append(_f(where, "skill-description", "description is required"))
    elif len(desc) > DESCRIPTION_MAX:
        out.append(_f(where, "description-too-long", f"description is {len(desc)} characters (max {DESCRIPTION_MAX})"))
    if len(text.encode("utf-8")) > SKILL_MAX_BYTES or text.count("\n") + 1 > SKILL_MAX_LINES:
        out.append(_f(where, "skill-too-large", f"SKILL.md exceeds {SKILL_MAX_LINES} lines or {SKILL_MAX_BYTES} bytes"))
    for key, rx in CROSS_CLI.items():
        for ln, line in enumerate(body.splitlines(), 1):
            if re.search(rx, line):
                out.append(_f(f"{where}:{ln}", CROSS_CLI_RULES[key], "not portable across agent CLIs: " + line.strip()[:120]))
    for p in sorted(path.parent.rglob("*")):
        if p.is_file() and p != path and p.suffix.lower() != ".md":
            out.append(_f(str(p.relative_to(repo)), "skill-not-text", "a learn skill is text only: no scripts or other files"))
    tstat = statuses.get(topic)
    if tstat is None:
        out.append(_f(where, "skill-topic", f"metadata.learn-topic {topic!r} names no topic under .wicked/knowledge/"))
    if "\n## Sources" not in "\n" + body:
        out.append(_f(where, "skill-sources", "a learn skill ends with a ## Sources section of claim ids"))
    elif tstat is not None:
        for cid in sorted(set(CITATION_RE.findall(body))):
            if tstat.get(cid) != "active":
                out.append(_f(where, "skill-claim", f"cites {cid}, which is {tstat.get(cid) or 'unknown'} in {topic}"))
    return {"path": where, "topic": topic, "findings": out}


def run(repo: Path, slug: str | None) -> tuple[int, dict]:
    dirs = topic_dirs(repo, slug)
    if not dirs:
        return 2, {"ok": False, "repo": str(repo), "reason": "no .wicked/knowledge/<slug>/ topic" + (f" named {slug}" if slug else "")}
    topics, statuses = [], {}
    for d in dirs:
        summary, st = check_topic(d, repo)
        topics.append(summary)
        statuses[d.name] = st
    skills = []
    for p in _skill_files(repo):
        s = check_skill(p, repo, statuses)
        if s is not None and (slug is None or s["topic"] == slug):
            skills.append(s)
    count = sum(len(t["findings"]) for t in topics) + sum(len(s["findings"]) for s in skills)
    return (0 if count == 0 else 1), {"ok": count == 0, "repo": str(repo), "topics": topics, "skills": skills, "findings": count}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--slug")
    parser.add_argument("--claim-id", metavar="TEXT", help="print the id a claim with this text gets, and exit")
    parser.add_argument("--skill-dir", action="store_true", help="print the skill dir learn writes into, and exit")
    args = parser.parse_args(argv)
    if args.claim_id is not None:
        print(claim_id(args.claim_id))
        return 0
    if args.skill_dir:
        print(skill_dir(args.repo.resolve()).as_posix())
        return 0
    code, out = run(args.repo.resolve(), args.slug)
    print(json.dumps(out, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
