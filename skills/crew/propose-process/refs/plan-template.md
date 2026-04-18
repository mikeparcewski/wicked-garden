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

| Factor              | Reading | One-sentence reasoning                          |
|---------------------|---------|-------------------------------------------------|
| Reversibility       | LOW/MED/HIGH | <one sentence>                             |
| Blast radius        | LOW/MED/HIGH | <one sentence>                             |
| Compliance scope    | LOW/MED/HIGH | <one sentence>                             |
| User-facing impact  | LOW/MED/HIGH | <one sentence>                             |
| Novelty             | LOW/MED/HIGH | <one sentence>                             |
| Scope effort        | LOW/MED/HIGH | <one sentence>                             |
| State complexity    | LOW/MED/HIGH | <one sentence>                             |
| Operational risk    | LOW/MED/HIGH | <one sentence>                             |
| Coordination cost   | LOW/MED/HIGH | <one sentence>                             |

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

| # | Task title                             | Phase          | Specialist            | blockedBy | test_required | test_types | evidence_required |
|---|----------------------------------------|----------------|-----------------------|-----------|---------------|------------|-------------------|
| 1 | ...                                    | clarify        | requirements-analyst  |           | false         | []         | []                |
| 2 | ...                                    | design         | solution-architect    | [1]       | false         | []         | []                |
| 3 | ...                                    | build          | backend-engineer      | [2]       | true          | [unit,api] | [unit-results, api-contract-diff] |
| ...                                                                                                                                                |

## 10. Re-evaluation log

(Appended when `re-evaluate` mode fires. Each entry records: timestamp, trigger task,
pruned/augmented/re-tiered tasks with one-sentence WHY each.)

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
