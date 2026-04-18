# Onboarding Guide — Output Template

## Onboarding Plan for {developer_name}

**Project**: {project_name}
**Team Health**: {HEALTHY | DEGRADED | CRITICAL}
**Sprint Status**: {in_progress_count} in flight, {blocked_count} blocked

### Team Overview
{Brief team description — mission, team size, working hours, location}

### Current Focus Areas
{What the team is working on this sprint/quarter}

---

### Week 1: Orientation

- [ ] Read the [codebase-narrator] output for this project
- [ ] Review architecture documentation at {path}
- [ ] Set up local development environment (see `README.md` Quick Start)
- [ ] Meet key team members (see "People to Connect With" below)
- [ ] Attend sprint ceremonies (standup, planning, retro) as observer
- [ ] Pick first task: **{recommended_task}** — {why good first task}

**End-of-week check-in**: 30 minutes with {manager / tech lead} to align on what
clicked, what didn't, and adjust plan.

### Week 2: First Contribution

- [ ] Complete first task with pair programming
- [ ] Submit first PR and go through review process
- [ ] Attend a code review for someone else's PR (observer)
- [ ] Document one thing you learned (update onboarding docs)
- [ ] Optional: shadow an on-call shift

**End-of-week check-in**: 30 minutes on PR feedback, velocity, unblockers.

### Week 3: Independence

- [ ] Take on a medium-complexity task
- [ ] Review someone else's PR as a reviewer
- [ ] Identify one improvement opportunity (tech debt, doc gap, process friction)
- [ ] Share onboarding feedback (what worked, what didn't, what to change)
- [ ] Optional: take a small ops task (runbook walk-through, alert triage)

**End-of-week check-in**: retro on the full onboarding plan. Revise for next hire.

---

### Recommended Starting Points

1. **{task}** — {why this is a good first task}
2. **{task}** — {why this is a good second task}
3. **{task}** — {why this is a good third task}

### Key Systems

| System | Purpose | Complexity | Read First |
|--------|---------|------------|------------|
| {name} | {purpose} | LOW / MED / HIGH | {path} |

### Team Patterns

- **Code review**: {process — e.g. 1 engineering review + 1 domain review; 48h SLA}
- **Testing**: {approach — e.g. unit + integration required; e2e on feature branches}
- **Deployment**: {frequency — e.g. continuous; canary 10% → 50% → 100%}
- **Branching**: {e.g. trunk-based with short-lived feature branches}
- **On-call**: {e.g. weekly rotation; primary + secondary; runbooks in `runbooks/`}
- **Communication**: {primary channel — e.g. `#team-X` on Slack; decisions logged in `docs/adr/`}

### People to Connect With

| Person | Role | Reach Out For |
|--------|------|---------------|
| {name} | {role} | {topics} |
| {name} | Engineering Manager | 1:1s, career, blockers |
| {name} | Tech Lead | Architecture, code review |
| {name} | Product Manager | Requirements, priorities |
| {name} | On-call Coordinator | Incident process, runbooks |

### Onboarding Risks

| Risk | Mitigation |
|------|------------|
| {risk} | {mitigation} |
| Env setup takes > 1 day | Pair with {name} on bootstrap |
| Legacy system with no docs | Shadow {name}; use codebase-narrator |

### Feedback Loop

- **Day 3**: quick pulse check on environment + docs clarity
- **Day 7**: first-week retro
- **Day 14**: first-contribution retro
- **Day 21**: full onboarding retro, update this template for next hire

### Resources

- Architecture overview: `docs/ARCHITECTURE.md`
- Runbooks: `runbooks/`
- Decision log: `docs/adr/`
- Team glossary: `docs/GLOSSARY.md`
