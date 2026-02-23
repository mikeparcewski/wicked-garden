# wicked-qe

Quality engineering that watches every file you write and nudges you for test coverage in real time — so you ship with tests, not after.

## Quick Start

```bash
# Install
claude plugin install wicked-qe@wicked-garden

# Generate test scenarios from an existing module
/wicked-qe:scenarios src/auth/

# Create a full test plan before writing code
/wicked-qe:qe-plan "User authentication with OAuth2"
```

## Workflows

### Shift-left: generate tests before writing implementation

```bash
# Start from requirements
/wicked-qe:scenarios requirements/user-registration.md

# Get a prioritized test plan
/wicked-qe:qe-plan "Feature: user registration with email verification"
```

The test-strategist agent produces a risk-prioritized scenario list:

```
TEST PLAN: User Registration with Email Verification

Risk Areas (prioritized):
  CRITICAL  Email uniqueness — duplicate accounts cause auth failures downstream
  HIGH      Verification token expiry — tokens must expire, not silently reuse
  HIGH      Password hashing — must not store plaintext under any code path
  MEDIUM    Rate limiting — registration endpoint brute-forceable without it
  LOW       Form validation — client-side validation bypassable

Scenarios generated: 12
  - registration-happy-path.md
  - duplicate-email-rejection.md
  - token-expiry-flow.md
  - password-hash-verification.md
  - rate-limit-enforcement.md
  ...
```

Then generate the test code:

```bash
/wicked-qe:automate src/registration/ --framework jest
```

### Real-time coverage nudges while you code

wicked-qe installs a `PostToolUse` hook on every `Write` and `Edit` call. When you modify a file that lacks test coverage, you get a nudge before you move on:

```
[wicked-qe] You edited src/auth/token.ts — no test file found for this module.
Consider: /wicked-qe:scenarios src/auth/token.ts
```

The hook tracks all files changed during the session so it only nudges once per file, not on every save.

### Pre-PR quality review

```bash
# Review test quality and find coverage gaps
/wicked-qe:qe-review tests/ --focus coverage

# Full quality gate across code and tests together
/wicked-qe:qe src/
```

The code-analyzer agent reports:

```
QE REVIEW: tests/unit/

Coverage gaps found:
  src/payment/refund.ts       — no unit tests (high risk: financial logic)
  src/auth/session.ts         — missing expiry edge cases
  src/api/upload.ts           — no error path coverage

Test quality issues:
  tests/unit/user.test.ts     — assertions too broad (toBeDefined vs toEqual)
  tests/unit/order.test.ts    — no arrange/act/assert structure

Recommendation: Address financial logic gap before merging.
```

### Three-agent acceptance testing (evidence-gated)

```bash
/wicked-qe:acceptance scenarios/checkout-flow.md
```

Three independent agents handle write, execute, and review — eliminating false positives from self-grading:

```
Writer   → reads implementation, designs assertions, finds spec ambiguities
Executor → runs tests, captures artifacts, records everything (no judgment)
Reviewer → evaluates evidence independently, cites specific artifacts, attributes causes
```

Verdict is only PASS when the Reviewer can cite concrete evidence from the Executor's artifacts.

## Commands

| Command | What It Does | Example |
|---------|-------------|---------|
| `/wicked-qe:scenarios` | Generate test scenarios from code or requirements | `/wicked-qe:scenarios src/checkout/` |
| `/wicked-qe:qe-plan` | Create a risk-prioritized test strategy and plan | `/wicked-qe:qe-plan "Payment processing flow"` |
| `/wicked-qe:automate` | Generate test code from scenarios | `/wicked-qe:automate src/api/ --framework pytest` |
| `/wicked-qe:qe-review` | Find coverage gaps, quality issues, and risk areas in existing tests | `/wicked-qe:qe-review tests/unit/` |
| `/wicked-qe:qe` | Full quality review across code and delivery lifecycle | `/wicked-qe:qe src/` |
| `/wicked-qe:acceptance` | Evidence-gated acceptance testing with three-agent separation | `/wicked-qe:acceptance scenarios/checkout.md` |

## Agents

| Agent | Focus |
|-------|-------|
| `test-strategist` | Scenario generation, risk-based prioritization, coverage strategy |
| `test-automation-engineer` | Test code generation in Jest, pytest, JUnit, and more; CI/CD integration |
| `risk-assessor` | Security, reliability, and operational risk identification |
| `code-analyzer` | Static analysis for testability, coverage gaps, quality metrics |
| `tdd-coach` | Red-green-refactor guidance, test-first development practices |
| `acceptance-test-writer` | Designs acceptance test plans from scenarios and implementation code |
| `acceptance-test-executor` | Runs tests and captures all artifacts without making pass/fail judgments |
| `acceptance-test-reviewer` | Evaluates executor evidence independently to produce a final verdict |

## Skills

| Skill | What It Covers |
|-------|---------------|
| `qe-strategy` | Test pyramid, risk-based prioritization, when to use each test type |
| `acceptance-testing` | Evidence-gated three-agent pipeline, the problem with self-grading, artifact conventions |

## How It Works

**PostToolUse hook** — Every `Write` or `Edit` call triggers `change_tracker.py`, which updates a session-scoped file list in `~/.something-wicked/wicked-qe/`. When a changed file has no corresponding test file, Claude gets a nudge at the end of the turn.

**Three-agent acceptance pipeline** — Writer, Executor, and Reviewer are independent subagents with different instructions. The Executor has no pass/fail logic; it only captures artifacts. The Reviewer never runs code; it only evaluates what the Executor recorded. This separation prevents "something happened = PASS" false positives.

## Integration

| Plugin | What It Unlocks | Without It |
|--------|----------------|------------|
| wicked-crew | Auto-engaged during `test-strategy` and `review` phases of a crew workflow | Use commands directly when needed |
| wicked-engineering | Combined code review + test quality review in a single pass | QE perspective only, no code architecture view |
| wicked-search | Find untested code paths by traversing the symbol graph | Manual discovery of what lacks test coverage |
| wicked-mem | Remember test patterns, recurring failure modes, and past coverage decisions across sessions | Session-only context; patterns lost on restart |
| wicked-scenarios | Execute acceptance test scenarios as CLI-orchestrated E2E tests | Acceptance testing limited to unit/integration level |

## License

MIT
