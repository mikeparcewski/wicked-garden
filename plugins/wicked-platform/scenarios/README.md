# wicked-platform Test Scenarios

This directory contains functional test scenarios that demonstrate wicked-platform's real-world capabilities across DevSecOps, observability, and compliance domains.

## Purpose

These scenarios serve three purposes:

1. **Validation**: Verify that wicked-platform works correctly across different use cases
2. **Documentation**: Show concrete examples of what the plugin can do
3. **Onboarding**: Help new users understand the plugin through hands-on testing

## Scenario Overview

| Scenario | Type | Difficulty | Time | What It Proves |
|----------|------|------------|------|----------------|
| [01-ci-workflow-generation](01-ci-workflow-generation.md) | DevOps | Basic | 8 min | Generate secure, optimized GitHub Actions workflows automatically |
| [02-security-vulnerability-scan](02-security-vulnerability-scan.md) | Security | Intermediate | 12 min | OWASP vulnerability detection with actionable remediation |
| [03-incident-response-triage](03-incident-response-triage.md) | Infrastructure | Advanced | 15 min | Rapid incident triage with deployment correlation and rollback decisions |
| [04-compliance-audit-preparation](04-compliance-audit-preparation.md) | Compliance | Advanced | 15 min | SOC2 evidence collection and gap analysis for audit readiness |
| [05-system-health-assessment](05-system-health-assessment.md) | Infrastructure | Intermediate | 10 min | Unified health view with SLO tracking and capacity planning |
| [06-workflow-troubleshooting](06-workflow-troubleshooting.md) | DevOps | Intermediate | 10 min | Debug failing CI/CD with root cause analysis and fixes |

## Target Users

- **DevOps Engineers**: Scenarios 01, 06 - CI/CD workflow generation and debugging
- **Security Engineers**: Scenario 02 - Vulnerability assessment and OWASP compliance
- **SREs**: Scenarios 03, 05 - Incident response and system health monitoring
- **Compliance Officers**: Scenario 04 - Audit evidence collection and gap analysis
- **Infrastructure Engineers**: Scenarios 03, 05 - System health and capacity planning

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
   mkdir -p ~/test-wicked-platform
   cd ~/test-wicked-platform
   # ... follow setup instructions
   ```

2. **Execute the scenario**:
   ```bash
   # Follow the steps in order
   /wicked-platform:actions generate
   /wicked-platform:security src/
   # ... etc
   ```

3. **Verify results**:
   - Check that outputs match "Expected Outcome"
   - Verify success criteria checkboxes
   - Review generated reports and recommendations

4. **Clean up**:
   ```bash
   # Remove test data
   rm -rf ~/test-wicked-platform
   ```

## Recommended Testing Order

For comprehensive validation:

1. **Start with**: `01-ci-workflow-generation` (basic, quick win)
2. **Security**: `02-security-vulnerability-scan` (intermediate)
3. **DevOps**: `06-workflow-troubleshooting` (intermediate, builds on 01)
4. **Observability**: `05-system-health-assessment` (intermediate)
5. **Incident**: `03-incident-response-triage` (advanced)
6. **Compliance**: `04-compliance-audit-preparation` (advanced)

## Plugin Capabilities by Scenario

### DevSecOps (Scenarios 01, 02, 06)

| Command | Capability | Scenario |
|---------|------------|----------|
| `/wicked-platform:actions generate` | Create CI/CD workflows | 01 |
| `/wicked-platform:actions optimize` | Improve existing workflows | 01, 06 |
| `/wicked-platform:actions troubleshoot` | Debug failing workflows | 06 |
| `/wicked-platform:security` | Vulnerability assessment | 02 |

### Observability (Scenarios 03, 05)

| Command | Capability | Scenario |
|---------|------------|----------|
| `/wicked-platform:health` | System health aggregation | 05 |
| `/wicked-platform:incident` | Incident triage | 03 |
| `/wicked-platform:errors` | Error analysis | 03, 05 |
| `/wicked-platform:traces` | Distributed tracing | 03, 05 |

### Compliance (Scenario 04)

| Command | Capability | Scenario |
|---------|------------|----------|
| `/wicked-platform:compliance` | Framework compliance check | 04 |
| `/wicked-platform:audit` | Evidence collection | 04 |

## Success Criteria Summary

A successful test run means:

- [ ] All setup commands execute without errors
- [ ] Commands produce expected outputs
- [ ] Reports are well-formatted and actionable
- [ ] Recommendations are specific and implementable
- [ ] Security issues correctly identified
- [ ] Compliance gaps accurately detected
- [ ] Health metrics properly aggregated
- [ ] Incidents correctly triaged

## Agents Used

The scenarios exercise these specialized agents:

| Agent | Scenarios | Expertise |
|-------|-----------|-----------|
| `devops-engineer` | 01, 06 | CI/CD, automation |
| `security-engineer` | 02 | OWASP, vulnerability detection |
| `incident-responder` | 03 | Triage, root cause analysis |
| `sre` | 05 | Health monitoring, SLOs |
| `compliance-officer` | 04 | SOC2, HIPAA, GDPR |
| `auditor` | 04 | Evidence collection |

## Integration Points

wicked-platform works standalone but integrates with:

| Plugin | Enhancement | Tested In |
|--------|-------------|-----------|
| wicked-search | Code search for vulnerability patterns | 02 |
| wicked-crew | Phase-gated security reviews | 02, 04 |
| wicked-mem | Cross-session compliance learning | 04 |
| wicked-kanban | Track remediation tasks | 02, 04 |

## Common Issues

### No Observability Data
**Symptom**: Health commands show "No data sources found"
**Solution**: Expected in test environment. Plugin uses local fallbacks or simulated data.

### Permission Denied
**Symptom**: Cannot run gh commands
**Solution**: Authenticate with `gh auth login`

### Long Analysis Times
**Symptom**: Security scans taking >5 minutes
**Solution**: Use `--quick` flag for faster scans, or limit scope to specific paths.

### Missing Dependencies
**Symptom**: Script errors
**Solution**: Ensure Node.js, Python, and git are installed.

## Extending Scenarios

To create new scenarios:

1. **Use the template**:
   ```yaml
   ---
   name: my-scenario
   title: Human Readable Title
   description: One-line description
   type: security|compliance|infrastructure|devops
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
3. **Verify functionality**: Scenario must prove the plugin actually works
4. **Articulate value**: Why would someone use this? What problem does it solve?

## Value Summary

| Domain | Problem Solved | Time Saved |
|--------|----------------|------------|
| CI/CD Generation | Manual workflow creation with security gaps | 30 min -> 2 min |
| Security Review | Expensive, infrequent audits | $5,000 audit -> continuous |
| Incident Response | Scattered investigation across tools | 30 min MTTR -> 5 min |
| Compliance Audit | Manual evidence scramble | Weeks -> hours |
| Health Monitoring | Multiple dashboards, no unified view | 5 tools -> 1 command |
| Workflow Debug | Trial-and-error CI fixes | Hours -> minutes |

## Questions?

- **What's OWASP?**: Open Web Application Security Project - top 10 web vulnerabilities
- **What's SOC2?**: Service Organization Control 2 - security compliance framework
- **What's an SLO?**: Service Level Objective - reliability target (e.g., 99.9% uptime)
- **What's blast radius?**: Impact scope when something fails

For more details, see the [wicked-platform README](../README.md).
