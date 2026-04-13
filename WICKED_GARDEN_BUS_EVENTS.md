# wicked-garden Bus Event Catalog

> Auto-generated from `scripts/_bus.py:BUS_EVENT_MAP`. Do not edit manually.
> Regenerate: `python3 scripts/_bus_catalog_gen.py > WICKED_GARDEN_BUS_EVENTS.md`

## Naming Convention

```
wicked.<noun>.<past-tense-verb>
```

Three segments. Always starts with `wicked.`. Noun = the thing that changed. Verb = past tense.
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
| `wicked.gate.blocked` | `crew.gate` | Gate returned REJECT — phase advancement blocked |
| `wicked.gate.decided` | `crew.gate` | Gate returned APPROVE, CONDITIONAL, or REJECT |
| `wicked.phase.auto_advanced` | `crew.phase` | Phase auto-advanced for low-complexity project (audit trail) |
| `wicked.phase.transitioned` | `crew.phase` | Phase approved and advanced to next |
| `wicked.project.completed` | `crew.project` | Crew project completed (final phase approved) |
| `wicked.project.complexity_scored` | `crew.scoring` | Complexity score computed for a project |
| `wicked.project.created` | `crew.project` | New crew project created with complexity scoring |
| `wicked.rework.triggered` | `crew.rework` | Rework initiated after gate REJECT or CONDITIONAL |

### Delivery

| Event Type | Subdomain | Description |
|------------|-----------|-------------|
| `wicked.experiment.concluded` | `delivery.experiment` | A/B experiment concluded with results |
| `wicked.rollout.decided` | `delivery.rollout` | Rollout go/no-go decision made |

### Jam

| Event Type | Subdomain | Description |
|------------|-----------|-------------|
| `wicked.council.voted` | `jam.council` | Council evaluation completed with model votes |
| `wicked.persona.contributed` | `jam.persona` | Persona contributed a perspective in a brainstorm round |
| `wicked.session.started` | `jam.session` | Brainstorm or council session started |
| `wicked.session.synthesized` | `jam.session` | Session synthesis completed |

### Platform

| Event Type | Subdomain | Description |
|------------|-----------|-------------|
| `wicked.compliance.failed` | `platform.compliance` | Compliance check failed for a framework |
| `wicked.compliance.passed` | `platform.compliance` | Compliance check passed for a framework |
| `wicked.security.finding_raised` | `platform.security` | Security review raised a finding |

### Qe

| Event Type | Subdomain | Description |
|------------|-----------|-------------|
| `wicked.coverage.changed` | `qe.coverage` | Test coverage metrics changed |
| `wicked.scenario.run` | `qe.scenario` | Test scenario executed with pass/fail result |

## chain_id

All crew events carry `chain_id` in the `metadata` field (top-level, not buried in payload).
Format: `{uuid8}.root` for project root, `{uuid8}.{phase}` for phase scope.
Enables timeline reconstruction across phases without a graph DB.

## Consumer Integration Examples

### Slack Bot (5 events)

Subscribe to: `wicked.gate.blocked`, `wicked.phase.transitioned`, `wicked.project.completed`,
`wicked.session.synthesized`, `wicked.rework.triggered`

```bash
npx wicked-bus subscribe --plugin my-slack-bot --filter 'wicked.gate.*' --filter 'wicked.phase.*'
```

### Dashboard (all events)

Subscribe to: `wicked.*@wicked-garden`

```bash
npx wicked-bus subscribe --plugin my-dashboard --filter 'wicked.*@wicked-garden'
```
