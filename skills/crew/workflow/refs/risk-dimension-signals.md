# Risk Dimension Signals

Seven independent risk dimensions computed from text analysis. Each dimension
is scored 0-3 and drives different workflow decisions.

---

## Dimension Overview

| Dimension | Range | Drives |
|-----------|-------|--------|
| impact | 0-3 | Gate strictness (fast-pass vs full gate) |
| reversibility | 0-3 | Rollback planning, gate type selection |
| novelty | 0-3 | Specialist engagement, design phase inclusion |
| test_complexity | 0-3 | Test strategy scope, integration test setup needs |
| documentation | 0-3 | API docs, user guides, ADR requirements |
| coordination_cost | 0-3 | Cross-domain deps, specialist handoffs, review requirements |
| operational | 0-3 | Deployment, migration, rollback operational needs |

---

## Dimension: impact

Combines file role analysis with integration surface detection. Capped at 3.

### File Role Scoring (5-tier taxonomy)

| Tier | File Pattern | Weight |
|------|-------------|--------|
| 1 (behavior-defining) | commands/, handlers/, controllers/, routes/, middleware/, interceptors/ | 3.0 |
| 1 | hooks/, triggers/, listeners/, subscribers/ | 3.0 |
| 1 | .github/workflows/, gitlab-ci, Jenkinsfile | 3.0 |
| 1 | .tf, .hcl, Dockerfile, docker-compose | 3.0 |
| 1 | hooks.json, routes.json, pipeline.json | 3.0 |
| 1 | Makefile | 3.0 |
| 1 | agents/ | 3.0 |
| 1 | hooks/scripts/ | 3.0 |
| 2 (source code) | src/, lib/, app/, pkg/, internal/, core/ | 1.5 |
| 2 | scripts/ | 1.5 |
| 2 | skills/*.md, SKILL.md | 1.5 |
| 3 (generic code) | .py, .ts, .js, .go, .rs, .java, .rb, .tsx, .jsx, .c, .cpp | 1.0 |
| 4 (test code) | tests/, spec/, __tests__, e2e/, cypress/, playwright/ | 1.0 |
| 5 (low-impact) | README | 0.5 |
| 5 | CHANGELOG | 0.5 |
| 5 | docs/, examples/, samples/ | 0.5 |
| 5 | .md files | 0.5 |
| 5 | .json, .yaml files | 0.5 |
| 5 | LICENSE | 0.0 |

**Scoring**: Start with highest-weight file match. If 3+ distinct file matches, add +1 breadth bonus. Cap at 3.

### Integration Surface Detection

If ANY of these keywords appear in the text, add +2: `integrate, connect, api, endpoint, service, system`

Match all (first match of each keyword counts, not per-occurrence).

---

## Dimension: reversibility

0 = trivially reversible, 3 = very hard to undo. Additive scoring.

### Irreversibility Signals (push score UP)

| Keyword | Weight | Label |
|---------|--------|-------|
| migrat* | +3 | data migration |
| schema change | +3 | schema change |
| schema migrat* | +3 | schema migration |
| drop table | +3 | destructive DDL |
| drop column | +3 | destructive DDL |
| data transform* | +2 | data transformation |
| breaking change | +3 | breaking change |
| deprecat* | +2 | deprecation |
| remove api | +3 | API removal |
| rename api | +2 | API rename |
| backward incompatible | +3 | backward incompatible |
| delete | +1 | deletion |
| remove | +1 | removal |
| rename | +1 | rename |
| restructur* | +2 | restructuring |
| third party | +1 | third-party dependency |
| external api | +2 | external API |
| vendor | +1 | vendor dependency |

### Reversibility Mitigators (push score DOWN, negative weights)

| Keyword | Weight | Label |
|---------|--------|-------|
| feature flag | -2 | feature-flagged |
| feature toggle | -2 | feature-flagged |
| toggle | -1 | toggle available |
| rollback | -1 | rollback mentioned |
| revert | -1 | revert mentioned |
| canary | -1 | canary deployment |
| blue-green | -1 | blue-green deployment |
| experiment | -1 | experimental |

**Final score**: Sum all matched weights, then clamp to [0, 3].

---

## Dimension: novelty

0 = routine/familiar, 3 = highly novel/uncertain. Sources are additive.

### Explicit Novelty Keywords (break after first match)

| Keyword | Weight | Label |
|---------|--------|-------|
| first time | +2 | first-time work |
| new pattern | +2 | new pattern |
| prototype | +2 | prototype |
| proof of concept | +2 | proof of concept |
| poc | +2 | proof of concept |
| greenfield | +2 | greenfield |
| from scratch | +2 | built from scratch |
| never done | +2 | never done before |
| unfamiliar | +1 | unfamiliar territory |
| research | +1 | research needed |
| spike | +1 | exploration spike |
| experiment* | +1 | experimental |
| evaluat* | +1 | evaluation |

### Cross-Domain Bonus (applies after keyword check)

| Condition | Weight |
|-----------|--------|
| 3+ detected signal categories | +2 |
| 2 detected signal categories | +1 |

### Ambiguity Bonus

| Condition | Weight |
|-----------|--------|
| Input is ambiguous | +1 |

**Final score**: Sum all components, clamp to [0, 3].

---

## Dimension: test_complexity

Detects test strategy scope and integration test setup needs. All matches additive.

| Keyword | Weight |
|---------|--------|
| end-to-end test* | +2 |
| e2e test* | +2 |
| integration test* | +2 |
| test fixture* | +1 |
| test strateg* | +2 |
| playwright | +2 |
| cypress | +2 |
| mock service* | +1 |
| contract test* | +2 |
| test coverag* | +1 |
| acceptance test* | +2 |
| performance test* | +2 |
| load test* | +2 |
| ci pipeline | +1 |
| test suite* | +1 |
| unit test* | +1 |
| test setup | +1 |
| test infrastr* | +2 |

**Final score**: Sum all, clamp to [0, 3].

---

## Dimension: documentation

Detects API docs, user guides, ADR requirements. All matches additive.

| Keyword | Weight |
|---------|--------|
| openapi | +2 |
| swagger | +2 |
| api doc* | +2 |
| adr | +2 |
| architecture decision | +2 |
| decision record | +2 |
| user guide* | +2 |
| migration guide* | +2 |
| changelog | +1 |
| readme | +1 |
| runbook | +2 |
| playbook | +2 |
| docstring* | +1 |
| api reference* | +2 |
| technical doc* | +2 |
| annotate | +1 |
| document the | +1 |
| publish doc* | +2 |

**Final score**: Sum all, clamp to [0, 3].

---

## Dimension: coordination_cost

Detects cross-domain dependencies, specialist handoffs, review requirements.

| Keyword | Weight |
|---------|--------|
| coordinate with | +2 |
| cross-team | +2 |
| cross team | +2 |
| specialist review | +2 |
| cross-domain | +2 |
| handoff | +1 |
| hand-off | +1 |
| multiple team* | +2 |
| security review | +2 |
| legal review | +2 |
| compliance review | +2 |
| sign-off | +1 |
| approval required | +2 |
| stakeholder review | +2 |
| cross-functional | +2 |
| review board | +2 |
| change request | +1 |
| change control | +2 |

**Final score**: Sum all, clamp to [0, 3].

---

## Dimension: operational

Detects deployment, migration, rollback operational needs.

| Keyword | Weight |
|---------|--------|
| deploy* | +1 |
| zero-downtime | +3 |
| blue-green | +2 |
| canary deploy* | +2 |
| rollback plan | +3 |
| database migration | +3 |
| schema migration | +3 |
| migration script* | +2 |
| deployment window | +2 |
| ops monitor* | +2 |
| health check* | +1 |
| on-call | +2 |
| runbook | +2 |
| incident response | +3 |
| production deploy* | +2 |
| feature flag* | +1 |
| infra change* | +2 |
| config change* | +1 |
| environment variable* | +1 |

**Final score**: Sum all, clamp to [0, 3].
