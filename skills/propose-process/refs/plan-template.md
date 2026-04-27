# `process-plan.md` template

Write this artifact to the project directory (typically
`~/.something-wicked/wicked-garden/local/crew/<project>/process-plan.md` via
DomainStore, or the path returned by `resolve_path.py crew`).

The plan is mirrored into the task chain's metadata but exists as its own readable
artifact for humans and audit trails.

---

## Template

```markdown
# Process Plan — <project-slug>

**Created**: <ISO timestamp>
**Facilitator**: propose-process v1
**Mode**: propose | re-evaluate | yolo
**Chain id**: <project-slug>.root

## 1. What this work is

<2-3 sentences in your own words. Name the user-facing outcome, the surface area, and
any risk words heard.>

## 2. Priors consulted

- [<path>] — <one sentence of why this matters>
- [<path>] — <one sentence>
- [<path>] — <one sentence>

(If search returned 0 results: "No priors found — treating novelty as HIGH.")

## 3. Factor scoring

> **Direction**: this table renders the user-facing `risk_level` field
> (`low_risk` / `medium_risk` / `high_risk`) — NOT the backward-compat
> `reading` field, which is inverted (HIGH = safest). See #627.

| Factor              | Risk level | One-sentence reasoning                       |
|---------------------|------------|----------------------------------------------|
| Reversibility       | low_risk / medium_risk / high_risk | <one sentence>         |
| Blast radius        | low_risk / medium_risk / high_risk | <one sentence>         |
| Compliance scope    | low_risk / medium_risk / high_risk | <one sentence>         |
| User-facing impact  | low_risk / medium_risk / high_risk | <one sentence>         |
| Novelty             | low_risk / medium_risk / high_risk | <one sentence>         |
| Scope effort        | low_risk / medium_risk / high_risk | <one sentence>         |
| State complexity    | low_risk / medium_risk / high_risk | <one sentence>         |
| Operational risk    | low_risk / medium_risk / high_risk | <one sentence>         |
| Coordination cost   | low_risk / medium_risk / high_risk | <one sentence>         |

## 4. Specialists selected

- `<agent-name>` — <one-sentence why this specialist>
- `<agent-name>` — <one-sentence why>
- ...

## 5. Phases selected

1. `<phase>` — <one-sentence why>
2. `<phase>` — <one-sentence why>
3. ...

## 6. Rigor tier

**<minimal | standard | full>** — <one-sentence why>

## 7. Complexity estimate

**<0-7>** — <one-sentence why>

## 8. Open questions (if any)

1. <question>
2. <question>

(If no open questions: "None — plan proceeds without clarification.")

## 9. Task chain

Each phase should include a gate task at the end of the phase's task block.
Gate task `event_type` is `"gate-finding"`; gate name comes from the gate catalog.

| # | Task title                              | Phase          | Gate name            | Specialist            | blockedBy | test_required | evidence_required |
|---|-----------------------------------------|----------------|----------------------|-----------------------|-----------|---------------|-------------------|
| 1 | ...                                     | clarify        | —                    | requirements-analyst  |           | false         | []                |
| 2 | Gate: requirements-quality              | clarify        | requirements-quality | (reviewer at approve) | [1]       | false         | []                |
| 3 | ...                                     | design         | —                    | solution-architect    | [2]       | false         | []                |
| 4 | Gate: design-quality                    | design         | design-quality       | (reviewer at approve) | [3]       | false         | []                |
| 5 | ...                                     | build          | —                    | backend-engineer      | [4]       | true          | [unit-results]    |
| 6 | Gate: code-quality                      | build          | code-quality         | (reviewer at approve) | [5]       | false         | []                |
| ...                                                                                                                                                                |

The six phase gate names are: `requirements-quality`, `design-quality`, `testability`,
`code-quality`, `evidence-quality`, `final-audit`. Reviewer assignment is deferred to
approve time via `gate-policy.json` — do NOT embed reviewer names in the plan.

## 10. Re-evaluation log

(This section is retained for readability. Structured re-eval data is written to
`phases/{phase}/reeval-log.jsonl` as JSONL — see `refs/re-eval-addendum-schema.md`.)

A plain-English summary may be appended here after each phase-end re-eval fires:

- **<ISO timestamp>** — triggered by task <#> completion. Pruned task <#>
  (<reason>). Added task <#>: "<title>" (<reason>). Re-tiered task <#> from
  standard to full (<reason>).
```

---

## Where to store it

Use `DomainStore` via the crew domain's `resolve_path.py`:

```bash
PLAN_DIR=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_path.py" crew)
mkdir -p "${PLAN_DIR}/<project-slug>"
# Write process-plan.md to "${PLAN_DIR}/<project-slug>/process-plan.md"
```

---

## Writing discipline

- Keep it readable. This is a working document, not a specification.
- Prose over bullets for factor scoring and "what this work is."
- Tables for the task chain, factor summary, specialists.
- Do not duplicate the SKILL.md itself — the plan is the decision, not the rubric.
- Re-evaluation log is APPEND-ONLY — never rewrite prior entries.
