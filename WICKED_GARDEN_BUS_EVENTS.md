# wicked-garden Bus Event Catalog

> Auto-generated from `scripts/_bus.py:BUS_EVENT_MAP`. Do not edit manually.
> Regenerate: `python3 scripts/_bus_catalog_gen.py > WICKED_GARDEN_BUS_EVENTS.md`

## Naming Convention

```
wicked.<domain>.<noun>.<past-tense-verb>
```

Four segments (wicked-bus SPEC grammar). Always starts with `wicked.`. Domain = the producing plugin's short name (`garden` for garden-owned events; `crew` for the shared phase lifecycle; `brain` for consumed wicked-brain events). Noun = the thing that changed. Verb = past tense.
`domain` field is always `wicked-garden`. `subdomain` identifies the functional area.

## Payload Tiers

| Tier | Contents | Rule |
|------|----------|------|
| **Tier 1** | IDs + outcomes | Always included |
| **Tier 2** | Small categoricals (complexity_score, duration_secs, specialist) | Include when relevant |
| **Tier 3** | Content, diffs, memory body, source code | **NEVER on bus** |

## Payload Deny-List

These fields are **stripped automatically** by `_bus.py` before emission:

- `api_key`
- `body`
- `content`
- `credential`
- `diff`
- `file_content`
- `memory_content`
- `password`
- `patch`
- `prompt`
- `raw_text`
- `secret`
- `source_code`
- `thinking`
- `token`

## Event Catalog

### Crew

| Event Type | Subdomain | Description |
|------------|-----------|-------------|
| `wicked.crew.phase.transitioned` | `crew.phase` | Phase approved and advanced to next |
| `wicked.garden.amendment.appended` | `crew.amendment` | Phase amendment appended to amendments.jsonl (Site W6 cutover) |
| `wicked.garden.archetype.advanced` | `crew.archetype` | v11 archetype phase approved + (when present) next phase named |
| `wicked.garden.archetype.classified` | `crew.classify` | v11 prompt classified into work-shape archetype set (LLM or regex tier) |
| `wicked.garden.archetype.completed` | `crew.archetype` | v11 archetype final phase approved (project is_complete) |
| `wicked.garden.archetype.created` | `crew.archetype` | v11 archetype-mode project created (carries v11_archetype + initial phase_plan) |
| `wicked.garden.archetype.hard_gate_passed` | `crew.archetype` | v11 archetype hard gate (cutover/mitigate/etc.) passed with confirmed_by + evidence |
| `wicked.garden.condition.marked_cleared` | `crew.condition` | Condition verification flipped to verified=True via mark_cleared() (Site 5 cutover) |
| `wicked.garden.condition.resolved` | `crew.condition` | Mechanical CONDITIONAL finding resolved via crew:resolve skill (verdict unchanged) |
| `wicked.garden.consensus.evidence_recorded` | `crew.consensus` | Consensus rejection evidence written to consensus-evidence.json (audit trail) |
| `wicked.garden.consensus.gate_completed` | `crew.consensus` | Consensus gate verdict written to reviewer-report.md (append or create) |
| `wicked.garden.consensus.gate_pending` | `crew.consensus` | Pending consensus gate placeholder written to reviewer-report.md (evaluation failed) |
| `wicked.garden.consensus.report_created` | `crew.consensus` | Consensus gate report written to consensus-report.json |
| `wicked.garden.convergence.transition_recorded` | `crew.convergence` | Convergence-log transition recorded for an artifact (Site W8 cutover) |
| `wicked.garden.crew.inline_review_context_recorded` | `crew.solo_mode` | Inline-HITL gate review evidence recorded by solo_mode (Site W1 cutover) |
| `wicked.garden.crew.legacy_adopted` | `crew.migration` | Legacy beta.3 → v6.0 project migration applied via adopt_legacy.py (audit marker) |
| `wicked.garden.crew.qe_evaluator_migrated` | `crew.migration` | qe-evaluator → gate-adjudicator rename applied via migrate_qe_evaluator_name.py (audit marker) |
| `wicked.garden.crew.yolo_revoked` | `crew.yolo` | Yolo auto-approval revoked due to scope-increase mutation (audit + observability) |
| `wicked.garden.dispatch.log_entry_appended` | `crew.dispatch` | HMAC-signed dispatch-log.jsonl entry appended (orphan-check sentinel) |
| `wicked.garden.gate.blocked` | `crew.gate` | Gate returned REJECT — phase advancement blocked |
| `wicked.garden.gate.decided` | `crew.gate` | Gate returned APPROVE, CONDITIONAL, or REJECT |
| `wicked.garden.hitl.decision_recorded` | `crew.hitl` | HITL pause-decision evidence recorded by hitl_judge.write_hitl_decision_evidence (Site W5 cutover) |
| `wicked.garden.modernize.stack_gap` | `crew.modernize` | Legacy stack class is planned/none/unknown — capability-gap task emitted instead of a fabricated migration |
| `wicked.garden.phase.auto_advanced` | `crew.phase` | Phase auto-advanced for low-complexity project (audit trail) |
| `wicked.garden.project.completed` | `crew.project` | Crew project completed (final phase approved) |
| `wicked.garden.project.complexity_scored` | `crew.scoring` | Complexity score computed for a project |
| `wicked.garden.project.created` | `crew.project` | New crew project created with complexity scoring |
| `wicked.garden.reeval.addendum_appended` | `crew.reeval` | Re-eval addendum appended to per-phase + project-root JSONL logs (Site W7 cutover; dual-file projection) |
| `wicked.garden.review.semantic_gap_recorded` | `crew.review` | Semantic-gap report persisted at review phase (Site W10a cutover) |
| `wicked.garden.rework.triggered` | `crew.rework` | Rework initiated after gate REJECT or CONDITIONAL |
| `wicked.garden.subagent.engaged` | `crew.subagent` | Specialist subagent engagement recorded by subagent_lifecycle (Site W9b cutover) |

### Delivery

| Event Type | Subdomain | Description |
|------------|-----------|-------------|
| `wicked.garden.quality.drift_detected` | `delivery.telemetry` | Cross-session quality metric drifted past baseline threshold (special-cause or >=15% drop) |

### Facts

| Event Type | Subdomain | Description |
|------------|-----------|-------------|
| `wicked.garden.fact.extracted` | `facts` | Structured fact extracted from conversation (consumed by wicked-brain auto-memorize) |

### Gate

| Event Type | Subdomain | Description |
|------------|-----------|-------------|
| `wicked.test.verdict.created` | `gate.verdict` | wicked-testing reviewer recorded a gate verdict (PASS/FAIL/N-A/SKIP) |

### Jam

| Event Type | Subdomain | Description |
|------------|-----------|-------------|
| `wicked.garden.council.voted` | `jam.council` | Council evaluation completed with model votes |
| `wicked.garden.persona.contributed` | `jam.persona` | Persona contributed a perspective in a brainstorm round |
| `wicked.garden.session.started` | `jam.session` | Brainstorm or council session started |
| `wicked.garden.session.synthesis_ready` | `jam.session` | All expected Round 1 personas contributed or timeout elapsed — facilitator may synthesize |
| `wicked.garden.session.synthesized` | `jam.session` | Session synthesis completed |

### Platform

| Event Type | Subdomain | Description |
|------------|-----------|-------------|
| `wicked.garden.compliance.failed` | `platform.compliance` | Compliance check failed for a framework |
| `wicked.garden.compliance.passed` | `platform.compliance` | Compliance check passed for a framework |
| `wicked.garden.guard.findings` | `platform.guard` | Autonomous session-close guard pipeline surfaced findings (Issue #448) |
| `wicked.garden.log.rotated` | `platform.log_retention` | Log file rotated by log_retention.rotate_if_needed (audit marker) |
| `wicked.garden.security.finding_raised` | `platform.security` | Security review raised a finding |

### Qe

| Event Type | Subdomain | Description |
|------------|-----------|-------------|
| `wicked.garden.coverage.changed` | `qe.coverage` | Test coverage metrics changed |
| `wicked.garden.scenario.run` | `qe.scenario` | Test scenario executed with pass/fail result |

## chain_id

All crew events carry `chain_id` in the `metadata` field (top-level, not buried in payload).
Format: `{uuid8}.root` for project root, `{uuid8}.{phase}` for phase scope.
Enables timeline reconstruction across phases without a graph DB.

## Consumer Integration Examples

### Slack Bot (5 events)

Subscribe to: `wicked.garden.gate.blocked`, `wicked.crew.phase.transitioned`, `wicked.garden.project.completed`,
`wicked.garden.session.synthesized`, `wicked.garden.rework.triggered`

```bash
npx wicked-bus subscribe --plugin my-slack-bot --filter 'wicked.garden.gate.*' --filter 'wicked.crew.phase.*'
```

### Dashboard (all events)

Subscribe to: `wicked.*@wicked-garden`

```bash
npx wicked-bus subscribe --plugin my-dashboard --filter 'wicked.*@wicked-garden'
```
