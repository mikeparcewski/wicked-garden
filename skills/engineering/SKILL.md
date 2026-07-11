---
name: wicked-garden-engineering
user-invocable: true
description: |
  Consolidated engineering domain skill: senior-engineer code review, architecture
  analysis, systematic debugging, implementation planning, and documentation
  generation — plus cross-cutting guidance on code quality, patterns, and
  maintainability.

  Use when: "review this code / file / diff" (quality, patterns, maintainability;
  --focus security|performance|patterns|tests, --persona <name>, --scenarios);
  "review the architecture of X" / "evaluate component boundaries, coupling, or
  layer violations" (--scope module|service|system); "debug this error / bug /
  unexpected behavior" (hypothesis-driven root cause, reproduction, fix,
  prevention); "plan this change" / "implementation plan with specific file
  changes, risk assessment, and test recommendations before writing code";
  "generate API docs / README / guide / inline comments" (--type
  api|readme|guide|inline) or "docs drifted from code". Replaces the former
  /wicked-garden:engineering:{review,arch,debug,plan,docs} commands.

  NOT for reviewing an AI agent system (agentic domain review), a UI (product
  ux-review), or a binding go/no-go verdict (archetype review); NOT for
  greenfield system design (architecture knowledge module or the
  wicked-garden-engineering-solution-architect fork skill).
phase_relevance: ["design", "build", "review"]
archetype_relevance: ["*"]
---

# Engineering

Senior engineering guidance on code quality, architecture, and implementation.
The five actions below run **inline** (no dispatch); genuinely structural,
migration, or API-reference work dispatches to the fork workers listed at the end.

## Routing

| Ask | Action |
|-----|--------|
| Code-level quality review of files or a diff | § review |
| Component/system-level architecture review | § arch |
| Bug / error / unexpected-behavior diagnosis | § debug |
| Implementation plan before writing code | § plan |
| Generate or refresh documentation | § docs |
| Multi-file mechanical change (add-field/rename/remove) | [patch](patch/SKILL.md) |

**Review disambiguation**: this skill reviews **source code**. For an AI agent
system use `agentic` review, for a UI use product `ux-review`, and for a binding
go/no-go verdict use `archetype` review (see `docs/domains.md` → "review appears
in three domains"). `arch` is component/system-level review; `review` is
code-level; greenfield design is the [architecture module](architecture/SKILL.md).

## review — senior-engineer code review

1. Parse scope (path or git-diff target), `--focus`, `--persona`, and `--scenarios`.
2. `Read("${CLAUDE_PLUGIN_ROOT}/skills/engineering/refs/review.md")` — R1–R6 Bulletproof Coding
   Standards, T1–T6 Bulletproof Testing Standards, agent overstepping checklist, focus lane
   definitions, persona routing instructions, wicked-scenarios format, and output template.
3. **Persona branch** (only if `--persona <name>` present): resolve the persona via
   `scripts/persona/registry.py --get {name} --json`. If found, apply the review through that
   persona's frame. If not found, warn and fall through.
4. Read the target file(s) / diff. Apply R1–R6 to all code; add T1–T6 when `--focus tests` or
   reviewing test files. If `--focus` given, deepen that lane. Flag agent overstepping (scope creep,
   commented-out code, over-engineering) with `file:line` citations.
5. Emit the standard Engineering Review output (Strengths, Issues table with rule + location,
   Architecture Notes, Maintainability Concerns, Agent Overstepping, Recommendations).
   If `--scenarios`, append wicked-scenarios blocks for each Critical/High finding.

## arch — architecture analysis

Use `arch` for component/system-level review; use `review` for code-level review.

1. Parse `[target]` and `--scope` (module | service | system; infer if absent from directory depth
   and file count).
2. `Read("${CLAUDE_PLUGIN_ROOT}/skills/engineering/refs/arch.md")` — rubric, checklists, output
   formats, and architecture principles for both module/service and system scope.
3. Map the directory layout, entry points, key dependencies, and data flow of the target.
4. Apply the scope-appropriate checklist from the rubric directly. Flag unauthorized architectural
   changes or scope creep when reviewing a diff.
5. Emit the scope-appropriate output format (strengths, concerns table, recommendations,
   trade-off table, ADR candidates for system scope).

For genuinely structural greenfield design, dispatch
[wicked-garden-engineering-solution-architect](../engineering-solution-architect/SKILL.md).

## debug — systematic debugging session

1. Parse the error message, symptom, or issue description.
2. Use `Skill("superpowers:systematic-debugging")` — the full hypothesis-driven debugging
   methodology (gather context, form hypothesis, test, document root cause).
3. `Read("${CLAUDE_PLUGIN_ROOT}/skills/engineering/refs/debug.md")` for garden-specific heuristics:
   check the wicked-bus first, loom/vault availability for gate failures, cross-platform hook issues,
   and the standard debug output format.
4. Apply the six-step process. Read relevant files at error locations, search for related patterns,
   check logs if available.
5. Emit the standard Debug Analysis output format (Symptom, Root Cause with confidence, Evidence,
   Reproduction Steps, Recommended Fix with rationale, Verification, Prevention).
6. If the user approves the fix, implement it, add a regression test, and verify resolution.

Patterns and deeper process live in the [debugging module](debugging/SKILL.md).

## plan — implementation planning

Analyze a change request against the current codebase and produce a detailed implementation plan
with specific file changes, risk assessment, and test recommendations. **Distinct from the patch
module's `patch-plan`** (propagation preview for mechanical patches — see
[patch/SKILL.md](patch/SKILL.md)); this `plan` produces a human implementation plan.

1. Parse the change request: identify goal, scope, and constraints. Ask a clarifying question if
   the request is too vague to scope (e.g. no target file or system identified).
2. `Read("${CLAUDE_PLUGIN_ROOT}/skills/engineering/refs/plan.md")` — exploration checklist,
   risk assessment checklist, plan output format, and security/performance heuristics.
3. Explore the affected code: entry points, key files, callers, existing patterns, test coverage.
   Use `wicked-garden:search:blast-radius {symbol}` for impact analysis.
4. Apply the risk assessment checklist (breaking changes, performance, security, data integrity,
   test gaps, deployment coordination).
5. Emit the Implementation Plan output format: Summary, Scope (in/out), Changes Required per
   file, Risk Assessment table, Test Plan, Rollout Considerations, Open Questions.
6. Present the plan and ask: "Ready to proceed with implementation, or would you like to adjust
   the approach?" Do not write any code until approved.

## docs — documentation generation

1. Parse `<file or component>` and `--type` (api | readme | guide | inline). Infer if absent:
   `.ts/.py/.go` → api or inline; top-level directory → readme; workflow request → guide.
2. `Read("${CLAUDE_PLUGIN_ROOT}/skills/engineering/refs/docs.md")` — type-routing table,
   pre-generation checklist, API/README/guide/inline checklists, OpenAPI template, and quality
   standards.
3. Read the source code: public interfaces, function signatures, types, error conditions, and
   existing docs (check for drift from implementation).
4. Apply the type-appropriate checklist and generate the documentation inline following the
   output template in the rubric. API/reference docs dispatch to
   [wicked-garden-engineering-api-documentarian](../engineering-api-documentarian/SKILL.md).
5. Present the documentation for user review before writing to file. When writing: API docs →
   `docs/api/`; READMEs → component root; guides → `docs/guides/`; inline → Edit tool in-file.

Audit (coverage metrics) and sync (stale-docs detection) modes live in the
[docs module](docs/SKILL.md).

## Knowledge modules

[architecture](architecture/SKILL.md) · [backend](backend/SKILL.md) ·
[frontend](frontend/SKILL.md) · [integration](integration/SKILL.md) ·
[system-design](system-design/SKILL.md) · [debugging](debugging/SKILL.md) ·
[docs](docs/SKILL.md) · [large-scale-migration](large-scale-migration/SKILL.md) ·
[patch](patch/SKILL.md) · [unit-test-quality](unit-test-quality/SKILL.md)

## Fork workers

| Skill | Dispatch for |
|-------|-------------|
| `wicked-garden-engineering-solution-architect` | System design, structural trade-offs, greenfield architecture, ADRs |
| `wicked-garden-engineering-migration-engineer` | Production schema/data migrations, expand-contract, deprecation paths |
| `wicked-garden-engineering-api-documentarian` | OpenAPI specs, endpoint reference docs |

Frontend (React/CSS/browser), backend (APIs/databases/server-side), and debugging
(error investigation, root-cause analysis) are handled **inline** by this skill —
apply the relevant checklist from `refs/`.

## Key principles

- **Code quality**: clear naming and organization, DRY, SOLID, consistent style.
- **Architecture**: design patterns, separation of concerns, component boundaries,
  dependency management.
- **Maintainability**: easy to understand, modify, and test; well-documented;
  deliberate error handling.
- **Performance**: efficient algorithms and data structures, resource management,
  caching strategies.

## Review process

Use comprehensive checklists covering structure (patterns, abstractions,
dependencies), quality (naming, duplication, style), error handling (recovery,
messages), maintainability (clarity, configuration), performance (queries, data
structures), and **agent overstepping** (unnecessary changes, commented-out code,
scope creep). See [refs/engineering-checklists.md](refs/engineering-checklists.md)
for detailed review checklists and severity guidelines.

## Output formats

Structured guidance for implementation planning (approach + steps) and code
reviews (strengths, issues, recommendations). See
[refs/engineering-templates.md](refs/engineering-templates.md) for output
templates and focus areas.

## Integration with wicked-crew

Engaged during the **build phase** (implementation guidance and pattern
recommendations), the **review phase** (code quality and architecture review),
and **error recovery** (when issues are encountered during development).

## Notes

- Always explain the "why" behind recommendations.
- Be constructive, not critical.
- Offer alternatives with tradeoffs.
- Encourage questions and discussion.
