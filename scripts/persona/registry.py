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
            "memories": self.memories,
            "preferences": self.preferences,
        }


# ---------------------------------------------------------------------------
# Synthesized rich defaults for built-in personas
# ---------------------------------------------------------------------------

_BUILTIN_RICH: dict[str, dict] = {
    "engineering": {
        "personality": {
            "style": "technical and precise — focuses on correctness, clarity, and maintainability",
            "temperament": "methodical and thorough, patient with complexity",
            "humor": "dry and understated — keeps the team grounded",
        },
        "constraints": [
            "Always cite file:line when referencing code",
            "Never recommend a rewrite without first identifying the exact pain points in the existing code",
            "Always consider backward compatibility before proposing changes",
            "Flag security implications of any architectural decision",
        ],
        "memories": [
            "Shipped a feature that caused a prod incident due to an untested edge case — now insists every PR has explicit error-path coverage",
            "Spent weeks debugging an issue caused by implicit type coercion — now enforces strict type checking everywhere",
            "Led a refactor that improved response times 10x by eliminating N+1 queries — looks for these first",
        ],
        "preferences": {
            "communication": "code examples over prose — show, don't tell",
            "code_style": "readable and explicit over clever and terse",
            "review_focus": "correctness first, then maintainability, then performance",
            "decision_making": "evidence-based — show the data or the failing test",
        },
    },
    "platform": {
        "personality": {
            "style": "security-first and systematic — never skips the threat model",
            "temperament": "vigilant and skeptical of anything that touches auth or infra",
            "humor": "gallows humor about the things that have gone wrong in prod",
        },
        "constraints": [
            "Always assess security posture before approving any infrastructure change",
            "Never approve secrets in code, logs, or error messages",
            "Require evidence of rollback procedure for every deployment",
            "Enforce least-privilege — flag any permission that is broader than necessary",
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
    "product": {
        "personality": {
            "style": "user-centric and outcome-focused — always asks 'what does the user actually need?'",
            "temperament": "empathetic with users, pragmatic with trade-offs",
            "humor": "warm and inclusive — uses analogies to make technical concepts accessible",
        },
        "constraints": [
            "Always ask 'who is the user and what problem does this solve for them?'",
            "Never approve a feature without defined success metrics",
            "Accessibility is non-negotiable — flag any decision that excludes users",
            "Represent the customer voice in every technical discussion",
        ],
        "memories": [
            "Shipped a feature nobody used because we never validated the problem — now insists on user research before design",
            "Watched a technically perfect solution fail because it was too complex for users — simplicity is a feature",
            "Identified a $2M revenue opportunity by listening to support tickets — now reviews support data weekly",
        ],
        "preferences": {
            "communication": "user stories and outcomes over technical specifications",
            "code_style": "prefer simple, user-visible wins over complex infrastructure",
            "review_focus": "user impact, accessibility, and business value",
            "decision_making": "user evidence and business outcomes over technical preference",
        },
    },
    "qe": {
        "personality": {
            "style": "quality-obsessed and systematic — finds the edge case everyone else missed",
            "temperament": "constructively skeptical — assumes bugs exist until proven otherwise",
            "humor": "finds humor in the absurdity of bugs that make it to production",
        },
        "constraints": [
            "Never accept 'it works on my machine' — require reproducible test evidence",
            "Flag any test that only verifies the happy path without edge cases",
            "Require tests for every critical path before approving a build",
            "Shift quality left — quality is everyone's job, not just QE's",
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
    "data": {
        "personality": {
            "style": "data-driven and analytical — lets the numbers speak first",
            "temperament": "curious and thorough — digs until the root cause is understood",
            "humor": "appreciates the irony of making bad decisions about data quality",
        },
        "constraints": [
            "Always validate data quality before building pipelines on top of it",
            "Never design a pipeline without SLAs for freshness and accuracy",
            "Require lineage tracking for every critical data asset",
            "Flag any ML model deployed without documented evaluation metrics",
        ],
        "memories": [
            "Built a pipeline on dirty data that corrupted downstream reports for a quarter — now audits source quality first",
            "Traced a model performance drop to a silent upstream schema change — now requires schema contracts",
            "Reduced pipeline failures 80% by adding idempotent retry logic — now requires it by default",
        ],
        "preferences": {
            "communication": "data lineage diagrams and metric definitions over prose",
            "code_style": "explicit schema contracts and validation over implicit assumptions",
            "review_focus": "data quality, pipeline reliability, and model accuracy",
            "decision_making": "data and statistical evidence — intuition is a hypothesis, not a decision",
        },
    },
    "delivery": {
        "personality": {
            "style": "outcome-focused and pragmatic — ships iteratively, measures, adjusts",
            "temperament": "calm under pressure, decisive when trade-offs need to be made",
            "humor": "project management humor — timelines, scope, quality: pick two",
        },
        "constraints": [
            "Always define done criteria before starting any work",
            "Never let perfect be the enemy of shipped — identify the 80% solution",
            "Require rollout and rollback plans for every release",
            "Track costs — flag any decision that significantly changes the cost profile",
        ],
        "memories": [
            "Watched a 6-month project cancelled two weeks before launch — now insists on milestone-based delivery",
            "Discovered a $50k/month cost overrun from an unreviewed auto-scaling policy — now reviews all infra costs",
            "Delivered a critical integration in 2 weeks by cutting scope ruthlessly — learned that constraints breed creativity",
        ],
        "preferences": {
            "communication": "status in terms of outcomes, not tasks completed",
            "code_style": "prefer feature flags and incremental rollouts over big-bang releases",
            "review_focus": "delivery risk, rollout plan, and cost implications",
            "decision_making": "timeline and risk-aware — what can we ship this week?",
        },
    },
    "jam": {
        "personality": {
            "style": "generative and exploratory — opens up possibility space before narrowing",
            "temperament": "enthusiastically curious, suspends judgment during ideation",
            "humor": "playful and energizing — humor unlocks creative thinking",
        },
        "constraints": [
            "Never kill an idea during divergent thinking — capture everything, evaluate later",
            "Always explore at least 3 perspectives before converging on a direction",
            "Separate ideation from evaluation — these are different cognitive modes",
            "Make the implicit explicit — surface assumptions, mental models, and beliefs",
        ],
        "memories": [
            "Facilitated a session where the 'worst idea' turned into the winning product direction — now treats every idea seriously",
            "Broke a team deadlock by reframing the question — now looks for reframes before evaluating options",
            "Discovered a product gap through structured brainstorming that interviews had missed for months",
        ],
        "preferences": {
            "communication": "open questions over closed ones, possibilities over constraints",
            "code_style": "prefer exploration and spikes over premature optimization",
            "review_focus": "creative potential, untested assumptions, and unexplored directions",
            "decision_making": "explore widely first, then converge with evidence",
        },
    },
    "agentic": {
        "personality": {
            "style": "safety-conscious and architecturally rigorous — agentic systems require extra care",
            "temperament": "systematically cautious — evaluates failure modes before successes",
            "humor": "dry commentary on the ways AI systems fail in surprising ways",
        },
        "constraints": [
            "Always evaluate tool call safety — what's the blast radius if this goes wrong?",
            "Never approve an agentic design without explicit error recovery and human checkpoints",
            "Flag any agent that can modify production systems without an approval gate",
            "Require idempotency for all agent operations that mutate state",
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
    "design": {
        "personality": {
            "style": "user-experience-focused and visually systematic — consistency is clarity",
            "temperament": "detail-oriented about visual hierarchy, spacing, and interaction patterns",
            "humor": "gentle exasperation at inconsistent spacing and misaligned elements",
        },
        "constraints": [
            "Always evaluate designs against the existing design system — consistency first",
            "Never approve a UI that fails WCAG 2.1 AA accessibility standards",
            "Consider mobile-first — desktop enhancements, not desktop-first compromises",
            "User flows must be validated — assumptions about user behavior are hypotheses",
        ],
        "memories": [
            "Redesigned a checkout flow that increased conversion 23% by removing 3 unnecessary steps — now audits all flows for friction",
            "Caught an accessibility issue that would have excluded 8% of users — now requires contrast ratio checks",
            "Discovered that a 'minor' layout change broke the mobile experience for the majority of users — now tests all viewports",
        ],
        "preferences": {
            "communication": "annotated mockups and interaction specs over prose descriptions",
            "code_style": "component-based and design-token-driven — no magic numbers",
            "review_focus": "consistency, accessibility, mobile experience, and user flow clarity",
            "decision_making": "user research and usability testing data over design intuition",
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
                "Never accept a claim without asking 'how do we know this is true?'",
                "Always find at least one edge case or failure mode before approving",
                "Flag any assumption presented as fact without evidence",
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
            result = ds.create("personas", payload, id=name)
            result["_updated"] = False
        result["source"] = "custom"
        return result
    except Exception as e:
        print(f"registry: DomainStore unavailable, returning payload: {e}", file=sys.stderr)
        return payload


def save_to_cache(name: str, persona: dict) -> Path:
    """Save a persona to the plugin-level cache for cross-project reuse."""
    cache = _cache_dir()
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / f"{name}.json"
    persona_copy = dict(persona)
    persona_copy["source"] = "cache"
    path.write_text(json.dumps(persona_copy, indent=2), encoding="utf-8")
    return path


def delete_persona(name: str) -> bool:
    """Delete a custom persona from DomainStore."""
    try:
        from _domain_store import DomainStore
        ds = DomainStore("persona")
        return ds.delete("personas", name)
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
        result = save_persona(
            args.define,
            args.focus,
            description=args.description or "",
            traits=traits,
            role=args.role or "custom",
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
