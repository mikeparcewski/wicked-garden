# Stakeholder Report Rubric

Apply this inline. Generate multi-perspective delivery reports from project data.

## Data ingestion

Accept from:
- **CSV/export files**: map columns to id, title, status, priority, assignee, labels, dates.
- **Active tasks**: read native tasks under `${CLAUDE_CONFIG_DIR}/tasks/{session_id}/`; filter by `metadata.event_type=="task"`.
- **Crew project**: `sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/crew/phase_manager.py" status`.
- **Verbal description**: extract tasks, statuses, blockers from prose.

## Base metrics to compute

- **Total items**: count of all tasks.
- **Status breakdown**: Done / In Progress / Blocked / Todo.
- **Completion rate**: Done / Total.
- **Priority distribution**: P0/P1/P2/P3 counts.
- **Aging**: items not updated in threshold period.
- **Blocker count**: items in blocked status.

## Six persona lenses

### Default (always generated)

**Delivery Lead**: Sprint velocity + completion rate, blockers + escalation triggers,
timeline risk + scope status, dependency health, action items for unblocking.

**Engineering Lead**: Technical complexity + debt, team capacity + workload,
implementation risks, code quality signals, resource allocation recommendations.

**Product Lead**: Feature delivery progress, user value + impact, backlog health +
prioritization, stakeholder alignment, go-to-market readiness.

### Extended (with --all flag)

**QE Lead**: Defect density + trends, test coverage gaps, quality risks by feature area,
regression signals, testing capacity.

**Architecture Lead**: System impact of changes, technical decision tracking,
integration point risks, scalability concerns, debt-to-feature ratio.

**DevSecOps Lead**: Security items, CI/CD pipeline health, operational readiness,
compliance concerns, infrastructure stability.

## Persona section template

```markdown
### {Persona Name} Perspective

**Summary**: {1-2 sentence assessment}
**Risk Level**: {GREEN|YELLOW|RED}

**Key Findings**:
1. {finding relevant to this persona}
2. {finding relevant to this persona}

**Metrics**:
| Metric | Value | Assessment |
|--------|-------|------------|
| {relevant metric} | {value} | {interpretation} |

**Recommendations**:
1. {actionable recommendation with ticket reference}
```

## Cross-persona synthesis

After individual sections:
- **Consensus risks**: issues flagged by 2+ personas.
- **Conflicting priorities**: where personas disagree.
- **Blind spots**: issues no persona flagged but data suggests.

## Executive summary

```markdown
## Executive Summary

**Sprint/Project**: {name}  **Status**: {ON TRACK|AT RISK|CRITICAL}  **Date**: {date}

### Key Metrics
| Metric | Value | Status |
|--------|-------|--------|
| Completion | {%}% ({done}/{total}) | {status} |
| Blocked    | {n} items | {status} |
| Velocity   | {value} | {trend} |

### Critical Items
1. {most important finding}

### Decisions Needed
- {decision needed from leadership}

### Recommendations
1. {top recommendation}
```

## Output formats

- **Default**: all three default personas inline.
- **--all**: include six personas.
- **--personas {list}**: specific personas only.
- **--output {dir}**: write per-persona files to directory.

## Quality standards

- **Perspective-appropriate**: each persona sees what matters to them.
- **Data-backed**: every finding references specific items.
- **Actionable**: recommendations are specific with ticket references.
- **Honest**: status reflects reality, not optimism.
- **Concise**: one page per persona max.
