# wicked-platform

A platform engineering team with auto-discovery -- SREs, security engineers, compliance officers, and incident responders that detect your observability stack (Sentry, Jaeger, Prometheus) via MCP. Live metrics and traces, not just static code analysis. Ships with SOC2, HIPAA, GDPR, and PCI compliance checks plus GitHub Actions and GitLab CI generation. Catches production issues, vulnerabilities, and regulatory gaps before they become incidents.

## Quick Start

```bash
# Install
claude plugin install wicked-platform@wicked-garden

# Security review your API
/wicked-platform:security src/api/

# Run a health check
/wicked-platform:health api-gateway

# Validate HIPAA compliance
/wicked-platform:compliance hipaa

# Investigate error patterns
/wicked-platform:errors recent

# Review infrastructure code
/wicked-platform:infra terraform/
```

## Commands

| Command | What It Does | Example |
|---------|-------------|---------|
| `/wicked-platform:security` | OWASP security review | `/wicked-platform:security src/api/` |
| `/wicked-platform:health` | System health assessment | `/wicked-platform:health api-gateway` |
| `/wicked-platform:compliance` | Regulatory compliance check | `/wicked-platform:compliance soc2 CC6.1` |
| `/wicked-platform:incident` | Incident triage and response | `/wicked-platform:incident "500 errors spiking"` |
| `/wicked-platform:errors` | Error pattern analysis | `/wicked-platform:errors recent` |
| `/wicked-platform:traces` | Distributed tracing analysis | `/wicked-platform:traces slow` |
| `/wicked-platform:infra` | Infrastructure and IaC review | `/wicked-platform:infra terraform/` |
| `/wicked-platform:actions` | GitHub Actions workflow generation | `/wicked-platform:actions generate` |
| `/wicked-platform:gh` | GitHub CLI operations | `/wicked-platform:gh workflows` |
| `/wicked-platform:audit` | Audit evidence collection | `/wicked-platform:audit soc2 CC6.1` |

## Pain Points Solved

- **"Did I break production?"** → `/health` before deploying
- **"Is this secure?"** → `/security` catches OWASP Top 10
- **"Are we compliant?"** → `/compliance` validates SOC2/HIPAA/GDPR/PCI
- **"What caused this outage?"** → `/incident` with distributed tracing
- **"Can we ship this?"** → Release readiness across security/compliance/reliability

## MCP Auto-Discovery

The plugin auto-detects your observability stack. No configuration needed:

| Tool | What It Enables |
|------|----------------|
| Sentry/Rollbar/Datadog | Live error tracking via `/errors` |
| Jaeger/Zipkin/Honeycomb | Distributed tracing via `/traces` |
| Prometheus/Grafana | Live health metrics via `/health` |

**Without integrations**, everything still works - it analyzes logs, configs, and code patterns instead.

## Agents

| Agent | Focus |
|-------|-------|
| `security-engineer` | Vulnerability assessment, OWASP, secure coding |
| `devops-engineer` | CI/CD pipelines, deployment automation |
| `infrastructure-engineer` | Cloud IaC, Kubernetes, Terraform |
| `release-engineer` | Versioning, deployment strategies, rollbacks |
| `sre` | System health, capacity planning, reliability |
| `incident-responder` | Triage, root cause analysis, blast radius |
| `compliance-officer` | SOC2, HIPAA, GDPR, PCI validation |
| `policy-analyst` | Policy-to-controls mapping |
| `privacy-expert` | PII/PHI detection, privacy by design |
| `auditor` | Evidence collection, audit trails |

## Skills

| Skill | Purpose |
|-------|---------|
| `github-actions` | Write and optimize GitHub Actions workflows |
| `gitlab-ci` | Write GitLab CI/CD pipelines |
| `gh-cli` | GitHub CLI power utilities |
| `glab-cli` | GitLab CLI operations |
| `health` | System health from observability sources |
| `traces` | Distributed tracing analysis |
| `errors` | Error tracking aggregation |
| `compliance` | Regulatory framework analysis |
| `policy` | Policy interpretation |
| `audit` | Audit evidence gathering |

## Integration

Works standalone in three modes:

1. **With MCP integrations** - Live metrics, traces, errors
2. **Without integrations** - Expert analysis of logs, configs, code
3. **Offline** - Static analysis and best practice guidance

Enhanced with:

| Plugin | Enhancement | Without It |
|--------|-------------|------------|
| wicked-crew | Auto-engaged in build/review phases | Use commands directly |
| wicked-mem | Cross-session learning | Session-only context |
| wicked-workbench | Platform dashboards | Text output only |

## License

MIT
