"""Shared reader for a repository's learned knowledge (DES-learn-workflow §2).

Layout, under the repository root:

    .wicked/knowledge/<slug>/topic.json    {schema: 1, slug, title, kind: topic|event, questions[], ...}
    .wicked/knowledge/<slug>/claims.jsonl  one claim per line (see CLAIM_STATUSES)
    .wicked/knowledge/<slug>/README.md     the synthesis; every factual sentence cites [c-xxxxxxxx]
    <skill dir>/<name>/SKILL.md            text-only skills with ``metadata.learn-topic: <slug>``

Standard library only.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

KNOWLEDGE_DIR = Path(".wicked") / "knowledge"
# The repository's skill dir, in preference order; the first that exists wins, else the first is created.
SKILL_DIRS = (Path(".agents") / "skills", Path("skills"), Path(".claude") / "skills")
CLAIM_STATUSES = ("active", "superseded", "contradicted", "retired")
TOPIC_KINDS = ("topic", "event")
SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
CLAIM_ID_RE = re.compile(r"^c-[0-9a-f]{8}$")
CITATION_RE = re.compile(r"\[(c-[0-9a-f]{8})\]")
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})$")


def claim_id(text: str) -> str:
    """The stable id of a claim at first sight: ``c-`` + 8 hex of sha256(normalised text)."""
    norm = " ".join(text.lower().split())
    return "c-" + hashlib.sha256(norm.encode("utf-8")).hexdigest()[:8]


@dataclass
class Topic:
    slug: str
    root: Path
    meta: dict = field(default_factory=dict)
    claims: list = field(default_factory=list)
    readme: str = ""
    errors: list = field(default_factory=list)  # read errors (unparseable files), reported by check

    @property
    def active(self) -> list:
        return [c for c in self.claims if isinstance(c, dict) and c.get("status") == "active"]


def topic_dirs(repo: Path, slug: str | None = None) -> list[Path]:
    base = repo / KNOWLEDGE_DIR
    if not base.is_dir():
        return []
    dirs = sorted(p for p in base.iterdir() if p.is_dir())
    return [d for d in dirs if slug is None or d.name == slug]


def read_topic(d: Path) -> Topic:
    t = Topic(slug=d.name, root=d)
    tj = d / "topic.json"
    try:
        t.meta = json.loads(tj.read_text(encoding="utf-8"))
        if not isinstance(t.meta, dict):
            t.errors.append("topic.json is not a JSON object")
            t.meta = {}
    except FileNotFoundError:
        t.errors.append("topic.json is missing")
    except (OSError, ValueError) as e:  # UnicodeDecodeError is a ValueError
        t.errors.append(f"topic.json does not parse: {e}")
    cj = d / "claims.jsonl"
    try:
        for n, line in enumerate(cj.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                t.claims.append(json.loads(line))
            except ValueError as e:
                t.errors.append(f"claims.jsonl line {n} does not parse: {e}")
    except FileNotFoundError:
        t.errors.append("claims.jsonl is missing")
    except (OSError, UnicodeDecodeError) as e:
        t.errors.append(f"claims.jsonl is unreadable: {e}")
    try:
        t.readme = (d / "README.md").read_text(encoding="utf-8")
    except FileNotFoundError:
        t.errors.append("README.md is missing")
    except (OSError, UnicodeDecodeError) as e:
        t.errors.append(f"README.md is unreadable: {e}")
    return t


def skill_dir(repo: Path) -> Path:
    """The skill dir learn writes into: the first existing one, else ``.agents/skills``."""
    for rel in SKILL_DIRS:
        if (repo / rel).is_dir():
            return rel
    return SKILL_DIRS[0]


def tree_hash(d: Path) -> str:
    """A content hash of one topic directory (file names + bytes), for change detection."""
    h = hashlib.sha256()
    for p in sorted(x for x in d.rglob("*") if x.is_file()):
        h.update(str(p.relative_to(d)).encode("utf-8") + b"\0")
        h.update(p.read_bytes() + b"\0")
    return h.hexdigest()[:16]
