# Evidence Framing (functional, not coverage)

Evidence is about proving the task did what it claims. Coverage percentages are gate
metrics — not facilitator metrics. The facilitator picks the MINIMUM set of evidence
artifacts that a reader could use to independently verify the change.

---

## Framing: input → output → observable analysis

For every test, name:

1. **Input** — what state or call triggers behavior.
2. **Output** — what the behavior produces (response, DB row, event, screenshot).
3. **Analysis** — what makes the output "correct" (assertion, diff, visual diff).

If you can't name all three for a test_type, don't include that test_type.

---

## test_types — when to include each

| Type            | Include when ...                                                              |
|-----------------|-------------------------------------------------------------------------------|
| `unit`          | logic branches > 1, pure functions, non-trivial data transformations.          |
| `integration`   | multiple modules coordinate (DB + service, queue + worker, client + server).   |
| `api`           | public or internal HTTP/gRPC endpoint contract is added or changed.            |
| `ui`            | rendered component or page is added or changed; include visual-before-after.   |
| `acceptance`    | user-facing flow exists; scripted end-to-end scenario validates the AC.        |
| `migration`     | schema change OR data transformation; include dry-run + rollback.              |
| `security`      | authN, authZ, crypto, secrets, input validation on trust boundary.             |
| `a11y`          | user-facing UI change; WCAG 2.1 AA minimum; keyboard + SR; contrast.           |
| `performance`   | hot path, expected change > 10% throughput or latency, new external dep.       |

Exclude a type if you can't name what observable signal it would produce. Don't add
`security` on a typo fix just because the login button is involved — add it only if
the change touches credentials, tokens, or auth state.

---

## evidence_required — choose the minimum

| Artifact                        | Proves ...                                                  |
|---------------------------------|-------------------------------------------------------------|
| `unit-results`                  | Logic branches behave as specified.                         |
| `integration-results`           | Modules coordinate correctly (real collaborators or test doubles). |
| `acceptance-report`             | End-to-end scenario matches AC from clarify.                |
| `screenshot-before-after`       | UI change rendered as intended; visual diff.                |
| `api-contract-diff`             | Contract change is what was designed; no unexpected breaks. |
| `migration-rollback-plan`       | State change is reversible; dry-run + rollback script.      |
| `compliance-traceability`       | Requirement → design → code → test → verification chain.    |
| `security-scan`                 | No new OWASP / secrets / dep-CVE findings on the diff.      |
| `performance-baseline`          | Before/after numbers with noise characterization.           |
| `a11y-report`                   | WCAG 2.1 AA check results with remediation notes.           |

Rules:

1. Every task with `test_required: true` MUST have ≥1 evidence artifact.
2. Every task with a `migration` test_type MUST have `migration-rollback-plan`.
3. Every task touching compliance-scoped surfaces MUST have `compliance-traceability`.
4. Every task with operational_risk HIGH SHOULD have `performance-baseline` on the hot
   path.
5. UI changes with user-facing impact HIGH SHOULD have both `screenshot-before-after`
   AND `a11y-report`.

---

## Anti-patterns (do not do)

- **Coverage percentages** — never include `"coverage >= 80%"` as evidence. Coverage is
  a gate metric, not a task artifact.
- **"Tests pass"** as evidence — too shallow. Require results artifacts tied to inputs.
- **Over-specifying docs-only tasks** — a docs typo does not need `unit-results`.
- **Under-specifying data-export tasks** — always include `compliance-traceability` and
  `api-contract-diff` for GDPR export endpoints, even if the code is "just a handler."
- **`acceptance-report` on internal refactors** — there is no user-visible behavior to
  accept; use `unit-results` + `integration-results` + `api-contract-diff`.

---

## Worked examples

### Typo in button label
- test_required: false
- test_types: []
- evidence_required: []
- reasoning: no behavior change; visual change on a single string is its own proof.

### `/users` 500 on empty query string (bugfix)
- test_required: true
- test_types: [unit, integration]
- evidence_required: [unit-results, integration-results]
- reasoning: regression test for the edge case (empty query) + integration test showing
  a 2xx response.

### CSV export feature
- test_required: true
- test_types: [unit, api, ui, acceptance]
- evidence_required: [unit-results, api-contract-diff, acceptance-report,
  screenshot-before-after]
- reasoning: generator unit tests, new endpoint contract, UI button, end-to-end export.

### JWT migration (cross-service)
- test_required: true
- test_types: [unit, integration, api, security, acceptance, performance]
- evidence_required: [unit-results, integration-results, api-contract-diff,
  security-scan, acceptance-report, compliance-traceability, performance-baseline,
  migration-rollback-plan]
- reasoning: full pyramid + compliance + rollback + perf baseline for token verification
  hot path.

### Nullable column add + backfill
- test_required: true
- test_types: [unit, integration, migration]
- evidence_required: [unit-results, integration-results, migration-rollback-plan]
- reasoning: migration-rollback-plan is the marquee artifact; functional tests cover
  read/write paths before and after.

### Internal refactor (no behavior change)
- test_required: true
- test_types: [unit]
- evidence_required: [unit-results]
- reasoning: existing unit tests should pass unchanged; behavior parity is the claim.

### README update for API key setup
- test_required: false
- test_types: []
- evidence_required: []
- reasoning: docs-only; no behavior.

### GDPR data-export endpoint
- test_required: true
- test_types: [unit, integration, api, security, acceptance]
- evidence_required: [unit-results, integration-results, api-contract-diff,
  security-scan, acceptance-report, compliance-traceability]
- reasoning: privacy-sensitive + new API + auditable; traceability is mandatory.
