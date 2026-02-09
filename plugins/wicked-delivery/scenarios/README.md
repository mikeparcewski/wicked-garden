# Wicked Delivery Test Scenarios

This directory contains real-world test scenarios that demonstrate and validate wicked-delivery functionality across its four domains: PMO, Onboarding, Experimentation, and FinOps.

## Scenario Overview

| Scenario | Domain | Type | Difficulty | Time | What It Tests |
|----------|--------|------|------------|------|---------------|
| [01-new-developer-onboarding](01-new-developer-onboarding.md) | Onboarding | workflow | basic | 8 min | Full onboarding flow: orientation, learning paths, first tasks |
| [02-sprint-health-check](02-sprint-health-check.md) | PMO | workflow | basic | 6 min | Delivery metrics, velocity tracking, blocker identification |
| [03-ab-test-design](03-ab-test-design.md) | Experiment | workflow | intermediate | 10 min | Hypothesis formulation, sample size calculation, instrumentation |
| [04-progressive-rollout](04-progressive-rollout.md) | Experiment | workflow | intermediate | 8 min | Risk assessment, canary deployment, rollback planning |
| [05-cloud-cost-analysis](05-cloud-cost-analysis.md) | FinOps | workflow | intermediate | 10 min | Cost breakdown, anomaly detection, optimization recommendations |
| [06-stakeholder-reporting](06-stakeholder-reporting.md) | PMO | feature | advanced | 12 min | Multi-perspective delivery reports from project exports |

## Coverage Map

### Domain Coverage

| Domain | Scenarios | Agents Tested | Skills Tested |
|--------|-----------|---------------|---------------|
| **Onboarding** | 01 | onboarding-guide, codebase-narrator | orient, guide, explain |
| **PMO** | 02, 06 | delivery-manager, progress-tracker, risk-monitor, stakeholder-reporter | reporting |
| **Experiment** | 03, 04 | experiment-designer, rollout-manager | design, rollout, analyze |
| **FinOps** | 05 | finops-analyst, cost-optimizer, forecast-specialist | analyze, optimize, forecast |

### Feature Coverage

- **Orientation & Learning**: 01-new-developer-onboarding
- **Code Explanation**: 01-new-developer-onboarding
- **Velocity Tracking**: 02-sprint-health-check
- **Blocker Identification**: 02-sprint-health-check
- **Experiment Design**: 03-ab-test-design
- **Sample Size Calculation**: 03-ab-test-design
- **Risk Assessment**: 04-progressive-rollout
- **Rollout Stages**: 04-progressive-rollout
- **Cost Analysis**: 05-cloud-cost-analysis
- **Cost Optimization**: 05-cloud-cost-analysis
- **Multi-Perspective Reports**: 06-stakeholder-reporting

### Integration Testing

- **wicked-kanban**: 02-sprint-health-check, 03-ab-test-design
- **wicked-mem**: 01-new-developer-onboarding, 05-cloud-cost-analysis
- **wicked-search**: 01-new-developer-onboarding, 02-sprint-health-check

## Running Scenarios

Each scenario is self-contained with:
- **Setup** - Initial conditions and test data creation
- **Steps** - Specific actions to perform
- **Expected Outcome** - What should happen
- **Success Criteria** - Verifiable checkboxes
- **Value Demonstrated** - Why this matters

### Example: Running 01-new-developer-onboarding

```bash
# Follow the setup commands in the scenario file
mkdir -p ~/test-wicked-delivery/sample-project
cd ~/test-wicked-delivery/sample-project
# ... continue with setup

# Then execute the scenario steps using Task tool
Task tool: subagent_type="wicked-delivery:onboarding-guide"
prompt="Help me get oriented in this codebase"
```

### Verification

After running each scenario:
1. Check that outputs match expected format
2. Verify deliverables are actionable (specific file paths, concrete steps)
3. Confirm all success criteria checkboxes can be marked
4. Test integration with other wicked-* plugins if available

## Scenario Design Principles

All scenarios follow these guidelines:

1. **Real-world use cases** - No toy examples; scenarios reflect actual development and delivery workflows
2. **Functional testing** - Each scenario proves a feature actually works
3. **Concrete setup** - Clear, executable commands to create test data
4. **Verifiable criteria** - Objective checkboxes that can be tested
5. **Value articulation** - Clear explanation of WHY someone would use this

## Adding New Scenarios

When adding scenarios, include:

```markdown
---
name: scenario-name
title: Human Readable Title
description: One-line description
type: workflow|integration|feature
difficulty: basic|intermediate|advanced
estimated_minutes: N
---

# Title

## Setup
[Concrete setup commands]

## Steps
[Numbered steps with commands]

## Expected Outcome
[What should happen]

## Success Criteria
- [ ] Verifiable criteria 1
- [ ] Verifiable criteria 2

## Value Demonstrated
[Why this matters in real-world usage]
```

## Test Execution

These scenarios can be:
- **Manual testing** - Follow steps during development
- **Onboarding** - Help new users understand capabilities
- **Documentation** - Show real examples of features
- **Regression testing** - Verify nothing broke after changes
- **Value demonstration** - Show prospective users what the plugin does

## Recommended Testing Order

For comprehensive validation:

1. **Start with**: `01-new-developer-onboarding` (basic, foundational)
2. **PMO basics**: `02-sprint-health-check` (delivery metrics)
3. **Experimentation**: `03-ab-test-design` (experiment planning)
4. **Safe rollouts**: `04-progressive-rollout` (risk management)
5. **Cost management**: `05-cloud-cost-analysis` (FinOps)
6. **Advanced**: `06-stakeholder-reporting` (multi-perspective)

## Integration Levels

### Full Integration (All wicked-* plugins)
```bash
claude plugin install wicked-mem@wicked-garden
claude plugin install wicked-search@wicked-garden
claude plugin install wicked-kanban@wicked-garden
```
Run all scenarios to see full integration capabilities.

### Partial Integration
Install only wicked-mem for cross-session memory.
Run: 01, 05 (benefit from memory recall)

### Standalone
No additional plugins required.
Run: All scenarios work standalone, with graceful degradation.

## Questions?

- **What are the four domains?**: PMO (delivery), Onboarding, Experimentation, FinOps
- **Which agents are included?**: 11 specialized agents across 4 domains
- **What's capability discovery?**: Finding available tools without hardcoding vendor names
- **What's graceful degradation?**: Working with reduced functionality when integrations unavailable

For more details, see [wicked-delivery README](../README.md).
