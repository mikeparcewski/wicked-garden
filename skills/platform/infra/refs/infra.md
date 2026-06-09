# Infrastructure-as-Code Review Rubric

Review IaC and cloud architecture for security, cost, HA, and best-practice posture.
Covers: Terraform/OpenTofu, CloudFormation, Pulumi, Kubernetes manifests, docker-compose.

## Step 1: Discover IaC Files

Parse `$ARGUMENTS` (path or `scan`). When `scan`, discover:
```bash
find . -name "*.tf" -o -name "*.tfvars" 2>/dev/null
find . -name "cloudformation*.yaml" -o -name "cloudformation*.json" 2>/dev/null
find . -name "pulumi.yaml" 2>/dev/null
find . -name "*.k8s.yaml" -o -path "*/kubernetes/*.yaml" 2>/dev/null
find . -name "docker-compose*.yaml" -o -name "docker-compose*.yml" 2>/dev/null
```

Detect platform (AWS/GCP/Azure/K8s/Docker) from content.

## Step 2: Security Matrix

- [ ] No hardcoded credentials or secrets (use Secrets Manager / KMS / env vars)
- [ ] IAM: least-privilege — no `*` actions, no `*` resources without justification
- [ ] Network: security groups / firewall rules restrict ingress; no `0.0.0.0/0` on sensitive ports
- [ ] Encryption at rest: storage volumes, DB, S3 buckets encrypted
- [ ] Encryption in transit: TLS enabled on all endpoints
- [ ] Public exposure: no inadvertently public buckets, DBs, or APIs

## Step 3: Cost Optimization

- [ ] Instance/resource sizing justified by actual load (not over-provisioned)
- [ ] Unused or orphaned resources (old snapshots, unattached volumes)
- [ ] Spot/preemptible instances for non-critical workloads
- [ ] S3/GCS lifecycle policies for infrequently accessed data
- [ ] Reserved instances / savings plans for steady-state compute

## Step 4: High Availability & DR

- [ ] Multi-AZ deployment for stateful services
- [ ] Auto-scaling configured for compute tier
- [ ] Database: Multi-AZ / read replicas / failover configured
- [ ] Load balancer with health checks
- [ ] Backup strategy defined and tested
- [ ] DR plan: RTO and RPO documented

## Step 5: Platform Best Practices

### Terraform/OpenTofu
- [ ] Remote state with locking (S3+DynamoDB, GCS, Terraform Cloud)
- [ ] Version constraints on providers
- [ ] Variables parameterized (no hardcoded values in `.tf`)
- [ ] Modules used for reusability
- [ ] Resource tagging (env, team, cost-center)

### Kubernetes
- [ ] Resource `requests` and `limits` on all containers
- [ ] `livenessProbe` and `readinessProbe` configured
- [ ] RBAC: minimal `ServiceAccount` permissions
- [ ] Network policies defined
- [ ] ConfigMaps/Secrets for configuration (no env vars with secrets in manifests)

### Docker Compose
- [ ] No `privileged: true` unless required
- [ ] Port bindings limited to necessary ports
- [ ] Named volumes for persistent data
- [ ] Health checks on dependent services

## Output Format

```markdown
## Infrastructure Review: {platform}

**IaC Tool**: {Terraform | CloudFormation | Pulumi | K8s | Docker Compose}
**Files reviewed**: {list}

### Resource Inventory
{table: resource type, name, region/zone, sizing}

### Security Matrix
| Control | Status | Evidence / Issue |
|---------|--------|-----------------|
| No hardcoded secrets | ✓/✗ | {location if ✗} |
| IAM least-privilege | ✓/✗ | {issue if ✗} |
| Network segmentation | ✓/✗ | {issue if ✗} |
| Encryption at rest | ✓/✗ | {issue if ✗} |
| Encryption in transit | ✓/✗ | {issue if ✗} |

### Cost Opportunities
| Item | Current | Recommendation | Est. Savings |
|------|---------|---------------|-------------|
| {resource} | {spec} | {change} | ${amount}/mo |

### HA Gaps
{list of missing HA components with risk level}

### Prioritized Fixes
**Critical** (security/data-loss risk):
1. {issue} — {file:line} — {fix}

**High** (HA/cost):
2. {issue} — {fix}

**Improvements**:
3. {suggestion}
```
