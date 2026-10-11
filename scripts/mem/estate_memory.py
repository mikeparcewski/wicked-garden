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
  recall         → memory.recall       (query; default scope = the current
                                        project + ancestors; scope_prefix is
                                        the explicit opt-in, "" = everything)
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
brain-migrated leaves). `store` and `recall` default to ``project:<cwd-basename>``
(recall adds its ancestors, so root-scoped memories stay visible); other
projects' memories need the explicit opt-in ``scope_prefix: ""``.

Durability gate
---------------
`store` / `capture-batch` refuse only the unambiguous (``durability_rejects``):
an empty or under-40-char body, a bare id / SHA / version, or first-person
progress narration. Ids, versions, SHAs, PIDs and dates inside a body are
advisory ``warnings`` (``durability_warnings``); the store still succeeds.

Erase guard
-----------
`memory.erase` deletes every memory under a scope_prefix. To keep one typo'd
call from nuking the store, `forget` requires a scope_prefix containing at
least one ``kind:id`` segment; erasing the root ("" / "*") additionally
requires ``{"confirm_erase_all": true}``.

Governed / read-only mode (wicked-garden #1130)
------------------------------------------------
Inside a wicked-crew run (a governed-unit marker present — see
`_estate_client.GOVERNED_MARKERS` — or ``--governed`` passed) — or when the
caller passes ``--readonly`` — the shim spawns ``wicked-estate-mcp --readonly`` with the
store pinned from ``--db <path>`` or the worker environment
(``WICKED_ESTATE_DB`` / ``WICKED_HOME`` / ``WICKED_MEMORY_DB``); an unpinned
store in a run is refused (``{"ok": false, "reason": ...}``). The flags ride
THIS script's argv, anywhere on it, and are forwarded to the shim
(`_estate_client.parse_cli_flags`) instead of being dropped — the wicked-core
gate hook allows a backend call only when ``--readonly`` is spelled on it and
the store is pinned (core #471). Under ``--readonly`` every write action
(store / capture-batch / ingest / write / forget) is refused by the MCP
itself; recall / review / sources / health keep working.

Fail-open contract
------------------
Estate missing/unreachable is a degrade, not a crash: actions emit
``{"ok": false, "reason": ...}`` and exit 0. Only usage errors exit 1
(including an unknown ``--flag``: a misspelt ``--read-only`` must never pass
through silently — the MCP would run write-capable).
Cross-platform: stdlib only; JSON in/out; ``-`` reads args from stdin so long
content never fights shell quoting.

Usage
-----
  python3 scripts/mem/estate_memory.py [--readonly] [--governed] [--db <path>] <action> '<json-args>'
  printf '%s' '<json-args>' | python3 scripts/mem/estate_memory.py <action> -
"""

import json
import os
import re
import sys
import time
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
    "usage: estate_memory.py [--readonly] [--governed] [--db <path>] "
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
    return _estate_client.project_scope()


def _default_intent():
    """The session intent faceted memories are admitted against (estate `intent`).

    Estate hides a faceted memory unless the intent carries every facet it
    names, and repo-learn files memories under ``{repo, project}``. Derived
    from the enclosing git checkout: ``repo`` = its directory name, ``project``
    = the run's `WICKED_RUN_PROJECT`, else the checkout's parent directory
    (the umbrella, e.g. ``wicked`` for ``wicked/wicked-estate``). Outside a git
    checkout: {} (unfaceted memories only, as before).
    """
    root = _estate_client.checkout_root()
    if root is None:
        return {}
    project = (os.environ.get("WICKED_RUN_PROJECT") or "").strip() or root.parent.name
    return {k: v for k, v in (("repo", root.name), ("project", project)) if v}


def _memory_recall_args(args, query, budget):
    """memory.recall arguments shared by recall and sources (scope, prefix, intent)."""
    m_args = {"query": query, "token_budget": budget}
    if "scope_prefix" in args:
        m_args["scope_prefix"] = args["scope_prefix"]  # explicit opt-in subtree
    else:
        m_args["scope"] = args.get("scope") or _default_scope()  # project + ancestors
    intent = args["intent"] if "intent" in args else _default_intent()
    if intent:
        m_args["intent"] = intent
    return m_args


def _date(ts):
    try:
        return time.strftime("%Y-%m-%d", time.gmtime(int(ts))) if int(ts) > 0 else "undated"
    except (TypeError, ValueError):
        return "undated"


def memory_label(item):
    """`[memory · <kind> · <captured date> · <scope>]` for an answer citation."""
    kind = item.get("kind") or item.get("tier") or "memory"
    return f"memory · {kind} · {_date(item.get('created_at'))} · {item.get('scope') or 'root'}"


def knowledge_label(item):
    """`[knowledge · src <source>]` for an answer citation (observed date once estate has it)."""
    observed = item.get("observed_at")
    tail = f" · observed {_date(observed)}" if observed else ""
    return f"knowledge · src {item.get('source') or 'unknown'}{tail}"


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


# ── durability gate ─────────────────────────────────────────────────────────
# A memory must help a fresh session on a different task months from now: it
# states a rule, why it holds, and when it applies. That judgment is the
# agent's (the skill text asks it). The backend refuses only what is
# unambiguous, and WARNS on the rest: an id, version or SHA inside a real rule
# ("keep SQLite >= 3.35.0 because RETURNING", "CRC32 polynomial edb88320") is
# fine, so those heuristics never block a store.
MIN_CONTENT_CHARS = 40
# First-person progress narration: "I'll retry", "I'm going to guess again", "We shipped …".
_NARRATION = re.compile(
    r"\b(?:i['\u2019]ll|i will|we['\u2019]ll|let me"
    r"|(?:i['\u2019]m|i am|we['\u2019]re|we are) (?:going|about) to)\b"
    r"|^(?:i|we)(?: just| finally)? (?:shipped|released|merged|pushed|deployed|landed|tried|retried"
    r"|restarted|bumped|tagged)\b", re.I)
# One identifier on its own: a SHA, a version, a uuid, a #123 / repo#123.
_ID_TOKEN = (r"(?:[0-9a-f]{7,40}|v?\d+\.\d+\.\d+(?:[-+][0-9a-z.]+)?"
             r"|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[a-z][\w.-]*#\d+|#\d+)")
_BARE_ID = re.compile(r"^[\W_]*" + _ID_TOKEN + r"[\W_]*$", re.I)
_ADVISORIES = (
    (re.compile(r"\b(?=[0-9a-f]*\d)(?=[0-9a-f]*[a-f])[0-9a-f]{7,40}\b", re.I), "a commit SHA?"),
    (re.compile(r"(?<![\w.])v?\d+\.\d+\.\d+(?![.\d])"), "a version?"),
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I),
     "a run/session id?"),
    (re.compile(r"\b(?:pr|pull request|issue|run|job)\s*(?:#\s*\d+|\d{5,})\b"
                r"|\b[a-z][\w.-]*#\d+\b|(?<![\w&])#\d+\b", re.I), "a PR/issue/run id?"),
    (re.compile(r"\bpids?\s*[:=#]?\s*\d{3,}\b", re.I), "a process id?"),
    (re.compile(r"\b(?:today|yesterday|tonight|this (?:morning|afternoon|evening|week))\b", re.I),
     "a date-relative word?"),
)


def durability_rejects(content):
    """Hard refusals ([] = it may be stored): an empty or under-40-char body, a
    body that is only an id / SHA / version, or first-person progress narration.
    """
    text = (content or "").strip()
    if len(text) < MIN_CONTENT_CHARS:
        return [f"too short to state a rule, why it holds and when it applies "
                f"(< {MIN_CONTENT_CHARS} chars)"]
    if _BARE_ID.match(text):
        return ["only an identifier (a SHA, version or id), not a learning"]
    if _NARRATION.search(text):
        return ["first-person progress narration (what was done or will be done)"]
    return []


def durability_warnings(content):
    """Advisory only: ids, versions, SHAs, PIDs or dates that MAY mark a moment
    rather than a rule. The store still succeeds; the agent re-checks the
    three-month test and keeps the memory if it holds.
    """
    text = (content or "").strip()
    return [why for rx, why in _ADVISORIES if rx.search(text)]


def _capture_one(item):
    """One memory.capture call. Returns (memory_id | None, error | None)."""
    content = (item.get("content") or "").strip()
    if not content:
        return None, "empty content"
    if item.get("source"):
        # Provenance test (DES-memory-vs-knowledge): memory is told, witnessed or decided;
        # a claim whose evidence is a source artifact is acquired, i.e. knowledge.
        return None, ("acquired from a source, so it is knowledge, not memory: use the `write` "
                      'action ({"content": ..., "class": "concept", "source": ...}) or `ingest`')
    rejects = durability_rejects(content)
    if rejects:
        return None, ("not a durable learning (" + "; ".join(rejects) + "): state the rule, "
                      "why it holds and when it applies")
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
    out = {"ok": True, "memory_id": memory_id, "scope": args.get("scope") or _default_scope()}
    warnings = durability_warnings(args.get("content"))
    if warnings:
        out["warnings"] = warnings
    _emit(out)
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
    if "intent" in args and not isinstance(args["intent"], dict):
        _emit({"error": "intent must be an object of facet axis -> value"})
        return 1
    arguments = _memory_recall_args(args, query, budget)
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
            entry = {"index": i, "memory_id": memory_id}
            warnings = durability_warnings(item.get("content"))
            if warnings:
                entry["warnings"] = warnings
            stored.append(entry)
    _emit({
        "ok": not failures or bool(stored),
        "stored": len(stored),
        "failed": len(failures),
        "ids": [s["memory_id"] for s in stored],
        "warnings": [s for s in stored if s.get("warnings")],
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
    if "intent" in args and not isinstance(args["intent"], dict):
        _emit({"error": "intent must be an object of facet axis -> value"})
        return 1
    memory = _estate_client.call("memory.recall", _memory_recall_args(args, query, budget))
    m_items = memory.get("items", []) if isinstance(memory, dict) else []
    if knowledge is None and memory is None:
        return _fail_open("estate unreachable (knowledge.recall and memory.recall both failed)")
    # Every item says which side it is from and how old it is (DES-memory-vs-knowledge §4).
    k_items = [dict(i, label=knowledge_label(i)) for i in k_items if isinstance(i, dict)]
    m_items = [dict(i, label=memory_label(i)) for i in m_items if isinstance(i, dict)]
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
    # The shim's own flags (--readonly, --db <path>) may sit anywhere on argv;
    # they are applied to the shim and stripped here — never dropped, never
    # mistaken for the action or the JSON positional (garden #1130).
    try:
        argv = _estate_client.parse_cli_flags(list(argv))
    except ValueError as exc:
        _emit({"error": f"{exc}; {_USAGE}"})
        return 1
    if not argv or argv[0] not in _ACTIONS:
        _emit({"error": _USAGE})
        return 1
    refusal = _estate_client.governed_refusal()
    if refusal:
        return _fail_open(refusal)
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
