---
description: Infrastructure review and IaC analysis
argument-hint: "<path to IaC files or 'scan' for discovery>"
---

# /wicked-garden:platform:infra

Review infrastructure-as-code, analyze cloud architecture, and identify optimization opportunities.

## Instructions

### 1. Discover Infrastructure Files

If "scan" or no argument:
```bash
# Find IaC files
find . -name "*.tf" -o -name "*.tfvars"
find . -name "cloudformation*.yaml" -o -name "cloudformation*.json"
find . -name "pulumi.*"
find . -name "*.k8s.yaml" -o -name "kubernetes/*.yaml"
find . -name "docker-compose*.yaml"
```

### 2. Dispatch to Infrastructure Engineer

```python
Task(
    subagent_type="wicked-garden:platform:infrastructure-engineer",
    prompt="""Review infrastructure-as-code and cloud architecture.

Files: {discovered or specified IaC files}
Platform: {detected from files - Terraform, CloudFormation, K8s, etc.}

Analysis Checklist:
1. Resource configuration and sizing - Appropriate instance types, storage
2. Security posture:
   - IAM permissions (least privilege)
   - Network segmentation
   - Encryption at rest and in transit
   - No hardcoded secrets
3. Cost optimization opportunities - Reserved instances, rightsizing
4. High availability setup - Multi-AZ, redundancy
5. Disaster recovery readiness - Backups, cross-region
6. Best practices compliance - Platform-specific guidelines

Return Format:
- Resource inventory table
- Security assessment matrix
- Cost optimization opportunities with savings estimates
- High availability status and recommendations
- Best practice violations with fixes
- Prioritized recommendations (critical fixes, then improvements)
"""
)
```

### 3. Analyze IaC

For Terraform:
- Resource configuration
- Module usage
- State management
- Variable handling

For Kubernetes:
- Resource requests/limits
- Pod security
- Network policies
- ConfigMaps/Secrets handling

### 4. Security Check

Verify:
- [ ] No hardcoded secrets
- [ ] IAM least privilege
- [ ] Network segmentation
- [ ] Encryption enabled
- [ ] Logging configured

### 5. Deliver Infrastructure Report

```markdown
## Infrastructure Review

**Scope**: {files/directories reviewed}
**Platform**: {AWS/GCP/Azure/K8s}

### Resource Inventory
| Resource | Type | Configuration |
|----------|------|---------------|
| {name} | {type} | {key settings} |

### Security Assessment
| Check | Status | Finding |
|-------|--------|---------|
| IAM | {status} | {finding} |
| Network | {status} | {finding} |
| Encryption | {status} | {finding} |

### Cost Optimization
1. {opportunity with savings estimate}

### High Availability
- Current: {setup}
- Recommendation: {improvement}

### Best Practice Violations
1. {violation with fix}

### Recommendations
**Priority**:
1. {critical fix}

**Improvements**:
1. {enhancement}
```

## Example

```
User: /wicked-garden:platform:infra terraform/

Claude: I'll review your Terraform infrastructure.

[Finds terraform files]
[Analyzes resources and configuration]

## Infrastructure Review: terraform/

**Platform**: AWS
**Provider Version**: 5.0

### Resource Inventory
| Resource | Type | Configuration |
|----------|------|---------------|
| main-vpc | aws_vpc | 10.0.0.0/16, 3 AZs |
| web-asg | aws_autoscaling_group | min=2, max=10, t3.medium |
| rds-primary | aws_db_instance | db.r5.large, Multi-AZ |
| api-lambda | aws_lambda_function | 512MB, 30s timeout |

### Security Assessment
| Check | Status | Finding |
|-------|--------|---------|
| IAM Policies | WARN | Lambda has overly broad permissions |
| Security Groups | PASS | Properly restricted |
| Encryption | PASS | RDS and S3 encrypted |
| Secrets | FAIL | DB password in tfvars |

### Security Issues

1. **Hardcoded secret** - `terraform/rds.tf:12`
```hcl
# INSECURE
password = "SuperSecret123!"
```
Fix: Use AWS Secrets Manager
```hcl
password = data.aws_secretsmanager_secret_version.db.secret_string
```

2. **Overly permissive Lambda role** - `terraform/lambda.tf:34`
```hcl
# Current: Full S3 access
actions = ["s3:*"]

# Recommended: Specific permissions
actions = ["s3:GetObject", "s3:PutObject"]
resources = ["arn:aws:s3:::my-bucket/*"]
```

### Cost Optimization

1. **RDS Reserved Instance** - Save ~40%
   - Current: On-demand db.r5.large = $175/month
   - Reserved (1yr): ~$105/month
   - Savings: $840/year

2. **Lambda Memory** - Currently over-provisioned
   - Current: 512MB, avg usage 128MB
   - Recommended: 256MB (50% cost reduction)

### High Availability
- VPC spans 3 AZs ✓
- ASG min=2 across AZs ✓
- RDS Multi-AZ enabled ✓
- **Gap**: No cross-region DR setup

### Priority Fixes
1. Move DB password to Secrets Manager
2. Scope down Lambda IAM permissions
```
