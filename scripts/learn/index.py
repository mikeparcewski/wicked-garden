#!/usr/bin/env python3
"""Index a repository's learned knowledge into the wicked-estate knowledge store (DES-learn-workflow §4).

    wicked-garden run scripts/learn/index.py --repo <checkout> [--name <repo name>] [--slug <slug>] [--dry-run]

Reads ``.wicked/knowledge/<slug>/`` from the checkout (run it on the default branch: index what was
MERGED, never an open pull request) and, per topic, REPLACES its knowledge in estate: one
``knowledge.ingest {replace_source: true}`` (source ``repo:<repo>/.wicked/knowledge/<slug>``, scope
``learn:<repo>/topic:<slug>``, ``observed_at`` = the topic's refreshed_at, ``source_rev`` = its tree hash)
whose chunks are the topic's ACTIVE claims (each chunk ends with its sources and observed dates) and the
README's sections. A retired, superseded or contradicted claim therefore leaves recall at the next
index; a topic with nothing left is forgotten by its source (``knowledge.forget``).

When estate does not advertise ``knowledge.forget`` (before estate K1+K2), the topic is ingested under a
per-revision scope ``learn:<repo>/topic:<slug>/rev:<tree hash>`` instead and the output says
``"replace": "unavailable"`` (an older revision stays recallable until estate can replace it).

Never from inside a governed run: a run's estate is read-only, and learned knowledge reaches the
store only after its pull request merged. Prints one JSON object ``{ok, repo, topics: [{slug, scope,
chunks, replace, tree_hash, ingested}]}``. Exit 0 indexed (or nothing to index), 1 when estate refused
or was unreachable for a topic, 2 on a usage error or a governed run. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _knowledge import read_topic, topic_dirs, tree_hash  # noqa: E402

SECTION_RE = re.compile(r"^#{1,3} ", re.M)
SCOPE_PREFIX = "learn:"


def repo_name(repo: Path) -> str:
    """The repository's name: its origin remote's last path segment, else the directory name."""
    try:
        url = subprocess.run(["git", "-C", str(repo), "remote", "get-url", "origin"], capture_output=True,
                             text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        url = ""
    name = url.rstrip("/").rsplit("/", 1)[-1].rsplit(":", 1)[-1] if url else repo.name
    return name[:-4] if name.endswith(".git") else name


def claim_chunk(c: dict) -> str | None:
    """One active claim as a recall chunk, or ``None`` for a claim too malformed to index."""
    text, sources = c.get("text"), c.get("sources")
    if not isinstance(text, str) or not text.strip() or not isinstance(sources, list):
        return None
    srcs = "; ".join(f"{s.get('url')} (observed {s.get('observed_at')})" for s in sources if isinstance(s, dict))
    return f"{text.strip()} [{c.get('id')}]\nSources: {srcs}"


def readme_sections(readme: str) -> list[str]:
    starts = [m.start() for m in SECTION_RE.finditer(readme)] or [0]
    if starts[0] != 0:
        starts.insert(0, 0)
    parts = [readme[a:b].strip() for a, b in zip(starts, starts[1:] + [len(readme)])]
    return [p for p in parts if p]


def topic_payload(repo: Path, name: str, d: Path) -> dict:
    t = read_topic(d)
    chunks = [x for x in (claim_chunk(c) for c in t.active) if x is not None] + readme_sections(t.readme)
    return {
        "slug": t.slug,
        "title": (t.meta.get("title") if isinstance(t.meta, dict) else None) or t.slug,
        # Every scope segment is kind:id (estate Scope), and a prefix matches whole segments, so
        # erasing topic:sqlite never touches topic:sqlite-wal.
        "scope": f"{SCOPE_PREFIX}{name}/topic:{t.slug}",
        "source": f"repo:{name}/.wicked/knowledge/{t.slug}",
        "chunks": chunks,
        "tree_hash": tree_hash(d),
        # when the topic was last researched (topic.json refreshed_at, else created_at)
        "observed_at": (t.meta.get("refreshed_at") or t.meta.get("created_at")) if isinstance(t.meta, dict) else None,
        "read_errors": t.errors,
    }


def index_topic(client, p: dict, tools: list | None = None) -> dict:
    """Replace one topic in estate. With ``knowledge.forget`` advertised (estate K1+K2), the topic's
    source is replaced in place (``knowledge.ingest {replace_source: true}``, carrying ``observed_at``
    and ``source_rev``), and a topic with nothing left to index is forgotten by its source. Without
    it, the topic is ingested under a per-revision scope and the output says so."""
    out = {"slug": p["slug"], "scope": p["scope"], "chunks": len(p["chunks"]), "tree_hash": p["tree_hash"]}
    if p["read_errors"]:
        out["read_errors"] = p["read_errors"]
        out["ingested"] = False
        out["reason"] = "the topic could not be fully read; its indexed knowledge is left as it was"
        return out
    replace = "knowledge.forget" in (tools if tools is not None else client.list_tools())
    if not p["chunks"]:
        out["ingested"] = False
        out["reason"] = "no active claims and no README to index"
        if replace:
            forgotten = client.call("knowledge.forget", {"source": p["source"]}, timeout=30.0)
            out["replace"] = "forgotten" if forgotten is not None else "forget-failed"
            out["forgotten"] = forgotten
            out["ok"] = forgotten is not None
        return out
    args = {"title": p["title"], "chunks": p["chunks"], "source": p["source"]}
    if replace:
        out["replace"] = "replaced"
        args.update(scope=p["scope"], replace_source=True, source_rev=p["tree_hash"])
        if p.get("observed_at"):
            args["observed_at"] = p["observed_at"]
    else:
        out["replace"] = "unavailable"
        out["scope"] = f"{p['scope']}/rev:{p['tree_hash']}"
        args["scope"] = out["scope"]
    res = client.call("knowledge.ingest", args, timeout=60.0)
    out["ingested"] = res is not None
    if res is None:
        out["reason"] = "estate knowledge.ingest failed or estate is unreachable"
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--name", help="the repository name in the scope (default: origin's name, else the directory)")
    parser.add_argument("--slug")
    parser.add_argument("--dry-run", action="store_true", help="print what would be indexed; touch no store")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    import _estate_client as client  # noqa: E402  (scripts/ is on sys.path)

    if client.is_governed() and not args.dry_run:
        print(json.dumps({"ok": False, "reason": "refusing inside a governed run: a run's estate is read-only, and "
                          "learned knowledge is indexed from the merged default branch (DES-learn-workflow §4.2)"}))
        return 2
    name = args.name or repo_name(repo)
    payloads = [topic_payload(repo, name, d) for d in topic_dirs(repo, args.slug)]
    if args.dry_run:
        print(json.dumps({"ok": True, "repo": name, "dry_run": True,
                          "topics": [{k: v for k, v in p.items() if k != "chunks"} | {"chunks": len(p["chunks"])} for p in payloads]}, indent=2))
        return 0
    tools = client.list_tools()
    results = [index_topic(client, p, tools) for p in payloads]
    ok = all(r.get("ingested") or (not r["chunks"] and "read_errors" not in r and r.get("ok", True)) for r in results)
    print(json.dumps({"ok": ok, "repo": name, "topics": results}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
