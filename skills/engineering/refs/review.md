# review — senior engineering code review rubric

Bulletproof Standards (R1–R6 + T1–T6), severity guidelines, persona routing, and output format.
Use `engineering:review` for code-level review; use `engineering:arch` for component/system architecture review.

## Bulletproof Coding Standards — R1–R6

These are enforcement directives, not suggestions. Flag every violation. No exceptions.

- **R1: No Dead Code** — Flag unused imports, functions, variables, types, and unreachable branches.
  Dead code decays, misleads, and costs. Delete it, or add a comment explaining why it stays.

- **R2: No Bare Panics** — Every function that can fail MUST return an error type or throw within
  a handled context. No `panic()`, no unhandled exceptions, no `unwrap()` in production paths,
  no `process.exit(1)` in library code. If it can fail, the signature must show it.

- **R3: No Magic Values** — All constants must be named. No bare numbers, strings, or config values
  in logic. Examples to flag: `if retries > 3`, `timeout: 5000`, `color: '#1a1a2e'`, `z-index: 9999`.
  Demand a named constant with a comment explaining the choice.

- **R4: No Swallowed Errors** — Every error catch must handle or propagate. Empty catch blocks,
  `_ = err`, `pass`, and `console.log(err)` without user feedback are violations. "Log and continue"
  counts only if the log includes the error detail and the function's contract allows partial failure.

- **R5: No Unbounded Operations** — All I/O (HTTP calls, DB queries, file reads, queue polls) MUST
  have timeouts. No indefinite `await`, no missing `context.WithTimeout`, no fetch without
  `AbortController` or `signal`, no infinite retries without backoff and ceiling. External calls
  need a timeout AND a failure mode.

- **R6: No God Functions** — Functions over ~60 lines need extraction. More than 3 nesting levels
  needs early returns or decomposition. If you can't describe what a function does in one sentence,
  it does too much.

## Bulletproof Testing Standards — T1–T6

Apply when `--focus tests` or when reviewing test files directly.

- **T1: Determinism** — No date/time dependencies without injected clocks. No random without seed.
  No order-dependent test suites. Same input → same result, always.

- **T2: No sleep-based sync** — No `sleep(200)` or `time.Sleep` as a synchronization mechanism.
  Use explicit waits, callbacks, events, or polling with a timeout and an error on timeout.

- **T3: Isolation** — Each test sets up and tears down its own state. No shared mutable globals
  between tests. No dependency on test execution order.

- **T4: Single assertion focus** — One logical assertion per test (multiple asserts on the same
  subject is fine). Tests that assert five unrelated things make failures hard to diagnose.

- **T5: Descriptive names** — Test name should read as a sentence: `test_returns_empty_list_when_no_users`,
  not `test_user_3`. Name should encode: subject + scenario + expected outcome.

- **T6: Provenance** — Each test should trace to a requirement, acceptance criterion, or bug ID.
  Tests without clear purpose are maintenance debt. Note the gap as LOW severity.

## Agent overstepping — always flag

- Unrelated edits outside stated scope
- Commented-out code left in the diff
- Over-engineering / speculative generality (YAGNI violations)
- Scope creep: restructuring files not mentioned in the task
- Refactoring mixed into a bug fix (makes rollback impossible)

## Focus lanes (applied when `--focus` given)

| Flag | Deepen these areas |
|------|-------------------|
| `--focus security` | Auth/authz, input validation, SQL injection, credential handling, OWASP Top 10 |
| `--focus performance` | Hot paths, N+1 queries, missing indexes, unbounded ops, caching opportunities |
| `--focus patterns` | DRY, SOLID, naming, abstractions, module boundaries, coupling |
| `--focus tests` | T1–T6 standards, coverage gaps, flakiness risks, missing edge cases |

## Persona routing (`--persona <name>`)

1. Resolve the persona:
   ```bash
   PERSONA_JSON=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/persona/registry.py --get "${persona_name}" --json 2>/dev/null)
   ```
2. If found: apply the review through the persona's lens — flag what that persona's frame of
   reference would catch (e.g. a security-focused persona finds auth gaps a general review might
   rate LOW).
3. If not found: warn "Persona '{name}' not found — using default review lens" and fall through.

## wicked-scenarios (`--scenarios`)

For each Critical or High finding, emit a wicked-scenarios regression block:

```yaml
scenario: "{title describing the bug/issue}"
given: "{precondition}"
when: "{action that triggers it}"
then: "{expected behavior after fix}"
file: "{file}:{line}"
severity: "Critical|High"
```

## Standard output format

```markdown
## Engineering Review: {scope or file}

### Strengths
- {good pattern with file:line evidence}

### Issues

| Severity | Rule | Issue | Location | Recommendation |
|----------|------|-------|----------|----------------|
| CRITICAL/HIGH/MEDIUM/LOW | R1–R6 or T1–T6 | {description} | `{file}:{line}` | {concrete fix} |

### Architecture Notes
{Any structural observations — use engineering:arch for full analysis}

### Maintainability Concerns
{Long-term maintenance considerations}

### Agent Overstepping
{Any out-of-scope edits, commented-out code, or scope creep found — cite file:line}

### Recommendations
1. {Highest priority with rationale}
2. {Secondary}
```

## Severity guidelines

- **CRITICAL**: Will cause data loss, security breach, or production outage
- **HIGH**: Will cause bugs, broken patterns, or major maintainability problems
- **MEDIUM**: Should fix; will accumulate tech debt; non-blocking
- **LOW**: Nice to have; style; minor improvements; provenance gaps

## Cross-specialist referrals

- Security deep-dive → `wicked-garden:platform:security-engineer`
- Testing strategy → `wicked-testing:test-strategist`
- Architecture / structural trade-offs → `wicked-garden:engineering:solution-architect`
- Frontend specifics (React hooks, CSS, a11y), backend specifics (DB, API design,
  queues): handled inline — apply the relevant checklist from this skill's refs.
