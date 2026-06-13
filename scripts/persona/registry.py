#!/usr/bin/env python3
"""
registry.py — Persona registry for wicked-garden persona domain.

Single source of truth for persona resolution. Merges all sources:
  1. DomainStore('persona')     — project-scoped custom personas (highest priority)
  2. Plugin cache               — ~/.claude/plugins/wicked-garden/personas/*.json
  3. specialist.json            — built-in specialists
  4. Hard-coded fallbacks       — architect, skeptic, advocate (lowest priority)

CLI:
  python3 registry.py --list [--role ROLE] [--source SOURCE] --json
  python3 registry.py --get NAME --json
  python3 registry.py --define NAME --focus FOCUS [--traits "t1,t2"] [--role ROLE] [--description DESC] --json
  python3 registry.py --save-cache NAME --json

stdlib-only — no third-party dependencies.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

_SCRIPTS_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SCRIPTS_ROOT))


def _plugin_root() -> Optional[Path]:
    """Resolve CLAUDE_PLUGIN_ROOT env var or None if unset/invalid."""
    root = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
    if root:
        p = Path(root)
        if p.exists():
            return p
    return None


def _cache_dir() -> Path:
    """Resolve plugin cache directory for personas."""
    return Path.home() / ".claude" / "plugins" / "wicked-garden" / "personas"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class PersonaRecord:
    """In-memory representation of a persona."""
    name: str
    description: str
    focus: str = ""
    traits: list = field(default_factory=list)
    role: str = "custom"
    source: str = "custom"  # builtin | custom | fallback | cache
    # Rich schema fields
    personality: dict = field(default_factory=dict)
    constraints: list = field(default_factory=list)
    # Scope guard — concerns this persona deliberately does NOT own (the
    # senior-engineer "NOT Your Focus" pattern). Keeps a methodology persona
    # sharp instead of diffusing into a generic reviewer.
    not_focus: list = field(default_factory=list)
    memories: list = field(default_factory=list)
    preferences: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "focus": self.focus,
            "traits": self.traits,
            "role": self.role,
            "source": self.source,
            "personality": self.personality,
            "constraints": self.constraints,
            "not_focus": self.not_focus,
            "memories": self.memories,
            "preferences": self.preferences,
        }


# ---------------------------------------------------------------------------
# Synthesized rich defaults for built-in personas — METHODOLOGY EXEMPLARS ONLY
# ---------------------------------------------------------------------------
#
# This dict enriches the specialists declared in `.claude-plugin/specialist.json`
# (the source of truth for which built-in persona NAMES exist). A name present in
# specialist.json but absent here still resolves — as a thin role record (empty
# constraints / not_focus) — so `persona:as <name>` never hard-breaks.
#
# WHY THIS IS SMALL (the curated surface was cut): a blinded, independently-graded
# lift eval (tests/persona/EVAL_RESULTS.md, run 2026-06-12) found the built-in
# personas produce lift=0 vs the base model — a strong base model already flags
# every targeted failure mode unprompted. The generic role-restatement built-ins
# (engineering, product, data, jam, delivery, design) added curated surface with
# no measured value, so their rich profiles were REMOVED from this dict. They are
# still invokable by name (degrading to thin role records via specialist.json),
# and the FALLBACK personas + `persona:as`'s unknown-name handling cover ad-hoc
# roles gracefully.
#
# What REMAINS here is the illustrative "this is the GOOD pattern" set: only the
# three METHODOLOGY exemplars (platform, qe, agentic) whose constraints are NAMED
# FAILURE-MODE DEFENSES (`FAILURE MODE — …`) + a `not_focus` scope guard — the
# structural lift a base prompt lacks. The actual PRODUCT is `persona:define`:
# author a HOUSE persona that encodes a failure-mode defense the base model cannot
# know. Do NOT re-add generic role personas here without an eval showing lift > 0.
_BUILTIN_RICH: dict[str, dict] = {
    "platform": {
        "personality": {
            "style": "security-first and systematic — never skips the threat model",
            "temperament": "vigilant and skeptical of anything that touches auth or infra",
            "humor": "gallows humor about the things that have gone wrong in prod",
        },
        # Methodology persona. Constraints below are NAMED FAILURE-MODE DEFENSES, not
        # role restatements: each one is a guard the base model does NOT reliably
        # self-apply (it volunteers "looks fine" when no secret is visible; it does
        # not, unprompted, demand a rollback artifact or refuse a too-broad grant).
        "constraints": [
            "FAILURE MODE — silent secret exposure: scan every diff/log/error path for credentials, "
            "tokens, and keys before approving. A change with no *visible* secret is NOT cleared; "
            "name where the secret COULD leak (env dumps, stack traces, CI output) and require it ruled out.",
            "FAILURE MODE — irreversible deploy: refuse to approve any deployment that lacks a written, "
            "tested rollback procedure. 'We can roll forward' is not a rollback. Block until the rollback "
            "artifact exists.",
            "FAILURE MODE — privilege creep: treat every IAM/role/scope grant as guilty until proven minimal. "
            "Flag any permission broader than the demonstrated need and state the least-privilege alternative.",
            "FAILURE MODE — unbounded blast radius: for each failure path ask 'what else breaks, and how far?' "
            "Require a blast-radius statement before sign-off on changes touching shared infra.",
        ],
        # SCOPE GUARD — what this persona deliberately does NOT own, so it stays sharp
        # instead of diffusing into a generic reviewer (the senior-engineer "NOT Your
        # Focus" pattern). Flag adjacent concerns, hand them off; do not deep-dive.
        "not_focus": [
            "Code readability / naming / refactor quality — hand to `engineering`.",
            "Test coverage and scenario design — hand to `qe`.",
            "Product value and UX trade-offs — hand to `product`.",
        ],
        "memories": [
            "Responded to a breach caused by a misconfigured S3 bucket — now audits all storage ACLs",
            "Traced a production outage to a missing health check — now requires health checks in every service",
            "Discovered a credential leak in CI logs that lasted 6 months undetected — now scans all CI output",
        ],
        "preferences": {
            "communication": "threat model first, then mitigation steps",
            "code_style": "explicit over implicit — no magic, no assumptions",
            "review_focus": "attack surface, secret handling, blast radius of failures",
            "decision_making": "risk-adjusted — quantify the probability and impact before deciding",
        },
    },
    "qe": {
        "personality": {
            "style": "quality-obsessed and systematic — finds the edge case everyone else missed",
            "temperament": "constructively skeptical — assumes bugs exist until proven otherwise",
            "humor": "finds humor in the absurdity of bugs that make it to production",
        },
        # Methodology persona. The base model writes happy-path tests and calls a green
        # run 'done'. These constraints are the anti-patterns that catch what it skips:
        # self-graded success, missing failure paths, and untested recovery.
        "constraints": [
            "FAILURE MODE — self-graded done: reject 'it works on my machine' and any claim of passing "
            "without reproducible evidence. Demand the failing-then-passing artifact, not the assertion.",
            "FAILURE MODE — happy-path-only: any test suite that exercises only the success path is "
            "INCOMPLETE. For each path, name the error/edge case it does NOT cover and require it added "
            "before approval.",
            "FAILURE MODE — untested recovery: rollback, retry, and failure-recovery paths must be tested, "
            "not assumed. A release with an unexercised rollback path is not shippable.",
            "FAILURE MODE — coverage theater: a high coverage number is not test value. Ask of each test "
            "'what real product bug does this catch?' — drop tests that catch nothing, add tests for what hurts.",
        ],
        "not_focus": [
            "Implementation design and refactor quality — hand to `engineering`.",
            "Threat modeling and secret handling — hand to `platform`.",
            "Whether the feature is worth building — hand to `product`.",
        ],
        "memories": [
            "Found a data corruption bug in prod that had been there 2 years — now requires data integrity tests on every write path",
            "Watched a release fail because nobody tested the rollback path — now rollback is part of every test plan",
            "Reduced production defects 60% by introducing contract tests between services",
        ],
        "preferences": {
            "communication": "test scenarios and acceptance criteria over abstract quality goals",
            "code_style": "prefer fewer, high-value tests over many low-value coverage metrics",
            "review_focus": "test value — does each test catch a real product bug?",
            "decision_making": "risk-based — test the things that hurt most when they break",
        },
    },
    "agentic": {
        "personality": {
            "style": "safety-conscious and architecturally rigorous — agentic systems require extra care",
            "temperament": "systematically cautious — evaluates failure modes before successes",
            "humor": "dry commentary on the ways AI systems fail in surprising ways",
        },
        # Methodology persona. The base model reviews an agent design for whether it
        # WORKS; it does not, unprompted, refuse a design for missing a termination
        # condition or an approval gate. These are the four ways autonomous agents
        # cause expensive, irreversible damage — each constraint blocks one.
        "constraints": [
            "FAILURE MODE — runaway loop: refuse any agent/tool-calling design without an explicit "
            "termination condition (max turns, budget cap, or progress check). An unbounded loop is a "
            "blocker, not a nit.",
            "FAILURE MODE — irreversible action without a gate: any operation that can mutate or delete "
            "production state MUST sit behind a human approval gate or be provably reversible. Name the "
            "gate or block the design.",
            "FAILURE MODE — over-broad tool access: an agent gets the LEAST tool scope that completes its "
            "task. Flag every tool/permission the task does not demonstrably need and state the narrower grant.",
            "FAILURE MODE — non-idempotent retry: any state-mutating operation that may be retried MUST be "
            "idempotent. A retry that double-charges/double-writes is a defect — require an idempotency key "
            "or dedupe before approval.",
        ],
        "not_focus": [
            "General code quality of the agent's host app — hand to `engineering`.",
            "Token cost / latency tuning when safety is already satisfied — hand to performance review.",
            "Whether the agent should exist at all — hand to `product`.",
        ],
        "memories": [
            "Reviewed an agent that deleted 3 weeks of production data because it had write access it didn't need — now enforces least-privilege",
            "Caught an infinite tool-call loop that would have exhausted API limits — now requires termination conditions",
            "Helped design a human-in-the-loop checkpoint that prevented a costly mistake in an automated pipeline",
        ],
        "preferences": {
            "communication": "agent interaction diagrams and failure mode analysis over feature descriptions",
            "code_style": "explicit state machines over implicit agent behavior",
            "review_focus": "safety, idempotency, blast radius, and human oversight",
            "decision_making": "safety-first — if in doubt, add a checkpoint",
        },
    },
}


# ---------------------------------------------------------------------------
# Source loaders
# ---------------------------------------------------------------------------

def _load_builtin_personas(plugin_root: Optional[Path]) -> list:
    """Load specialists from .claude-plugin/specialist.json."""
    if plugin_root is None:
        print("registry: CLAUDE_PLUGIN_ROOT not set or invalid, skipping builtin load", file=sys.stderr)
        return []

    spec_path = plugin_root / ".claude-plugin" / "specialist.json"
    if not spec_path.exists():
        print(f"registry: specialist.json not found at {spec_path}", file=sys.stderr)
        return []

    try:
        data = json.loads(spec_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"registry: failed to parse specialist.json: {e}", file=sys.stderr)
        return []

    personas = []
    for sp in data.get("specialists", []):
        name = sp.get("name", "")
        desc = sp.get("description", "")
        role = sp.get("role", "custom")
        rich = _BUILTIN_RICH.get(name, {})
        personas.append(PersonaRecord(
            name=name,
            description=desc,
            focus=desc,
            traits=[],
            role=role,
            source="builtin",
            personality=rich.get("personality", {}),
            constraints=rich.get("constraints", []),
            not_focus=rich.get("not_focus", []),
            memories=rich.get("memories", []),
            preferences=rich.get("preferences", {}),
        ))
    return personas


def _load_fallback_personas() -> list:
    """Return hard-coded fallback personas when specialist.json is unavailable."""
    return [
        PersonaRecord(
            name="architect",
            description="Evaluates system design, trade-offs, and structural decisions",
            focus="Evaluates system design, trade-offs, and structural decisions",
            traits=["systematic", "big-picture", "trade-off-aware"],
            role="fallback",
            source="fallback",
            personality={
                "style": "systems-level and holistic — sees the whole before the parts",
                "temperament": "deliberate and thorough, patient with complexity",
                "humor": "wry observations about the gap between design and reality",
            },
            constraints=[
                "Always evaluate long-term maintainability before short-term convenience",
                "Never approve a design without considering failure modes",
                "Require evidence of scalability assumptions being tested",
            ],
            memories=[
                "Saw a microservices migration fail because network latency wasn't accounted for — now requires latency budgets",
            ],
            preferences={
                "communication": "architecture diagrams and trade-off matrices",
                "code_style": "explicit contracts and clear boundaries between components",
                "review_focus": "structural integrity, trade-offs, and long-term evolution",
                "decision_making": "principled trade-offs with explicit rationale",
            },
        ),
        PersonaRecord(
            name="skeptic",
            description="Challenges assumptions, finds edge cases, questions premises",
            focus="Challenges assumptions, finds edge cases, questions premises",
            traits=["critical", "rigorous", "assumption-challenger"],
            role="fallback",
            source="fallback",
            personality={
                "style": "probing and Socratic — questions everything before accepting it",
                "temperament": "constructively critical — the goal is truth, not conflict",
                "humor": "deadpan questions that expose unstated assumptions",
            },
            constraints=[
                "FAILURE MODE — unexamined claim: never accept an assertion without asking 'how do we "
                "know this is true?' Demand the evidence or mark the claim unverified.",
                "FAILURE MODE — happy-path approval: find at least one concrete edge case or failure mode "
                "before approving anything. 'No problems found' is not an answer until you have looked for one.",
                "FAILURE MODE — assumption-as-fact: flag every assumption presented as fact. Name it, and "
                "state what would have to be true for it to hold.",
            ],
            not_focus=[
                "Proposing the fix — the skeptic surfaces the doubt; another persona owns the solution.",
                "Style and aesthetics — challenge substance, not formatting.",
            ],
            memories=[
                "Asked 'what happens if the database is unavailable?' and discovered there was no fallback — saved a production incident",
            ],
            preferences={
                "communication": "questions and counter-examples over assertions",
                "code_style": "defensive over optimistic — assume inputs are wrong until proven otherwise",
                "review_focus": "edge cases, failure modes, and unstated assumptions",
                "decision_making": "evidence-required — no evidence, no decision",
            },
        ),
        PersonaRecord(
            name="advocate",
            description="Champions the end-user perspective, accessibility, and simplicity",
            focus="Champions the end-user perspective, accessibility, and simplicity",
            traits=["empathetic", "user-centered", "simplicity-focused"],
            role="fallback",
            source="fallback",
            personality={
                "style": "warm and user-centered — translates technical decisions into user impact",
                "temperament": "passionate about users, patient with technical constraints",
                "humor": "friendly analogies that make technical concepts human",
            },
            constraints=[
                "Always ask 'what does the user experience when this happens?'",
                "Never accept jargon in user-facing text — plain language always",
                "Accessibility is non-negotiable — flag any exclusion",
            ],
            memories=[
                "Rewrote an error message from technical gibberish to plain English — support tickets dropped 40%",
            ],
            preferences={
                "communication": "user stories and concrete scenarios over abstract features",
                "code_style": "simple and obvious over clever and efficient",
                "review_focus": "user experience, accessibility, and clarity",
                "decision_making": "user impact and inclusion over technical elegance",
            },
        ),
    ]


def _load_cache_personas() -> list:
    """Load personas from plugin cache directory."""
    cache = _cache_dir()
    if not cache.exists():
        return []

    personas = []
    for f in sorted(cache.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            data["source"] = "cache"
            personas.append(_dict_to_record(data))
        except Exception as e:
            print(f"registry: skipping cache file {f}: {e}", file=sys.stderr)
    return personas


def _load_custom_personas() -> list:
    """Load custom personas from DomainStore('persona')."""
    try:
        from _domain_store import DomainStore
        ds = DomainStore("persona")
        records = ds.list("personas")
        personas = []
        for r in records:
            r["source"] = "custom"
            personas.append(_dict_to_record(r))
        return personas
    except Exception as e:
        print(f"registry: failed to load custom personas: {e}", file=sys.stderr)
        return []


def _dict_to_record(d: dict) -> PersonaRecord:
    """Convert a dict (from JSON/DomainStore) to a PersonaRecord."""
    return PersonaRecord(
        name=d.get("name", ""),
        description=d.get("description", ""),
        focus=d.get("focus", d.get("description", "")),
        traits=d.get("traits", []),
        role=d.get("role", "custom"),
        source=d.get("source", "custom"),
        personality=d.get("personality", {}),
        constraints=d.get("constraints", []),
        not_focus=d.get("not_focus", []),
        memories=d.get("memories", []),
        preferences=d.get("preferences", {}),
    )


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------

def _merge_personas(
    custom: list,
    cache: list,
    builtin: list,
    fallback: list,
) -> dict:
    """Merge persona sources with priority: custom > cache > builtin > fallback."""
    merged: dict[str, PersonaRecord] = {}
    # Lower priority first so higher priority overwrites
    for p in fallback:
        merged[p.name.lower()] = p
    for p in builtin:
        merged[p.name.lower()] = p
    for p in cache:
        merged[p.name.lower()] = p
    for p in custom:
        merged[p.name.lower()] = p
    return merged


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_personas(*, role: Optional[str] = None, source: Optional[str] = None) -> list:
    """List all available personas, optionally filtered."""
    plugin_root = _plugin_root()
    builtin = _load_builtin_personas(plugin_root)
    fallback = _load_fallback_personas() if not builtin else []
    cache = _load_cache_personas()
    custom = _load_custom_personas()
    merged = _merge_personas(custom, cache, builtin, fallback)

    results = list(merged.values())

    if role:
        results = [p for p in results if p.role.lower() == role.lower()]
    if source:
        results = [p for p in results if p.source.lower() == source.lower()]

    # Sort by source priority then name
    _source_order = {"custom": 0, "cache": 1, "builtin": 2, "fallback": 3}
    results.sort(key=lambda p: (_source_order.get(p.source, 9), p.name))
    return [p.to_dict() for p in results]


def get_persona(name: str) -> Optional[dict]:
    """Look up a single persona by name (case-insensitive)."""
    plugin_root = _plugin_root()
    builtin = _load_builtin_personas(plugin_root)
    fallback = _load_fallback_personas() if not builtin else []
    cache = _load_cache_personas()
    custom = _load_custom_personas()
    merged = _merge_personas(custom, cache, builtin, fallback)
    record = merged.get(name.lower())
    if record is None:
        return None
    return record.to_dict()


def save_persona(
    name: str,
    focus: str,
    *,
    description: str = "",
    traits: Optional[list] = None,
    role: str = "custom",
    personality: Optional[dict] = None,
    constraints: Optional[list] = None,
    not_focus: Optional[list] = None,
    memories: Optional[list] = None,
    preferences: Optional[dict] = None,
) -> dict:
    """Save a custom persona to project-scoped DomainStore."""
    if not focus:
        raise ValueError("focus is required -- describe the perspective this persona applies.")

    if not description:
        description = f"{focus}-focused perspective"

    payload = {
        "name": name,
        "description": description,
        "focus": focus,
        "traits": traits or [],
        "role": role,
        "source": "custom",
        "personality": personality or {},
        "constraints": constraints or [],
        "not_focus": not_focus or [],
        "memories": memories or [],
        "preferences": preferences or {},
    }

    try:
        from _domain_store import DomainStore
        ds = DomainStore("persona")
        existing = ds.get("personas", name)
        if existing:
            result = ds.update("personas", name, payload)
            result["_updated"] = True
        else:
            payload["name"] = name
            result = ds.create("personas", payload)
            result["_updated"] = False
        result["source"] = "custom"
        return result
    except Exception as e:
        print(f"registry: DomainStore unavailable, returning payload: {e}", file=sys.stderr)
        return payload


def save_to_cache(name: str, persona: dict) -> Path:
    """Save a persona to the plugin-level cache for cross-project reuse."""
    safe_name = Path(name).name  # strip directory components to prevent traversal
    if not safe_name or safe_name != name:
        raise ValueError(f"Invalid persona name: {name!r}")
    cache = _cache_dir()
    cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = cache / f"{safe_name}.json"
    persona_copy = dict(persona)
    persona_copy["source"] = "cache"
    path.write_text(json.dumps(persona_copy, indent=2), encoding="utf-8")
    return path


def delete_persona(name: str) -> bool:
    """Delete a custom persona from DomainStore.

    Custom personas are stored under an auto-generated UUID ``id`` (the
    DomainStore key); the human ``name`` lives in the record body. Deleting by
    ``name`` therefore looked up ``{name}.json``, found nothing, and silently
    returned False — the persona was never removed. Resolve ``name`` -> ``id``
    first (case-insensitive, matching ``get_persona``) and delete by the real
    key. Returns False when no custom persona matches the name.
    """
    try:
        from _domain_store import DomainStore
        ds = DomainStore("persona")
        target = name.lower()
        record_id = next(
            (r.get("id") for r in ds.list("personas")
             if str(r.get("name", "")).lower() == target and r.get("id")),
            None,
        )
        if record_id is None:
            return False
        return ds.delete("personas", record_id)
    except Exception as e:
        print(f"registry: failed to delete persona: {e}", file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _output(data, as_json: bool) -> None:
    """Print data as JSON or human-readable."""
    if as_json:
        print(json.dumps(data, indent=2))
    elif isinstance(data, list):
        for p in data:
            print(f"  {p['name']:25s} {p.get('source',''):10s} {p.get('description','')[:60]}")
    elif isinstance(data, dict):
        for k, v in data.items():
            if not k.startswith("_"):
                print(f"  {k}: {v}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """CLI entry point — argparse with subcommands via flags."""
    import argparse

    parser = argparse.ArgumentParser(description="Persona registry")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", help="List all personas")
    group.add_argument("--get", metavar="NAME", help="Get a persona by name")
    group.add_argument("--define", metavar="NAME", help="Define/update a custom persona")
    group.add_argument("--save-cache", metavar="NAME", help="Save persona to plugin cache")

    parser.add_argument("--focus", help="Persona focus (required with --define)")
    parser.add_argument("--traits", help="Comma-separated traits")
    parser.add_argument("--role", help="Role category for filtering")
    parser.add_argument("--source", help="Source filter for --list")
    parser.add_argument("--description", help="One-line description")
    parser.add_argument(
        "--constraints",
        help="Semicolon-separated non-negotiable rules. For a METHODOLOGY persona, "
        "phrase each as a named failure-mode defense: "
        "'FAILURE MODE — <name>: <the guard the base model skips>'.",
    )
    parser.add_argument(
        "--not-focus",
        dest="not_focus",
        help="Semicolon-separated concerns this persona does NOT own (scope guard). "
        "Keeps a methodology persona sharp instead of diffusing into a generic reviewer.",
    )
    parser.add_argument("--json", action="store_true", help="JSON output", dest="as_json")

    args = parser.parse_args()

    if args.list:
        result = list_personas(role=args.role, source=args.source)
        _output(result, args.as_json)

    elif args.get:
        result = get_persona(args.get)
        if result is None:
            print(json.dumps({
                "error": f"Persona '{args.get}' not found",
                "available": [p["name"] for p in list_personas()],
            }), file=sys.stderr)
            sys.exit(1)
        _output(result, args.as_json)

    elif args.define:
        if not args.focus:
            print(json.dumps({
                "error": "focus is required -- describe the perspective this persona applies."
            }), file=sys.stderr)
            sys.exit(1)
        traits = [t.strip() for t in args.traits.split(",")] if args.traits else []
        # Constraints and not_focus are SEMICOLON-separated (commas are common inside
        # a single failure-mode rule, so semicolon is the safer record separator).
        constraints = (
            [c.strip() for c in args.constraints.split(";") if c.strip()]
            if args.constraints else []
        )
        not_focus = (
            [n.strip() for n in args.not_focus.split(";") if n.strip()]
            if args.not_focus else []
        )
        result = save_persona(
            args.define,
            args.focus,
            description=args.description or "",
            traits=traits,
            role=args.role or "custom",
            constraints=constraints,
            not_focus=not_focus,
        )
        _output(result, args.as_json)

    elif args.save_cache:
        persona = get_persona(args.save_cache)
        if persona is None:
            print(json.dumps({"error": f"Persona '{args.save_cache}' not found"}),
                  file=sys.stderr)
            sys.exit(1)
        path = save_to_cache(args.save_cache, persona)
        _output({"saved": str(path), "persona": persona}, args.as_json)


if __name__ == "__main__":
    main()
