# Test Type Taxonomy

Reference for the QE strategy skill. Defines the 10 canonical test types, their evidence requirements,
change-type selection matrix, and evidence gate verdict format.

---

## 1. Scenario / Workflow Testing

**What it tests**: End-to-end user journeys from entry point to outcome, verifying that the system
satisfies acceptance criteria as a whole.

**Evidence required**:
- Scenario file executed and exits 0 (or equivalent pass signal)
- All defined assertions in the scenario are satisfied
- Artifact log showing inputs, outputs, and intermediate state

**Applies when**: A new user-facing feature is added, a workflow step changes, or acceptance criteria
are updated.

---

## 2. Integration / Contract Testing

**What it tests**: Boundaries between components — API contracts, service interfaces, and data
exchange formats between producer and consumer.

**Evidence required**:
- Contract test suite passes for all consumers of the changed interface
- Response schema validated against schema definition (OpenAPI, JSON Schema, etc.)
- Error response codes and payloads match the documented contract

**Applies when**: An API endpoint is added or modified, a service dependency changes, or a shared
data format (request/response body, event payload) changes.

---

## 3. Visual / Interaction Testing

**What it tests**: Rendered UI appearance and user interaction flows — layout, component rendering,
state transitions, and accessibility attributes.

**Evidence required**:
- Visual diff or snapshot comparison passes (no unexpected regressions)
- Interactive flow (click, form submit, navigation) completes without JS errors
- Accessibility audit passes at the configured WCAG level (typically AA)

**Applies when**: A UI component is added or changed, CSS/styling is modified, or an interaction
pattern (modal, form, navigation) is updated.

---

## 4. Unit / Logic Testing

**What it tests**: Individual functions, methods, or modules in isolation — pure logic correctness,
branching behavior, and edge case handling.

**Evidence required**:
- All branches of the changed logic path are covered
- Boundary values (zero, null, max, min) have explicit assertions
- Mock/stub verifies that dependencies are called with correct arguments

**Applies when**: Business logic is added or changed, a guard clause or conditional branch is added,
or algorithmic behavior is modified.

---

## 5. Copy / Accuracy Testing

**What it tests**: Text content, labels, error messages, and data accuracy — that the system says
what it should say and displays what it should display.

**Evidence required**:
- All user-visible strings match the approved copy spec or design artifact
- Error messages are meaningful and contextually accurate
- Numeric values, dates, and formatted output match the expected representation

**Applies when**: User-visible text changes, error messages are added or updated, or localization/
formatting rules are modified.

---

## 6. Regression Testing

**What it tests**: Previously working behavior has not been broken by the change — the "do no harm"
verification.

**Evidence required**:
- Full existing test suite passes without modification
- Any test that was previously skipped or failing is triaged (not silently removed)
- Coverage delta does not decrease from the pre-change baseline

**Applies when**: Any change to existing code — required for all change types as a baseline gate.

---

## 7. Data / State Testing

**What it tests**: Data persistence, state transitions, and schema integrity — that data written is
data read, and state machines follow valid transitions.

**Evidence required**:
- Migration runs successfully on a representative dataset (forward and rollback)
- Data written in the new format is correctly read back
- Invalid state transitions are rejected with appropriate errors
- Existing data remains readable after schema change

**Applies when**: A database schema changes, a migration is added, a stateful object gains or loses
fields, or event sourcing/CQRS projections are modified.

---

## 8. Security Testing

**What it tests**: Authentication, authorization, input validation, and common vulnerability patterns
(injection, path traversal, privilege escalation).

**Evidence required**:
- Auth boundary tested: unauthenticated requests return 401/403
- Authorization tested: user A cannot access user B's resources
- Input fuzzing or validation test rejects malformed/adversarial input
- Static analysis security scan (SAST) passes with no new high/critical findings

**Applies when**: A new endpoint is added, authentication logic changes, user-controlled input is
processed, or data access patterns change.

---

## 9. Configuration / Wiring Testing

**What it tests**: Application startup, dependency injection, environment-specific configuration, and
that all components are correctly wired together.

**Evidence required**:
- Application starts cleanly in the target environment configuration
- Environment variable overrides apply correctly
- Feature flags resolve to expected values
- Required services are reachable (health check / smoke test)

**Applies when**: A configuration key is added or renamed, dependency injection bindings change,
environment-specific behavior is added, or infrastructure configuration (IaC) changes.

---

## 10. Performance / Resource Testing

**What it tests**: Response time, throughput, memory usage, and resource consumption under expected
and peak load conditions.

**Evidence required**:
- P95 response time is within the defined SLA under baseline load
- No memory leak observed over a sustained run (heap profile or RSS trend)
- Database query plan reviewed — no full table scans introduced
- Resource consumption (CPU, memory, I/O) within acceptable bounds

**Applies when**: A hot code path changes, a query or algorithm is modified, caching behavior
changes, or a new resource-intensive operation is introduced.

---

## Change-Type Selection Matrix

Map the change type to the minimum required test types. Regression testing is always required and
is omitted from the per-row list for brevity — assume it is always included.

| Change Type | Required Test Types |
|---|---|
| New endpoint | unit, integration, scenario, security, regression |
| Bug fix | unit, regression, scenario |
| Refactor | unit, regression |
| Schema / migration change | data/state, integration, regression |
| UI / component change | visual, scenario, regression |
| Config / wiring change | configuration, regression |
| New user-facing feature | scenario, unit, integration, visual, regression |
| Auth / permission change | security, unit, integration, regression |
| Performance optimization | performance, unit, regression |
| Copy / text change | copy/accuracy, regression |

**Reading the matrix**: Every type listed must produce passing evidence before the work is
considered done. The list is a minimum — add types when risk signals indicate additional coverage.

### A11y Note

UI changes always include an accessibility check as part of visual/interaction testing. Track it
separately if your project has explicit WCAG compliance requirements.

---

## Evidence Gate Verdict Format

Each test type produces a verdict. Collect all verdicts into the test requirement matrix for the
change set.

### Verdict Values

| Verdict | Meaning |
|---|---|
| `PASS` | Evidence collected, assertions satisfied, gate cleared |
| `FAIL` | Evidence collected, one or more assertions not satisfied |
| `N-A` | Test type does not apply to this change (must be justified) |
| `SKIP` | Applicable but deferred — requires explicit approval and a linked ticket |

### Per-Type Verdict Record

```
Test Type:     <type name>
Verdict:       PASS | FAIL | N-A | SKIP
Evidence:      <artifact reference — file, URL, command output>
Justification: <required for N-A or SKIP>
Reviewer:      <agent or human who evaluated the evidence>
```

### Gate Rules

1. A change is **done** only when all applicable types are `PASS`.
2. `N-A` requires a written justification. "Not applicable" with no reason is treated as `FAIL`.
3. `SKIP` requires explicit approval (human or gate reviewer). Skipped gates must be tracked.
4. `FAIL` on any type blocks merge. No exceptions without council escalation (complexity >= 6).

---

## Integration with Crew

The QE strategy phase uses this taxonomy to build a **test requirement matrix** for the project.

### How the Phase Uses the Taxonomy

1. **Signal analysis** — `smart_decisioning.py` identifies change signals (new endpoint, schema
   change, UI work, etc.) from the project description and code diff.
2. **Matrix construction** — The test-strategist agent maps each detected signal to required test
   types using the change-type selection matrix above.
3. **Evidence planning** — For each required type, the agent defines the specific evidence artifact
   and the command or tool that produces it.
4. **Gate assignment** — Each test type is assigned to the appropriate crew phase:
   - `unit`, `configuration` → build phase gate
   - `integration`, `data/state` → build + test phase gate
   - `scenario`, `visual`, `copy/accuracy` → test phase gate
   - `security`, `performance` → test phase gate (or dedicated phase if signals are strong)
   - `regression` → test phase gate (full suite)
5. **Gate reviewer routing** — Strategy gates at complexity 3+ route to a specialist subagent.
   Complexity 6-7 or any security signal escalates to council.

### Output Format

The test-strategist agent produces a matrix block in the phase artifact:

```
## Test Requirement Matrix

| Test Type | Required | Evidence Artifact | Phase Gate | Verdict |
|---|---|---|---|---|
| Scenario | yes | `/wg-test scenarios/...` exits 0 | test | pending |
| Unit | yes | `pytest tests/unit/` passes | build | pending |
| Integration | yes | contract suite passes | build | pending |
| Security | yes | SAST + auth boundary tests | test | pending |
| Regression | yes | full suite passes | test | pending |
| Visual | N-A | UI not changed | — | N-A |
```

Subsequent phases update the `Verdict` column as evidence is collected. The gate reviewer
evaluates the complete matrix before clearing each phase gate.
