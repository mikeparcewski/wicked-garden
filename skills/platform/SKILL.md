---
name: wicked-garden-platform
user-invocable: true
description: |
  Platform domain skill: security scanning, incident triage, infrastructure
  review, and distributed-trace analysis. Routes to one of four inline actions
  (security | incident | infra | traces) backed by the rubrics in refs/, and
  links out to the domain's sub-skills (audit, compliance, health,
  observability, CI/CD tooling, peer-health) and fork workers.

  Use when: "security scan", "vulnerability assessment", "scan this PR for
  vulnerabilities", "run the security scanners", "incident", "production is
  down", "triage this alert", "root cause this error", "review our Terraform",
  "IaC review", "infrastructure review", "cloud cost review", "trace analysis",
  "why is this endpoint slow", "latency investigation", or any former
  /wicked-garden:platform:{security|incident|infra|traces} invocation.
phase_relevance: ["build", "review", "operate"]
archetype_relevance: ["*"]
---

# Platform Domain

One entry point for the platform domain. Pick the action from the request,
parse its args, load its ref, and apply it inline.

## Action router

| Action | Use for | Args | Ref |
|--------|---------|------|-----|
| `security` | Real-scanner vulnerability scan + triage on code, PRs, or full repos | `<path, PR, or 'full'> [--scenarios]` | `refs/security-scan.md` |
| `incident` | Rapid incident triage: root cause, blast radius, remediation | `<error message, alert, or symptom>` | `incident/refs/incident.md` |
| `infra` | IaC / cloud architecture review: security, cost, HA, best practice | `<path to IaC files or 'scan'>` | `infra/refs/infra.md` |
| `traces` | Distributed-trace analysis: latency, dependencies, bottlenecks | `[service, trace ID, or 'slow']` | `traces/refs/traces.md` |

Routing hints:
- Compliance **evidence collection** → the `audit` sub-skill, not `security`.
- Compliance **policy/framework checking** → the `compliance` sub-skill.
- System/service health aggregation → the `health` sub-skill.
- Plugin-level diagnostics (probes, hook traces, contract assertions) → the
  `observability` sub-skill.
- Application architecture review → engineering domain (`arch`), not `infra`.

## Action: security

Run the real security scanners, then triage their actual output. This action
does NOT grep-guess: it detects which scanners are installed, runs the ones
that exist, and feeds their findings to triage. A missing scanner is reported
and skipped — the action never fails because a tool is absent.

1. Set the target from args (a path; default `.`, or the PR's changed files
   when given a PR number). Note `--scenarios` if passed.
2. `Read("${CLAUDE_PLUGIN_ROOT}/skills/platform/refs/security-scan.md")` — the
   scanner detect+run block, the report formats for each scanner's JSON
   output, and the triage step.
3. For the triage rubric (CWE table, severity bands, OWASP matrix, output
   format, `--scenarios` behaviour, bus emit), read
   `${CLAUDE_PLUGIN_ROOT}/skills/platform-security-engineer/SKILL.md` — your
   reference, NOT a thing to re-derive.

NOT for compliance evidence collection (use the `audit` sub-skill) or IaC
posture (use the `infra` action).

## Action: incident

Rapid incident triage with root cause correlation, blast radius assessment,
and remediation guidance.

> **Scope**: this action is for **rapid active triage** — root cause, blast
> radius, remediation steps. To **log** an incident against a crew project
> with traceability, use the crew incident flow (`crew:incident`) instead.

1. Collect incident context from the args: error/alert description, start time
   if given, affected scope.
2. `Read("${CLAUDE_PLUGIN_ROOT}/skills/platform/incident/refs/incident.md")` —
   the 5-phase rubric (triage → stabilize → investigate → resolve →
   follow-up), severity classification, common patterns, output format, and
   communication templates.
3. Apply the rubric directly: discover observability sources via
   `ListMcpResourcesTool`, correlate with recent git changes, classify
   severity (SEV1–SEV4), and produce the incident report with blast radius,
   mitigation actions, and rollback decision.

## Action: infra

Review infrastructure-as-code and cloud architecture for security, cost, HA,
and best-practice posture. NOT for application architecture review (use the
engineering domain's arch review) or active incident response (use the
`incident` action).

1. Parse args: path to IaC files, or `scan` to discover `.tf`, `.tfvars`,
   CloudFormation, Pulumi, Kubernetes manifests, and `docker-compose` files.
2. `Read("${CLAUDE_PLUGIN_ROOT}/skills/platform/infra/refs/infra.md")` —
   discovery commands, security matrix, cost-optimization checklist, HA/DR
   checklist, platform best practices (Terraform, Kubernetes, Docker
   Compose), and output format.
3. Apply the rubric directly: discover IaC files, detect the platform, assess
   each dimension, and produce the infrastructure review with resource
   inventory, security matrix, cost opportunities, HA gaps, and prioritized
   fixes (critical first, then improvements).

## Action: traces

Analyze distributed traces for latency investigation, service dependencies,
and bottleneck detection. This is **distributed tracing across services** —
for wicked-garden hook execution traces, use the `observability` sub-skill
(`scripts/platform/observability/ops_log_viewer.py`).

1. Parse args: service name, trace ID, or `slow` for p99 latency
   investigation.
2. `Read("${CLAUDE_PLUGIN_ROOT}/skills/platform/traces/refs/traces.md")` —
   tracing source discovery, investigation checklist, fallback code-pattern
   analysis, common patterns (N+1, sequential fan-out, cold-start), and
   output format.
3. Apply the rubric directly: discover tracing sources via
   `ListMcpResourcesTool`, query the target, and produce the trace analysis
   with latency breakdown, service dependencies, bottlenecks, and
   optimization recommendations with expected impact.

## Sub-skills

Loaded on demand — each is its own skill beside this one:

| Sub-skill | Use for |
|-----------|---------|
| `skills/platform/audit/` | Audit evidence collection for SOC2/HIPAA/GDPR/PCI |
| `skills/platform/compliance/` | Regulatory compliance check against a framework |
| `skills/platform/errors/` | Production error spike/pattern investigation |
| `skills/platform/health/` | System health aggregation across services |
| `skills/platform/observability/` | Plugin ecosystem diagnostics: probes, hook traces, contract assertions, toolchain discovery |
| `skills/platform/gh-cli/` | Advanced gh CLI operations (workflows, PRs, releases, repo) |
| `skills/platform/glab-cli/` | Advanced glab CLI operations for GitLab |
| `skills/platform/github-actions/` | GitHub Actions workflow generation/optimization/troubleshooting |
| `skills/platform/gitlab-ci/` | GitLab CI/CD pipeline writing |
| `skills/platform/prereq-doctor/` | Missing tool/dependency diagnosis |
| `skills/platform/gate-benchmark-rebaseline/` | AC-11 gate-result benchmark re-baselining |
| `skills/platform/peer-health/` | wicked-* peer tool reachability + version health |

## Fork workers

Dispatchable specialist workers (context: fork), for delegated deep passes:

- `skills/platform-security-engineer/` — security scanning + vulnerability
  assessment (also the triage rubric for the `security` action)
- `skills/platform-compliance-officer/` — regulatory compliance analysis
- `skills/platform-privacy-expert/` — PII/PHI detection and privacy-by-design
