# wicked-platform

SREs, security engineers, compliance officers, and incident responders that auto-detect your observability stack (Sentry, Jaeger, Prometheus) via MCP and give you live metrics, not static analysis guesses.

## Quick Start

```bash
# Install
claude plugin install wicked-platform@wicked-garden

# Security review your API layer
/wicked-platform:security src/api/

# Validate HIPAA compliance before your next audit
/wicked-platform:compliance hipaa
```

## Workflows

### Security Review Before a PR Merge

You're about to merge a payment processing feature. Before it ships:

```bash
/wicked-platform:security src/payments/
```

Output:
```
Security Review: src/payments/ (14 files)

CRITICAL (1)
  payments/stripe.py:47 — API key read from environment but logged at DEBUG level
  CWE-532: Inclusion of Sensitive Information in Log Files

HIGH (2)
  payments/webhook.py:23 — Stripe signature not verified before payload deserialization
  CWE-345: Insufficient Verification of Data Authenticity

  payments/refund.py:89 — Amount parameter not validated against original charge
  CWE-20: Improper Input Validation

MEDIUM (1)
  payments/api.py:112 — No rate limiting on /api/payments/initiate endpoint

Recommendations: 3 code changes with specific line numbers and fixes
OWASP Top 10 coverage: A01 (Access Control), A02 (Crypto), A09 (Logging)
```

### Incident Response: From Alert to Root Cause

PagerDuty fires at 2am. Error rate on checkout spiked to 8%:

```bash
/wicked-platform:incident "500 errors spiking on checkout — started 14 minutes ago"
```

If Sentry MCP is configured, the incident responder pulls live error data directly. Without MCP, it analyzes your logs and recent deploys:

```
Incident Triage: checkout-service

Timeline
  02:14 — Deploy: checkout-service v2.3.1 (commit 8f2a91c)
  02:17 — Error rate crossed 1% threshold
  02:28 — Current: 8.3% error rate, ~420 affected users

Root cause (high confidence): NullPointerException in CartService.calculateTax()
  → New tax calculation logic in v2.3.1 fails when cart has digital goods
  → Affects: 12% of checkout sessions (those with digital + physical items)

Blast radius: checkout-service, order-service (downstream), revenue reporting
Rollback: git revert 8f2a91c && deploy → estimated 3 min

Remediation options:
  1. Rollback (immediate, safest)
  2. Feature flag: disable new tax logic → deploy patch
  3. Hotfix: null check in calculateTax() line 47
```

### Compliance Check Before an Audit

Your team handles PHI and your SOC2 audit is in 6 weeks:

```bash
/wicked-platform:compliance hipaa
```

Output:
```
HIPAA Compliance Assessment

GAPS FOUND (3)

  § 164.312(a)(1) Access Control
  FAIL: No audit logging on PHI access in src/patient/records.py
  Required: Automatic logoff, unique user identification
  Evidence needed: Access control policy, audit log samples

  § 164.312(e)(2)(ii) Encryption in Transit
  WARN: TLS 1.1 still supported in nginx config (line 34)
  Required: TLS 1.2 minimum
  Fix: ssl_protocols TLSv1.2 TLSv1.3;

  § 164.308(a)(5) Security Awareness Training
  INFO: No training records found in expected location
  Check: Are records stored elsewhere?

PASSING (14 of 17 controls)
Audit readiness: 82% — address gaps before scheduling
```

### Generate CI/CD Pipeline

```bash
/wicked-platform:actions generate
```

The devops engineer agent inspects your repo structure, detects your language, framework, and test setup, and generates a GitHub Actions workflow tailored to your project — not a generic template.

## Commands

| Command | What It Does | Example |
|---------|-------------|---------|
| `/wicked-platform:security` | OWASP security review with CWE mapping | `/wicked-platform:security src/api/` |
| `/wicked-platform:health` | System health assessment via MCP or log analysis | `/wicked-platform:health api-gateway` |
| `/wicked-platform:compliance` | Regulatory compliance check (SOC2, HIPAA, GDPR, PCI) | `/wicked-platform:compliance hipaa` |
| `/wicked-platform:incident` | Incident triage, root cause, and remediation plan | `/wicked-platform:incident "500 errors spiking"` |
| `/wicked-platform:errors` | Error pattern analysis from logs or Sentry/Rollbar | `/wicked-platform:errors recent` |
| `/wicked-platform:traces` | Distributed tracing analysis | `/wicked-platform:traces slow` |
| `/wicked-platform:infra` | Infrastructure and IaC review | `/wicked-platform:infra terraform/` |
| `/wicked-platform:actions` | GitHub Actions workflow generation | `/wicked-platform:actions generate` |
| `/wicked-platform:gh` | GitHub CLI power operations | `/wicked-platform:gh workflows` |
| `/wicked-platform:audit` | Audit evidence collection | `/wicked-platform:audit soc2 CC6.1` |

## How It Works

### MCP Auto-Discovery

The plugin auto-detects your observability stack when those MCP servers are configured. No setup needed:

| Tool | What It Enables |
|------|----------------|
| Sentry / Rollbar / Datadog | Live error tracking via `/errors` and `/incident` |
| Jaeger / Zipkin / Honeycomb | Distributed tracing via `/traces` |
| Prometheus / Grafana | Live health metrics via `/health` |

Without MCP integrations, everything still works — agents analyze logs, configs, and code patterns instead. The three modes:

1. **With MCP** — Live metrics, traces, errors pulled directly from your observability stack
2. **Without MCP** — Expert analysis of your logs, configs, and code
3. **Offline** — Static analysis and best practice guidance

## Agents

| Agent | Focus |
|-------|-------|
| `security-engineer` | Vulnerability assessment, OWASP Top 10, secure coding patterns |
| `devops-engineer` | CI/CD pipelines, deployment automation |
| `infrastructure-engineer` | Cloud IaC, Kubernetes, Terraform |
| `release-engineer` | Versioning, deployment strategies, rollbacks |
| `sre` | System health, capacity planning, reliability engineering |
| `incident-responder` | Triage, root cause analysis, blast radius assessment |
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
| `errors` | Error tracking and aggregation |
| `compliance` | Regulatory framework analysis |
| `policy` | Policy interpretation and controls mapping |
| `audit` | Audit evidence gathering |

## Integration

| Plugin | What It Unlocks | Without It |
|--------|----------------|------------|
| wicked-crew | Auto-engaged in build and review phases for security and reliability checks | Use commands directly |
| wicked-mem | Retain incident learnings and compliance decisions across sessions | Start fresh each session |
| wicked-workbench | Platform health and compliance dashboards | Text output only |

## License

MIT
