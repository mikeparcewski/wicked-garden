#!/usr/bin/env python3
"""estate_memory.py — the mem domain's deterministic backend over wicked-estate.

FOLD-1/2/3 (Phase 5-S7, SKILL-RATIONALIZATION §2.3): the agent surface for
memory + knowledge lives in garden (the `wicked-garden-mem` router and its
fork workers); the ENGINE lives in wicked-estate. This script is the seam
between them: every action maps 1:1 onto an estate MCP tool, reached through
the merged stdio shim (`scripts/_estate_client.py`). DEC-R applies — the
agent reasons (what to store, how to chunk, what an answer means); this
script only moves JSON.

Actions → estate tools
----------------------
  store          → memory.capture      (content, kind, tier, scope, about)
  recall         → memory.recall       (query, scope_prefix — "" = the whole
                                        subtree incl. migrated brain leaves)
  review         → memory.coverage (+ memory.reflect when a scope is given)
  forget         → memory.erase        (kind-guarded scope_prefix — see below)
  maintain       → memory.reflect + memory.coverage (estate consolidates
                                        in-store; this is the user surface)
  capture-batch  → memory.capture xN   (session-teardown writes, FOLD-3)
  ingest         → knowledge.ingest    (title + chunks + scope + source)
  write          → knowledge.write     (single fact / concept)
  sources        → knowledge.recall ∪ memory.recall (cited-answer feed —
                                        knowledge items carry `source`)
  health         → shim health + store liveness probes

Scope conventions (estate migration)
------------------------------------
Memories live under hierarchical `kind:id` scopes (slash-separated segments,
e.g. ``project:wicked-garden`` or ``brain:wicked-garden/doc:<id>`` for
brain-migrated leaves). Recall-everything = ``scope_prefix: ""`` (the root
subtree). `store` defaults its scope to ``project:<cwd-basename>``.

Erase guard
-----------
`memory.erase` deletes every memory under a scope_prefix. To keep one typo'd
call from nuking the store, `forget` requires a scope_prefix containing at
least one ``kind:id`` segment; erasing the root ("" / "*") additionally
requires ``{"confirm_erase_all": true}``.

Fail-open contract
------------------
Estate missing/unreachable is a degrade, not a crash: actions emit
``{"ok": false, "reason": ...}`` and exit 0. Only usage errors exit 1.
Cross-platform: stdlib only; JSON in/out; ``-`` reads args from stdin so long
content never fights shell quoting.

Usage
-----
  python3 scripts/mem/estate_memory.py <action> '<json-args>'
  printf '%s' '<json-args>' | python3 scripts/mem/estate_memory.py <action> -
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _estate_client  # noqa: E402

# Estate memory vocabulary (wicked-estate-memory-core: MemKind / Tier).
KINDS = ("working", "episode", "entity", "fact", "skill", "archive")
TIERS = ("working", "episodic", "semantic", "procedural", "archival")

# Default tier per kind — mirrors the tier each kind naturally lives in
# (fact/entity = distilled knowledge, episode = raw experience, skill =
# reinforced how-to, working/archive = their namesake tiers).
KIND_DEFAULT_TIER = {
    "working": "working",
    "episode": "episodic",
    "entity": "semantic",
    "fact": "semantic",
    "skill": "procedural",
    "archive": "archival",
}

_USAGE = (
    "usage: estate_memory.py "
    "<store|recall|review|forget|maintain|capture-batch|ingest|write|sources|health> "
    "['<json-args>' | -]"
)


def _emit(obj):
    sys.stdout.write(json.dumps(obj))
    sys.stdout.write("\n")


def _fail_open(reason):
    _emit({"ok": False, "reason": reason})
    return 0


def _default_scope():
    """Project-scoped default: ``project:<cwd-basename>`` (a kind:id segment)."""
    try:
        name = Path.cwd().name or "unknown"
    except OSError:
        name = "unknown"
    return f"project:{name}"


# One slash-separated scope segment: non-empty kind, ':', non-empty id.
_SCOPE_SEGMENT_RE = re.compile(r"^[A-Za-z0-9_-]+:[^/]+$")


def _is_kind_id_prefix(scope_prefix):
    """True iff every slash-separated segment is a well-formed ``kind:id``.

    This is the erase guard's shape check — ``":"``, ``"http://x"``, or a
    trailing empty segment must NOT count as a kind-guarded prefix.
    """
    segments = scope_prefix.split("/")
    return bool(segments) and all(_SCOPE_SEGMENT_RE.match(s) for s in segments)


def _parse_budget(args):
    """(token_budget, error) — usage error instead of a ValueError crash."""
    raw = args.get("token_budget", 2000)
    try:
        return int(raw), None
    except (TypeError, ValueError):
        return None, f"token_budget must be an integer, got: {raw!r}"


def _capture_one(item):
    """One memory.capture call. Returns (memory_id | None, error | None)."""
    content = (item.get("content") or "").strip()
    if not content:
        return None, "empty content"
    kind = item.get("kind") or "fact"
    if kind not in KINDS:
        return None, f"unknown kind: {kind} (valid: {', '.join(KINDS)})"
    tier = item.get("tier") or KIND_DEFAULT_TIER[kind]
    if tier not in TIERS:
        return None, f"unknown tier: {tier} (valid: {', '.join(TIERS)})"
    arguments = {
        "content": content,
        "kind": kind,
        "tier": tier,
        "scope": item.get("scope") or _default_scope(),
    }
    about = item.get("about")
    if isinstance(about, list) and about:
        arguments["about"] = [str(a) for a in about]
    payload = _estate_client.call("memory.capture", arguments)
    if isinstance(payload, dict) and payload.get("memory_id"):
        return payload["memory_id"], None
    return None, "estate memory.capture failed (estate unreachable or store rejected the write)"


def do_store(args):
    memory_id, err = _capture_one(args)
    if err:
        return _fail_open(err)
    _emit({"ok": True, "memory_id": memory_id, "scope": args.get("scope") or _default_scope()})
    return 0


def do_recall(args):
    query = (args.get("query") or args.get("_") or "").strip()
    if not query:
        _emit({"error": "recall requires a query"})
        return 1
    if "scope" in args and "scope_prefix" in args:
        _emit({"error": "recall takes scope OR scope_prefix, not both "
                        "(scope = ancestor-visible inheritance; "
                        "scope_prefix = subtree filter)"})
        return 1
    budget, err = _parse_budget(args)
    if err:
        _emit({"error": err})
        return 1
    arguments = {"query": query, "token_budget": budget}
    if "scope" in args:
        # Explicit scope, no prefix: estate's ancestor-visible inheritance.
        arguments["scope"] = args["scope"]
    else:
        # Subtree filter; "" = every memory, incl. migrated brain:*/doc:* leaves.
        arguments["scope_prefix"] = args.get("scope_prefix", "")
    payload = _estate_client.call("memory.recall", arguments)
    items = payload.get("items") if isinstance(payload, dict) else None
    if items is None:
        return _fail_open("estate memory.recall failed")
    _emit({"ok": True, "items": items})
    return 0


def do_review(args):
    scope_prefix = args.get("scope_prefix", "")
    coverage = _estate_client.call("memory.coverage", {"scope_prefix": scope_prefix})
    if not isinstance(coverage, dict):
        return _fail_open("estate memory.coverage failed")
    out = {"ok": True, "coverage": coverage}
    scope = args.get("scope")
    if scope:
        reflect = _estate_client.call("memory.reflect", {"scope": scope})
        if isinstance(reflect, dict):
            out["reflect"] = reflect
    _emit(out)
    return 0


def do_forget(args):
    scope_prefix = args.get("scope_prefix", args.get("_", ""))
    if not isinstance(scope_prefix, str):
        _emit({"error": "forget requires a string scope_prefix"})
        return 1
    scope_prefix = scope_prefix.strip()
    # Kind-guarded erase: every segment a well-formed kind:id, or an
    # explicit erase-all. A bare ":", "http://x", or partial segment is
    # rejected — the guard exists so one malformed call can't nuke subtrees.
    if not _is_kind_id_prefix(scope_prefix):
        if scope_prefix in ("", "*") and args.get("confirm_erase_all") is True:
            scope_prefix = ""
        else:
            _emit({
                "error": "forget requires a well-formed kind:id scope_prefix "
                         '(e.g. "project:wicked-garden" or '
                         '"brain:wicked-garden/doc:abc"). '
                         'To erase EVERYTHING pass {"scope_prefix": "", '
                         '"confirm_erase_all": true}.'
            })
            return 1
    payload = _estate_client.call("memory.erase", {"scope_prefix": scope_prefix})
    if not isinstance(payload, dict) or "deleted_count" not in payload:
        return _fail_open("estate memory.erase failed")
    _emit({"ok": True, "deleted_count": payload["deleted_count"], "scope_prefix": scope_prefix})
    return 0


def do_maintain(args):
    # Estate consolidates in-store (decay/promote/merge live in the engine —
    # consolidate.rs); reflect is the distillation surface, coverage the pulse.
    scope = args.get("scope", "")
    reflect = _estate_client.call("memory.reflect", {"scope": scope})
    if not isinstance(reflect, dict):
        return _fail_open("estate memory.reflect failed")
    out = {"ok": True, "reflect": reflect}
    coverage = _estate_client.call("memory.coverage", {"scope_prefix": scope})
    if isinstance(coverage, dict):
        out["coverage"] = coverage
    _emit(out)
    return 0


def do_capture_batch(args):
    memories = args.get("memories")
    if not isinstance(memories, list) or not memories:
        _emit({"error": 'capture-batch requires {"memories": [{"content": ...}, ...]}'})
        return 1
    stored, failures = [], []
    for i, item in enumerate(memories):
        if not isinstance(item, dict):
            failures.append({"index": i, "reason": "not an object"})
            continue
        memory_id, err = _capture_one(item)
        if err:
            failures.append({"index": i, "reason": err})
        else:
            stored.append({"index": i, "memory_id": memory_id})
    _emit({
        "ok": not failures or bool(stored),
        "stored": len(stored),
        "failed": len(failures),
        "ids": [s["memory_id"] for s in stored],
        "failures": failures,
    })
    return 0


def do_ingest(args):
    title = (args.get("title") or "").strip()
    chunks = args.get("chunks")
    if not title or not isinstance(chunks, list) or not chunks:
        _emit({"error": 'ingest requires {"title": ..., "chunks": [...]} '
                        "(+ scope, source for provenance)"})
        return 1
    arguments = {"title": title, "chunks": [str(c) for c in chunks]}
    arguments["scope"] = args.get("scope") or _default_scope()
    if args.get("source"):
        arguments["source"] = args["source"]
    payload = _estate_client.call("knowledge.ingest", arguments, timeout=30.0)
    if not isinstance(payload, dict) or not payload.get("doc_id"):
        return _fail_open("estate knowledge.ingest failed")
    _emit({"ok": True, "doc_id": payload["doc_id"], "chunks": len(chunks),
           "scope": arguments["scope"], "source": args.get("source")})
    return 0


def do_write(args):
    content = (args.get("content") or "").strip()
    if not content:
        _emit({"error": "write requires content"})
        return 1
    arguments = {"content": content}
    for key in ("class", "scope", "source"):
        if args.get(key):
            arguments[key] = args[key]
    arguments.setdefault("scope", _default_scope())
    payload = _estate_client.call("knowledge.write", arguments)
    if payload is None:
        return _fail_open("estate knowledge.write failed")
    _emit({"ok": True, "result": payload})
    return 0


def do_sources(args):
    """Cited-answer feed: knowledge chunks (each carrying `source`) plus
    memory items (carrying scope/tier/memory_id). The AGENT synthesizes the
    answer from these and cites per claim — estate's cited-answer method card
    (skill://cited-answer/SKILL.md): the engine ranks, it does not write prose.
    """
    query = (args.get("query") or args.get("_") or "").strip()
    if not query:
        _emit({"error": "sources requires a query"})
        return 1
    budget, err = _parse_budget(args)
    if err:
        _emit({"error": err})
        return 1
    knowledge = _estate_client.call("knowledge.recall", {"query": query, "token_budget": budget})
    k_items = knowledge.get("items", []) if isinstance(knowledge, dict) else []
    memory = _estate_client.call(
        "memory.recall",
        {"query": query, "token_budget": budget,
         "scope_prefix": args.get("scope_prefix", "")},
    )
    m_items = memory.get("items", []) if isinstance(memory, dict) else []
    if knowledge is None and memory is None:
        return _fail_open("estate unreachable (knowledge.recall and memory.recall both failed)")
    _emit({"ok": True, "query": query, "knowledge": k_items, "memories": m_items})
    return 0


def do_health(_args):
    reachable = _estate_client.health()
    out = {"ok": reachable, "estate": reachable}
    if reachable:
        coverage = _estate_client.call("memory.coverage", {"scope_prefix": ""})
        out["memory_store"] = isinstance(coverage, dict)
        if isinstance(coverage, dict):
            out["memory_total"] = coverage.get("total")
        k = _estate_client.call("knowledge.coverage", {})
        out["knowledge_store"] = isinstance(k, dict)
    _emit(out)
    return 0


_ACTIONS = {
    "store": do_store,
    "recall": do_recall,
    "review": do_review,
    "forget": do_forget,
    "maintain": do_maintain,
    "capture-batch": do_capture_batch,
    "ingest": do_ingest,
    "write": do_write,
    "sources": do_sources,
    "health": do_health,
}


def main(argv):
    if not argv or argv[0] not in _ACTIONS:
        _emit({"error": _USAGE})
        return 1
    raw = argv[1] if len(argv) > 1 else "{}"
    if raw == "-":
        raw = sys.stdin.read()
    try:
        args = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        # Convenience: a bare positional is the primary string arg.
        args = {"_": raw}
    if not isinstance(args, dict):
        _emit({"error": "json-args must be an object"})
        return 1
    return _ACTIONS[argv[0]](args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
