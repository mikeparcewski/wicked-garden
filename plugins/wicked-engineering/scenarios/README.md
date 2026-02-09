# wicked-engineering Test Scenarios

This directory contains functional test scenarios that demonstrate wicked-engineering's real-world capabilities.

## Purpose

These scenarios serve three purposes:

1. **Validation**: Verify that wicked-engineering works correctly across different use cases
2. **Documentation**: Show concrete examples of what wicked-engineering can do
3. **Onboarding**: Help new users understand the plugin through hands-on testing

## Philosophy

> **Testing is what allows you to deliver faster.**

wicked-engineering embodies shift-left quality engineering. These scenarios demonstrate catching issues early, systematic debugging, and building quality into every phase of development.

## Scenario Overview

| Scenario | Type | Difficulty | Time | What It Proves |
|----------|------|------------|------|----------------|
| [01-code-review-pr](01-code-review-pr.md) | Review | Basic | 10 min | Senior engineering review catches bugs before merge |
| [02-systematic-debugging](02-systematic-debugging.md) | Debugging | Intermediate | 12 min | Methodical root cause analysis with prevention |
| [03-architecture-analysis](03-architecture-analysis.md) | Architecture | Advanced | 15 min | Identify coupling, antipatterns, and evolution paths |
| [06-implementation-planning](06-implementation-planning.md) | Review | Advanced | 15 min | Plan changes with risk assessment and safe rollout |

> **Note**: QE scenarios (shift-left, test generation) have moved to [wicked-qe](../../wicked-qe/scenarios/).

## How to Run

Each scenario includes:
- **Setup**: Bash commands to create realistic test data
- **Steps**: Specific commands to execute
- **Expected Outcome**: What should happen at each step
- **Success Criteria**: Checkboxes to verify correct behavior
- **Value Demonstrated**: Explanation of real-world benefit

### Running a Scenario

1. **Create test environment**:
   ```bash
   # Run the setup commands from the scenario
   mkdir -p ~/test-wicked-engineering
   cd ~/test-wicked-engineering
   # ... follow setup instructions
   ```

2. **Execute the scenario**:
   ```bash
   # Follow the steps in order
   /wicked-engineering:review src/
   /wicked-engineering:debug "error message"
   # ... etc
   ```

3. **Verify results**:
   - Check that outputs match "Expected Outcome"
   - Verify success criteria checkboxes
   - Review generated artifacts

4. **Clean up**:
   ```bash
   # Remove test data
   rm -rf ~/test-wicked-engineering
   ```

## Recommended Testing Order

For comprehensive validation:

1. **Start with**: `01-code-review-pr` (basic, demonstrates core review capability)
2. **Debugging**: `02-systematic-debugging` (shows methodical problem solving)
3. **Architecture**: `03-architecture-analysis` (advanced design evaluation)
4. **Planning**: `06-implementation-planning` (full planning workflow)

## Command Coverage

| Command | Primary Scenario | Secondary Scenarios |
|---------|------------------|---------------------|
| `/wicked-engineering:review` | 01-code-review-pr | 06-implementation-planning |
| `/wicked-engineering:debug` | 02-systematic-debugging | - |
| `/wicked-engineering:arch` | 03-architecture-analysis | - |
| `/wicked-engineering:plan` | 06-implementation-planning | - |

## Agent Coverage

These scenarios exercise the following agents:

| Agent | Scenarios |
|-------|-----------|
| senior-engineer | 01, 06 |
| debugger | 02 |
| solution-architect | 03 |
| system-designer | 03 |

## Success Criteria Summary

A successful test run means:

- [ ] All setup commands execute without errors
- [ ] All steps produce expected outputs
- [ ] All success criteria checkboxes can be checked
- [ ] Reviews identify real issues (not false positives)
- [ ] Debugging traces to actual root cause
- [ ] Architecture analysis is actionable
- [ ] Generated tests are syntactically correct
- [ ] Plans include risk mitigation

## Common Issues

### Review Finds No Issues
**Symptom**: Review says "no issues found" on code with known problems
**Solution**: Ensure the setup code is copied correctly with intentional issues

### Debug Can't Find Root Cause
**Symptom**: Debugger goes in circles without identifying cause
**Solution**: Provide more context (stack trace, error logs)

### Architecture Too Broad
**Symptom**: Analysis is vague and generic
**Solution**: Specify `--scope module` for focused analysis

### Tests Don't Match Code
**Symptom**: Generated tests reference non-existent methods
**Solution**: Ensure implementation file is read before generating tests

## Integration with Other Plugins

wicked-engineering works standalone. Enhanced with:

| Plugin | Enhancement |
|--------|-------------|
| wicked-crew | QE phase integration, quality gates |
| wicked-search | Find related code during analysis |
| wicked-mem | Remember patterns across sessions |
| wicked-kanban | Track QE findings as tasks |

## Extending Scenarios

To create new scenarios:

1. **Use the template**:
   ```markdown
   ---
   name: my-scenario
   title: Human Readable Title
   description: One-line description
   type: review|architecture|debugging|testing
   difficulty: basic|intermediate|advanced
   estimated_minutes: N
   ---

   # Title

   ## Setup
   ## Steps
   ## Expected Outcome
   ## Success Criteria
   ## Value Demonstrated
   ```

2. **Create realistic setup**: Real code with real issues, not toy examples
3. **Verify functionality**: Actually proves the plugin works
4. **Articulate value**: Why would someone use this?

## Contributing

Found a bug while running scenarios? Scenario doesn't work as described? Please open an issue with:
- Which scenario failed
- What step failed
- Expected vs actual behavior
- Your environment details

## Questions?

- **What's shift-left?**: Catch issues early (requirements/design) instead of late (testing/production)
- **What's QE?**: Quality Engineering - holistic quality across the delivery lifecycle
- **Why scenarios before tests?**: Ensures comprehensive coverage, not just happy paths
- **What's a blast radius?**: Impact scope of changing a piece of code

For more details, see [wicked-engineering README](../README.md).
