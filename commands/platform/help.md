---
description: Show available platform engineering commands and usage
---

# /wicked-garden:platform:help

Display usage information and examples.

## Instructions

Show the following help information:

```markdown
# wicked-platform Help

Platform engineering and DevSecOps — security, infrastructure, compliance, incident response, CI/CD, and system health.

## Commands

| Command | Description |
|---------|-------------|
| `/wicked-garden:platform:security <target>` | Security review and vulnerability assessment |
| `/wicked-garden:platform:infra <path>` | Infrastructure review and IaC analysis |
| `/wicked-garden:platform:compliance <framework>` | Regulatory compliance check (SOC2, HIPAA, GDPR, PCI) |
| `/wicked-garden:platform:audit <framework>` | Audit evidence collection and compliance verification |
| `/wicked-garden:platform:incident <description>` | Incident response and triage |
| `/wicked-garden:platform:health [service]` | System health check and reliability assessment |
| `/wicked-garden:platform:errors [service]` | Error analysis and pattern detection |
| `/wicked-garden:platform:traces [service]` | Distributed tracing analysis for latency and dependencies |
| `/wicked-garden:platform:actions <operation>` | GitHub Actions workflow generation and optimization |
| `/wicked-garden:platform:gh <operation>` | GitHub CLI power utilities for workflows, PRs, and releases |
| `/wicked-garden:platform:help` | This help message |

## Quick Start

```
/wicked-garden:platform:security ./src
/wicked-garden:platform:infra scan
/wicked-garden:platform:health all
```

## Examples

### Security
```
/wicked-garden:platform:security ./api --scenarios
/wicked-garden:platform:security full
```

### Infrastructure
```
/wicked-garden:platform:infra ./terraform
/wicked-garden:platform:infra scan
```

### Compliance
```
/wicked-garden:platform:compliance soc2
/wicked-garden:platform:audit hipaa
```

### Incident Response
```
/wicked-garden:platform:incident "500 errors on /api/checkout"
/wicked-garden:platform:errors recent
/wicked-garden:platform:traces slow
```

### CI/CD
```
/wicked-garden:platform:actions generate
/wicked-garden:platform:actions optimize .github/workflows/ci.yml
/wicked-garden:platform:gh workflows
```

## Integration

- **wicked-crew**: Specialist routing for security and platform phases
- **wicked-engineering**: Architecture review with security lens
- **wicked-qe**: Security test scenarios
- **wicked-agentic**: Trust and safety audits for agent systems
```
