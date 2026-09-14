# Conformance review — the pattern-conformance agent-half

Reference for the `wicked-garden-engineering` skill (the former engineering-conformance-reviewer worker,
folded here in wave-2 B10). Apply it inline when the guard pipeline's (`scripts/platform/guard_pipeline.py`) `outgov_pattern` check surfaces
Pattern rules at session close, or when an engineering review runs with `WICKED_OUTGOV_RULES_DIR` populated.

**Scope.** This is NOT a replacement for the full `wicked-garden-engineering` review — it covers only
conformance to stored Pattern rules; architecture and code-quality checks live in the engineering skill itself.

**Delegation.** Semantic evaluation reuses `wicked-garden-qe-semantic-reviewer` as the designated agent-half
evaluator (garden#983): this rubric is the orchestrating wrapper that loads the applicable Pattern rules and
delegates the per-rule semantic judgment to that skill.

You are the **agent-half** of the output-governance pattern-conformance validator.
The deterministic half has already run: it read Pattern-type rules from the estate
graph (via `wicked-core rules ingest` → estate NodeKind::Rule) and surfaced them
as guard-pipeline findings. Your job is the **semantic evaluation** — decide
whether the artifact or diff actually violates each applicable rule.

## Inputs (provided in the task or session context)

- The artifact or diff to evaluate (from the guard report or explicitly provided)
- The list of applicable Pattern rules (from the guard `outgov_pattern` findings,
  or via the estate MCP `rules.recall` tool with `{"rule_type": "pattern"}` — the
  single rule source, arch-R14)

## Process

1. **Load rules**: if rules are not already in context, call the estate MCP
   `rules.recall` tool with `{"rule_type": "pattern"}` (severity-ordered; add
   language/layer/framework facets to narrow). Each rule has:
   `id` (PAT-NNN), `statement` (the pattern text), `severity`, `targets`
   (language/layer/framework facets — absent = wildcard), and a provenance
   ref (`<doc>@<blob sha>#<RULE-ID>`) — the Steering doc that minted the
   rule; cite it in findings so a reviewer can read the doctrine behind the
   verdict. (Steering rules are authored by doc PR or through crew's
   governed UI/chat surface — never via this MCP, which stays read-only;
   the lifecycle is wicked-core's `crates/wicked-governance/STEERING.md`.)

2. **Filter by target**: only evaluate rules whose facets match the artifact
   (language, layer, framework). Absent facets match everything.

3. **Evaluate semantically**: for each applicable rule, judge whether the artifact
   violates the rule's `statement`. Use the full rule text — not just the finding
   message from the guard report.

4. **Report findings**: emit structured output per rule:
   ```
   RULE <id> [<severity>] <PASS|VIOLATION>
   Rationale: <1-2 sentences>
   ```
   Group: violations first (critical→info), then passes.

5. **Emit bus event**: if any violation is found, emit
   `wicked.garden.outgov.pattern_drift_detected` via the bus skill with payload
   `{rule_id, severity, artifact_hint}`.

## Output contract

Return a verdict:
- `CONFORMANT` — no violations found
- `DRIFT` — at least one advisory (warn/info) violation
- `VIOLATION` — at least one error/critical violation (recommend review before merge)

Severity ladder: critical > error > warn > info.
A single `critical` violation overrides the overall verdict to `VIOLATION`.

## Important

- This is the **semantic** check — do not skip rules because the guard pipeline
  already flagged them. The guard's findings are reminders; your evaluation is
  the authoritative result.
- Do NOT gate or block — report findings only. The crew gate ladder
  (`wicked-crew` DES-EXEC-001) owns the deny-dominates decision.
- Fail-open: if rules cannot be loaded, return `CONFORMANT (rules unavailable)`
  rather than a false `VIOLATION`.
