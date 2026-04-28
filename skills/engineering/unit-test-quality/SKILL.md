---
name: unit-test-quality
description: |
  Language- and framework-neutral guard against useless unit tests — the kind
  that pass forever, never catch regressions, and inflate coverage without
  protecting behavior. Provides two complementary thought-experiment filters
  (execution + behavior), a pre-write self-check, a taxonomy of seven recurring
  anti-patterns (tautological, assertion-free, implementation mirror, framework
  retest, constant verification, sleep-coupled, exception-swallowing), and a
  one-line decision rule per pattern.

  Use when: writing a new unit test, reviewing a test diff, auditing a suite
  with high coverage but low confidence, "is this test worth keeping",
  "why didn't our tests catch that bug", before approving a PR that adds tests,
  pairing a test with a bug fix, "this test feels redundant".
status: stable
portability: portable
---

# Unit Test Quality

A test you cannot break by changing the system under test (SUT) is not a test —
it is dead weight. This skill exists because suites grow faster than they shrink,
and "100% coverage" is no defense against a suite that asserts the wrong things.

## Two complementary filters

No single mechanical filter catches every useless test — each anti-pattern
below has its own diagnostic. But two thought experiments catch the most common
cases and are language-neutral. Apply them in order; if either says "cut," you
are looking at a test that does not earn its keep.

### Filter A — execution check

> **If I replace the body of the SUT with a force-fail (`throw` / `raise` / `panic` / equivalent), does the test still pass?**

- **Still passes** → the test never exercised the SUT at all. Cut it (it is pure coverage theater, see #2 assertion-free, #4 framework retest).
- **Now fails** → the test at least *invokes* the SUT. Move to Filter B.

### Filter B — behavior check

> **If I replace the body of the SUT with a no-op stub returning sensible defaults (zero, null/None, empty collection, default-constructed value), does the test still pass?**

- **Still passes** → the test asserts nothing the SUT actually computes; the assertion would hold against an empty stub. Cut it (typically #5 constant verification or #4 framework retest).
- **Now fails** → the test depends on SUT-derived behavior. Likely worth keeping, but still apply the per-pattern rules below.

The filters are first-cut diagnostics — both can pass on #1 tautological (assertion mirrors mock input), #3 implementation mirror (assertion locks structure, not behavior), #6 sleep-coupled (timing flake is orthogonal), and #7 exception-swallowing (assertion-count guards are required regardless). Use the per-pattern decision rules below for those.

## The seven useless-test anti-patterns

### 1. Tautological — asserts what the mock was told to return

```
when(repo.find(1)).thenReturn(user);
result = service.fetch(1);
assert(result == user);   // Tests that the mock was wired correctly. The
                          // production fetch() could be `return repo.find(id)`
                          // OR `return repo.find(id).asJson().broken()` — this
                          // test cannot distinguish.
```

**Decision rule:** if the assertion is about a value you handed to a mock, the
test asserts mock plumbing, not behavior. Replace with a contract assertion
(state changed, side-effect emitted, derived value computed).

### 2. Assertion-free — "no exception thrown" is the only signal

```
test("processes order", () => {
  service.process(order);            // No assertion. Coverage counter ticks.
});
```

**Decision rule:** every test must contain a positive assertion against an
observable outcome. If the only thing the test proves is "this line executed",
delete it — coverage tools already prove that.

Variants to catch: `expect(x).toBeDefined()`, `expect(x).not.toBeNull()`,
`assert x is not None`, `assertNotNull(x)`. These are coverage assertions, not
behavior assertions.

### 3. Implementation mirror — asserts the structure of the code, not its outcome

```
expect(component.props).toEqual({a: 1, b: 2, c: 3, d: 4, e: 5});
```

**Decision rule:** snapshot tests and full-object equals tests rot — they catch
*every* change, including refactors that preserve behavior. Assert the
*minimum* set of fields that prove the contract. If the test must update every
time the SUT is touched, the test is locking in implementation, not behavior.

### 4. Framework retest — asserts that the framework still works

```
test("ORM saves user", () => {
  user = User.create({name: "x"});
  assert(User.find(user.id).name == "x");   // Tests Rails / Django / Hibernate.
});
```

**Decision rule:** the framework's test suite covers this. If your test would
also pass against an empty stub of *your* code, it is a framework test. Move
it to integration tests if the wiring is non-trivial; otherwise delete it.

### 5. Constant verification — tests with no logic

```
test("getter returns name", () => {
  user = new User("alice");
  expect(user.name).toBe("alice");
});
```

**Decision rule:** if the SUT contains no branches, no transformations, no
side-effects, and no derivations, there is nothing to test. Generated getters,
data-class field access, and one-line returns of constants do not need unit
tests.

### 6. Sleep-coupled — uses `sleep`, `setTimeout`, or wall-clock waits to "stabilize"

```
service.startBackground();
sleep(500);                  // Hopes the background work finished.
expect(state).toBe("done");
```

**Decision rule:** any test using a hardcoded delay is non-deterministic. Either
the test sometimes finishes before the SUT (false fail), sometimes finishes
exactly on the boundary (flake), or runs unnecessarily slowly (waste). Replace
with: a deterministic clock, an explicit completion signal, or a poll-with-timeout
over a real condition (not a sleep).

### 7. Exception-swallowing — try/catch hides the failure

```
test("handles bad input", () => {
  try { service.process(null); } catch (e) { /* expected */ }
});
```

**Decision rule:** assertions that depend on a `catch` block being entered must
*also* assert the catch was entered (`expect.assertions(N)` in Jest, `try…else` in
Python with a fail-the-test in `else`). A bare `catch` that swallows everything
makes the test pass even when the SUT fails to throw at all.

## Pre-write self-check (use before adding a new test)

Run through these in order. Stop at the first "no" — that is the work to do
before writing the test.

1. **What contract am I asserting?** State it in one sentence: input → expected
   observable outcome. If you cannot, you are not yet ready to write the test.
2. **Could this test pass against a broken SUT?** Mentally apply Filter A
   (replace SUT body with a force-fail) and Filter B (replace SUT body with a
   no-op default-returning stub). If the test passes either filter, stop and
   reconsider what you are asserting.
3. **Is the assertion about behavior or about plumbing?** Behavior: state
   changed, value derived, event emitted, error raised with specific shape.
   Plumbing: mock was called, function exists, framework worked.
4. **Is there exactly one logical assertion?** Multiple assertions about the
   same outcome are fine; multiple unrelated outcomes mean multiple tests.
5. **Is the test deterministic without sleeps?** If it depends on timing,
   reach for a fake clock or a completion signal, not a delay.
6. **Will I have to update this test on every refactor?** If yes, it is asserting
   implementation, not behavior. Narrow the assertion.
7. **Does the test name describe the behavior?** "test_user_creation" is a
   coverage label. "rejects user creation when email is missing" is a contract.

## Reviewer rubric (use during PR review of new tests)

For each new test in the diff:

- Read the test name. Does it state a contract or a code path? Contract → continue. Code path → flag.
- Read the assertion(s). Are they against observable outcomes the SUT controls? Yes → continue. No → flag.
- Apply Filter A mentally. Would the test fail if the SUT body became a force-fail (throw/raise/panic)? Yes → continue. No → flag (#2 assertion-free or #4 framework retest).
- Apply Filter B mentally. Would the test fail if the SUT body became a no-op stub returning defaults? Yes → likely keep. No → flag (#5 constant verification or #4 framework retest).
- If the test uses a mock: does the assertion verify *interaction the SUT chose to make*, not *value the test handed in*? Verifies SUT decision → keep. Echoes test input → flag (#1 tautological — neither filter catches this; structural inspection only).
- If the test contains `sleep`, `setTimeout(..., N)`, `Thread.sleep`, `time.sleep`, `await delay`, or any wall-clock-based wait: flag (#6 sleep-coupled). Replace with fake timers / virtual clock, an explicit completion signal/promise, or a poll-with-timeout over a real condition — never with `setTimeout(..., 0)` (which is a macrotask, not deterministic).

## What this skill does not cover

- **Integration / E2E tests** — different rules (real dependencies, slower feedback, broader contracts). Use the `integration` skill.
- **Property / fuzz testing** — requires its own taxonomy (shrinking, generators, invariants). Out of scope here.
- **Mutation testing** — verifies the *suite* catches bugs by mutating the SUT. Use the `mutation-test-engineer` agent for that audit; this skill prevents the bad tests in the first place.
- **Test runner / CI ergonomics** — flake quarantine, retry policy, parallel isolation. See the `flaky-test-hunter` agent.

## Why this is one skill across all languages

The seven anti-patterns above show up in pytest, Jest, Vitest, JUnit, RSpec,
xUnit, Go's `testing`, Rust's `#[test]`, and every framework that has ever
shipped. The syntax differs; the failure mode is identical. Keeping the rules
language-neutral is what makes this skill durable — any new framework inherits
the same filters the day it is adopted.
