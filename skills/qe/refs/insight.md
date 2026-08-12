---
phase_relevance: ["review", "operate"]
archetype_relevance: ["review", "ship", "incident"]
---

<!-- Action ref of the `wicked-garden-qe` router (Phase 6b port of
     wicked-testing's `insight` orchestrator). Loaded on demand
     via Read() from the router's `insight` action — not a skill. -->


# qe insight — full playbook

The read-only lens on wicked-testing's ledger. Built on the fixed-SQL oracle
so answers are auditable, not LLM-guessed.

## Usage

```
wicked-garden-qe insight "<question>" [--project <name>] [--json]
```

Flags `--project`, `--status`, `--since`, and `--json` are honored as filters
on the underlying oracle queries.

## When to use

- "Has scenario X passed in the last 24 hours?"
- "What's the flake rate for the auth suite?"
- "Give me a run report for PR #123"
- "Show me the last 10 runs of login-with-bad-creds"
- "Which scenarios haven't run in a month?"
- "Which code paths are still untested?"
- "Run an exploratory charter on the new checkout flow."

## How it dispatches

| Input                                           | Dispatch                                     |
|-------------------------------------------------|----------------------------------------------|
| A question, natural language                    | `wicked-garden-qe-test-oracle` (fixed SQL)     |
| "generate a report" / "run summary"             | Oracle rows rendered as a markdown summary (no new SQL); add Tier-2 specialists when the report needs them |
| "find flaky tests"                              | `wicked-garden-qe-flaky-test-hunter`           |
| "find untested legacy code"                     | `wicked-garden-qe-coverage-archaeologist`      |
| "run an exploratory session"                    | `wicked-garden-qe-exploratory-tester`          |
| "audit production quality" / post-deploy read   | `wicked-garden-qe-production-quality-engineer` |
| Unknown question                                | Oracle returns the supported question list   |
| "domain health" / "row counts" / "schema version"  | `wicked-garden-qe-test-oracle` → `row_counts` / `schema_version` queries |
| "what tasks are open" / "tasks for X"           | `wicked-garden-qe-test-oracle` → `tasks_by_status` / `tasks_for_project` |

### Dispatch block (executable)

Every id in the tables above is a forked worker skill (`context: fork`) —
invoke it with the Skill tool so it runs in an isolated context:

```
Skill(
  skill="wicked-garden-qe-test-oracle",
  args="""Answer the question below against the wicked-testing ledger.

## Question
{natural-language question}

## Optional filters (from flags)
- project: {name or null}
- scenario: {name or null}
- since: {ISO date or null}

## Instructions
1. Route the question to a named query in wicked-ledger's oracle-query
   library by keyword matching. NEVER synthesize SQL.
2. If no match, return the list of supported question patterns and exit —
   do not fabricate results.
3. If better-sqlite3 is unavailable, return ERR_SQLITE_UNAVAILABLE exactly.
4. Run the named query with bound parameters. Return rows as JSON or markdown
   table (per --json flag).
5. Include the query name used so the caller can audit.

Do NOT perform state mutations. Do NOT emit bus events."""
)
```

Swap the `skill` id to the specialist when the trigger matches something the
oracle doesn't cover — flake detection, coverage archaeology, and exploratory
sessions all have dedicated worker skills.

## Tier-2 specialists this skill routes to

Insight is heavier on Tier-2 than other Tier-1 skills because most history
questions have a specialist answer:

| Trigger                                                  | Specialist                                  |
|----------------------------------------------------------|---------------------------------------------|
| Flake rate / quarantine proposal                         | `wicked-garden-qe-flaky-test-hunter`          |
| Coverage gaps, dead-code detection                       | `wicked-garden-qe-coverage-archaeologist`     |
| Charter-driven exploratory session                       | `wicked-garden-qe-exploratory-tester`         |
| Post-deploy quality, canary read                         | `wicked-garden-qe-production-quality-engineer` |
| Observability assertion audit (trace/log/metric coverage)| `wicked-garden-qe-observability-test-engineer` |
| Contract drift report (historical / consumer-side)       | `wicked-garden-qe-contract-testing-engineer`  |
| "Most impactful tests for HEAD" / TIA lookup             | `wicked-garden-qe-test-impact-analyzer`       |
| "Should we ship v2.4.0?" / release readiness             | `wicked-garden-qe-release-readiness-engineer` |
| "Any incident without a regression scenario yet?"        | `wicked-garden-qe-incident-to-scenario-synthesizer` |

## Oracle safety

The oracle never generates SQL. It keyword-matches the question to one of the
named parameterized queries in `wicked-ledger`'s oracle-query library.
If nothing matches, it returns the list of supported questions — it never
guesses. See also `wicked-ledger`'s DomainStore for the
table-name allowlist that backs the CRUD layer.

## Output

- The answer (JSON or markdown table depending on caller)
- The query name used (so the reader can audit)
- A link to the ledger file if deeper inspection is warranted

This skill does not emit bus events — it is read-only and should not mutate
state.

## Legacy invocations (absorbed in 0.4.0)

`wicked-garden-qe` insight is the single read-only door to the ledger. What used to be separate
commands are now questions you ask it (routing per the dispatch table above):

| Old command | Ask insight instead |
|-------------|---------------------|
| `stats`     | "domain health" / "row counts" / "schema version" — routes to the `row_counts`, `schema_version`, `recent_runs` oracle queries |
| `report`    | "generate a report for <project/scope>" — oracle rows rendered as a markdown summary |
| `oracle`    | any plain-language data question — this *is* the oracle; `wicked-garden-qe` insight was always built on it |

> **`tasks` is removed, not absorbed.** `wicked-garden-qe` insight is read-only and will not
> create or mutate tasks. Existing task rows remain queryable here
> ("what tasks are open?", "tasks for <project>") via the `tasks_by_status`
> and `tasks_for_project` oracle queries. Task *creation/update* via a command
> is gone in 0.4.0 — use the `DomainStore` API (`import { createDomainStore } from "wicked-ledger"`) directly
> if a workflow needs it.

## References

- `docs/INTEGRATION.md` (wicked-testing npm package)
- `../../qe-test-oracle/SKILL.md`
- `wicked-ledger` oracle-queries (consumed dependency — query catalog)

## wicked-ledger resolution

`wicked-ledger` (npm) is the QE data layer — DomainStore, oracle queries, and
manifest building. Import-style snippets above must run where the package
resolves: the target project's `node_modules` (`npm i --no-save wicked-ledger`)
or any directory with it installed. The pinned range lives in
`.claude-plugin/plugin.json` → `wicked_ledger_version`.
