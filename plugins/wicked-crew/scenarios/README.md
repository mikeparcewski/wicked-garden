# wicked-crew Test Scenarios

This directory contains functional test scenarios that demonstrate wicked-crew's real-world capabilities.

## Purpose

These scenarios serve three purposes:

1. **Validation**: Verify that wicked-crew works correctly across different configurations
2. **Documentation**: Show concrete examples of what wicked-crew can do
3. **Onboarding**: Help new users understand the plugin through hands-on testing

## Scenario Overview

| Scenario | Type | Difficulty | Time | What It Proves |
|----------|------|------------|------|----------------|
| [01-end-to-end-feature](01-end-to-end-feature.md) | Workflow | Intermediate | 20 min | Complete 5-phase project lifecycle with quality gates |
| [02-autonomous-completion](02-autonomous-completion.md) | Workflow | Advanced | 15 min | Just-finish mode works safely with guardrails |
| [03-plugin-degradation](03-plugin-degradation.md) | Integration | Intermediate | 12 min | Graceful degradation across 4 integration levels |
| [04-context-isolation](04-context-isolation.md) | Feature | Advanced | 10 min | SADD pattern isolates context and prevents pollution |
| [05-multi-project-management](05-multi-project-management.md) | Workflow | Basic | 8 min | Multiple concurrent projects with independent state |

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
   mkdir -p ~/test-wicked-crew
   cd ~/test-wicked-crew
   # ... follow setup instructions
   ```

2. **Execute the scenario**:
   ```bash
   # Follow the steps in order
   /wicked-crew:start "..."
   /wicked-crew:execute
   # ... etc
   ```

3. **Verify results**:
   - Check that outputs match "Expected Outcome"
   - Verify success criteria checkboxes
   - Inspect generated artifacts

4. **Clean up**:
   ```bash
   # Remove test data
   rm -rf ~/test-wicked-crew
   rm -rf ~/.something-wicked/wicked-crew/projects/test-*
   ```

## Recommended Testing Order

For comprehensive validation:

1. **Start with**: `05-multi-project-management` (basic, quick win)
2. **Core workflow**: `01-end-to-end-feature` (the main use case)
3. **Resilience**: `03-plugin-degradation` (works without dependencies)
4. **Autonomy**: `02-autonomous-completion` (just-finish mode)
5. **Architecture**: `04-context-isolation` (advanced SADD pattern)

## Testing Different Configurations

### Full Integration (Level 4)
All wicked plugins installed:
```bash
claude plugin install wicked-jam@wicked-garden
claude plugin install wicked-search@wicked-garden
claude plugin install wicked-product@wicked-garden
claude plugin install wicked-kanban@wicked-garden
claude plugin install wicked-mem@wicked-garden
```
Run: `01-end-to-end-feature`, `02-autonomous-completion`

### Partial Integration (Level 2)
Only wicked-mem:
```bash
claude plugin install wicked-mem@wicked-garden
```
Run: `03-plugin-degradation`

### Standalone (Level 1)
No plugins:
```bash
# Uninstall all wicked plugins
```
Run: `03-plugin-degradation`, `05-multi-project-management`

## Success Criteria Summary

A successful test run means:

- [ ] All setup commands execute without errors
- [ ] All steps produce expected outputs
- [ ] All success criteria checkboxes can be checked
- [ ] Artifacts are created in correct locations
- [ ] No context leakage between projects/phases
- [ ] Guardrails prevent dangerous operations
- [ ] Degradation works correctly when plugins unavailable

## Common Issues

### Project Not Found
**Symptom**: `/wicked-crew:status` says "No active project"
**Solution**: Ensure you're in the correct working directory for the project

### Plugin Not Available
**Symptom**: Status shows "degraded mode"
**Solution**: This is expected if testing degradation. Install plugins for full integration.

### Approval Required
**Symptom**: Execute command pauses for approval
**Solution**: This is expected for guardrails. Use `/wicked-crew:approve <phase>` to continue.

### Phase Already Complete
**Symptom**: "Cannot execute completed phase"
**Solution**: Check status - you may have already advanced past this phase.

## Extending Scenarios

To create new scenarios:

1. **Use the template**:
   ```markdown
   ---
   name: my-scenario
   title: Human Readable Title
   description: One-line description
   type: workflow|integration|feature
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

2. **Create realistic setup**: Real code, not toy examples
3. **Verify functionality**: Actually proves the plugin works
4. **Articulate value**: Why would someone use this?

## Contributing

Found a bug while running scenarios? Scenario doesn't work as described? Please open an issue with:
- Which scenario failed
- What step failed
- Expected vs actual behavior
- Your plugin configuration (degradation level)

## Questions?

- **What's SADD?**: Spawn-Agent-Dispatch-Destroy pattern for context isolation
- **What's a quality gate?**: Required approval between phases
- **What's degradation?**: Graceful fallback when plugins unavailable
- **Why phases?**: Enforces outcome-before-code, testing-before-build

For more details, see [wicked-crew README](../README.md).
