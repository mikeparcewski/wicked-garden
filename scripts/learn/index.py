#!/usr/bin/env python3
"""Index a repository's learned knowledge into the wicked-estate knowledge store (DES-learn-workflow §4).

    wicked-garden run scripts/learn/index.py --repo <checkout> [--name <repo name>] [--slug <slug>] [--dry-run]

Reads ``.wicked/knowledge/<slug>/`` from the checkout (run it on the default branch: index what was
MERGED, never an open pull request) and, per topic, REPLACES the estate scope ``learn:<repo>/<slug>``:
``knowledge.erase`` of that scope, then one ``knowledge.ingest`` whose chunks are the topic's ACTIVE
claims (each chunk ends with its sources and observed dates) and the README's sections. A retired,
superseded or contradicted claim therefore leaves recall at the next index.

When the estate binary has no ``knowledge.erase`` yet, the topic is ingested under a per-revision
scope ``learn:<repo>/<slug>@<tree hash>`` instead and the output says ``"replace": "unavailable"``
(an older revision stays recallable until estate can erase it).

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


def claim_chunk(c: dict) -> str:
    srcs = "; ".join(f"{s.get('url')} (observed {s.get('observed_at')})" for s in c.get("sources") or [] if isinstance(s, dict))
    return f"{c.get('text', '').strip()} [{c.get('id')}]\nSources: {srcs}"


def readme_sections(readme: str) -> list[str]:
    starts = [m.start() for m in SECTION_RE.finditer(readme)] or [0]
    if starts[0] != 0:
        starts.insert(0, 0)
    parts = [readme[a:b].strip() for a, b in zip(starts, starts[1:] + [len(readme)])]
    return [p for p in parts if p]


def topic_payload(repo: Path, name: str, d: Path) -> dict:
    t = read_topic(d)
    chunks = [claim_chunk(c) for c in t.active] + readme_sections(t.readme)
    return {
        "slug": t.slug,
        "title": (t.meta.get("title") if isinstance(t.meta, dict) else None) or t.slug,
        "scope": f"{SCOPE_PREFIX}{name}/{t.slug}",
        "source": f"repo:{name}/.wicked/knowledge/{t.slug}",
        "chunks": chunks,
        "tree_hash": tree_hash(d),
        "read_errors": t.errors,
    }


def index_topic(client, p: dict) -> dict:
    out = {"slug": p["slug"], "scope": p["scope"], "chunks": len(p["chunks"]), "tree_hash": p["tree_hash"]}
    if p["read_errors"]:
        out["read_errors"] = p["read_errors"]
    erased = client.call("knowledge.erase", {"scope_prefix": p["scope"]}, timeout=30.0)
    if erased is None:
        out["replace"] = "unavailable"
        out["scope"] = f"{p['scope']}@{p['tree_hash']}"
    else:
        out["replace"] = "erased"
        out["erased"] = erased
    if not p["chunks"]:
        out["ingested"] = False
        out["reason"] = "no active claims and no README to index"
        return out
    res = client.call("knowledge.ingest", {"title": p["title"], "chunks": p["chunks"], "scope": out["scope"],
                                           "source": p["source"]}, timeout=60.0)
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
    results = [index_topic(client, p) for p in payloads]
    ok = all(r.get("ingested") or not r["chunks"] for r in results)
    print(json.dumps({"ok": ok, "repo": name, "topics": results}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
