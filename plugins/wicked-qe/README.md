# wicked-qe

Shift-left quality engineering that generates test scenarios from requirements before code exists. PostToolUse hooks track every file change as you write, nudging for test coverage in real time -- so testing enables faster delivery, not slower. Catch issues during development, not after, with AI-powered test strategies, scenario generation, and automation code that wire directly into your workflow.

## Quick Start

```bash
# Install
claude plugin install wicked-qe@wicked-garden

# Generate test scenarios for a feature
/wicked-qe:scenarios src/auth/

# Create a full test plan
/wicked-qe:qe-plan "User authentication with OAuth2"

# Generate test code from scenarios
/wicked-qe:automate src/auth/ --framework jest

# Review existing test quality
/wicked-qe:qe-review tests/
```

## Commands

| Command | What It Does | Example |
|---------|-------------|---------|
| `/wicked-qe:scenarios` | Generate test scenarios from code or requirements | `/wicked-qe:scenarios src/checkout/` |
| `/wicked-qe:qe-plan` | Create comprehensive test strategy and plan | `/wicked-qe:qe-plan "Payment processing flow"` |
| `/wicked-qe:automate` | Generate test code from scenarios | `/wicked-qe:automate src/api/ --framework pytest` |
| `/wicked-qe:qe-review` | Review test quality, coverage gaps, and risk areas | `/wicked-qe:qe-review tests/unit/` |
| `/wicked-qe:qe` | Full quality review across the delivery lifecycle | `/wicked-qe:qe src/` |

## Workflows

### Shift-Left Testing (Write Tests Before Code)

```bash
# 1. Generate scenarios from requirements
/wicked-qe:scenarios requirements.md

# 2. Create test plan with risk-based prioritization
/wicked-qe:qe-plan "Feature: user registration"

# 3. Generate test code
/wicked-qe:automate src/registration/ --framework jest

# 4. Review after implementation
/wicked-qe:qe-review tests/
```

### Pre-PR Quality Check

```bash
# Review test quality before submitting
/wicked-qe:qe-review tests/ --focus coverage

# Full quality review
/wicked-qe:qe src/
```

## Agents

| Agent | Focus |
|-------|-------|
| `test-strategist` | Test scenario generation, coverage strategy, risk-based prioritization |
| `test-automation-engineer` | Test code generation, CI/CD test integration, coverage reporting |
| `risk-assessor` | Security, reliability, and operational risk identification |
| `code-analyzer` | Static analysis for testability, quality metrics, coverage gaps |
| `tdd-coach` | Red-green-refactor guidance, test-first development practices |

## Philosophy

> Testing is what allows you to deliver faster.

QE catches issues early when they're cheap to fix - in requirements, design, and architecture, not just in code. Every hour spent on test strategy saves days of debugging in production.

## Integration

Works standalone. Enhanced with:

| Plugin | Enhancement | Without It |
|--------|-------------|------------|
| wicked-crew | Auto-engaged during test-strategy and review phases | Use commands directly |
| wicked-engineering | Combined code + test review in `/review` | QE-only perspective |
| wicked-search | Find untested code paths via symbol graph | Manual discovery |
| wicked-mem | Remember test patterns and past failures | Session-only context |

## License

MIT
