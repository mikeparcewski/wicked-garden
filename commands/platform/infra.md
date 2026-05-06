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

Review infrastructure-as-code and cloud architecture for security, cost, HA, and best-practice posture. Use for Terraform/CloudFormation/Pulumi/K8s/docker-compose reviews. NOT for application architecture (use engineering:arch) or live incidents (use platform:incident).

## 1. Dispatch

```
Task(subagent_type="wicked-garden:platform:infrastructure-engineer",
     prompt="""Review infrastructure-as-code.

Args: $ARGUMENTS  (path to IaC files | 'scan' to discover .tf/.tfvars, cloudformation*.{yaml,json},
pulumi.*, *.k8s.yaml, kubernetes/*.yaml, docker-compose*.yaml)

Detect platform, then assess: resource sizing, IAM least-privilege, network segmentation,
encryption at rest/in transit, no hardcoded secrets, cost optimization, multi-AZ/HA, DR readiness,
platform best practices.
Return resource inventory, security matrix, cost opportunities with savings, HA gaps,
prioritized fixes (critical first, then improvements).""")
```
