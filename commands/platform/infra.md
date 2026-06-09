---
description: |
  Use when reviewing infrastructure-as-code (Terraform, CloudFormation, Pulumi) for correctness, cost,
  or security posture. NOT for application architecture review (use engineering:arch) or
  active incident response (use platform:incident).
argument-hint: "<path to IaC files or 'scan' for discovery>"
phase_relevance: ["build", "review", "operate"]
archetype_relevance: ["*"]
---

# /wicked-garden:platform:infra

Review infrastructure-as-code and cloud architecture for security, cost, HA, and best-practice posture.

## Run it inline (no dispatch)

1. Parse `$ARGUMENTS`: path to IaC files, or `scan` to discover `.tf`, `.tfvars`, CloudFormation,
   Pulumi, Kubernetes manifests, and `docker-compose` files.
2. `Read("${CLAUDE_PLUGIN_ROOT}/skills/platform/infra/refs/infra.md")` — discovery commands,
   security matrix, cost-optimization checklist, HA/DR checklist, platform best practices
   (Terraform, Kubernetes, Docker Compose), and output format.
3. Apply the rubric directly: discover IaC files, detect the platform, assess each dimension,
   and produce the infrastructure review with resource inventory, security matrix, cost opportunities,
   HA gaps, and prioritized fixes (critical first, then improvements).
