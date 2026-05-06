---
description: Code review with senior engineering perspective on quality, patterns, and maintainability
argument-hint: "[file or directory path] [--focus security|performance|patterns|tests] [--scenarios] [--persona <name>]"
phase_relevance: ["build", "review"]
archetype_relevance: ["code-repo", "schema-migration", "config-infra"]
---

# /wicked-garden:engineering:review

Senior-engineer code review on quality, patterns, maintainability. Use `--focus security|performance|patterns|tests` to deepen one area. Use `--persona <name>` to route the review through a registered persona's lens. Use `--scenarios` to also emit wicked-scenarios regression blocks. Use this for code-level review; use `engineering:arch` for component/system-level architecture review.

## 1. Persona branch (only if `--persona <name>` present)

```bash
PERSONA_JSON=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/persona/registry.py --get "${persona_name}" --json 2>/dev/null)
```

If found: dispatch via `wicked-garden:persona:persona-agent` with the persona JSON + scope + flags echoed in. If not found: warn "Persona '{persona_name}' not found — using default" and fall through to step 2.

## 2. Dispatch

```
Task(subagent_type="wicked-garden:engineering:senior-engineer",
     prompt="""Scope: {path or git-diff target}  Focus: {--focus or 'general'}  Scenarios: {--scenarios true/false}
Run a senior-engineer review: clarity, error handling, contracts, failure recovery, naming, perf, test value.
Flag agent overstepping (unrelated edits, commented-out code, over-engineering, scope creep).
If --focus given, deepen that lane. If --scenarios, emit a wicked-scenarios block per actionable Critical/High finding.
Cite file:line for every finding. Return inline.""")
```
