# Audit Evidence Collection Rubric

Collect audit evidence, verify controls, and generate compliance artifacts for SOC2/HIPAA/GDPR/PCI.

## Step 1: Parse Arguments

`$ARGUMENTS` = `<framework> [control_id]`
- Framework: `soc2` | `hipaa` | `gdpr` | `pci`
- Control: specific control ID (e.g., `CC6.1`) or `all`

## Step 2: Evidence Collection Checklist

### Define Scope
- [ ] Systems in scope for this audit
- [ ] Compliance framework and controls to test
- [ ] Audit period (start/end date)
- [ ] Evidence sources available

### Design Evidence (Architecture + Policy)
```bash
# Find architecture docs
find . -name "*.md" -path "*/docs/*" | xargs grep -l "architecture\|diagram\|security\|incident" 2>/dev/null | head -10

# Find policy documents
find . -path "*/policies/*" -o -name "*policy*.md" -o -name "*incident*response*.md" 2>/dev/null | head -10
```

### Implementation Evidence (Code + Config)

**Access Control (CC6.1, HIPAA 164.312(a))**:
```bash
grep -rn "authenticate\|require.*auth\|login\|authorize\|require.*role\|permission" --include="*.py" --include="*.ts" --include="*.js" -l
```

**Encryption (CC6.6, GDPR Art 32)**:
```bash
grep -rn "encrypt\|cipher\|AES\|crypto\|tls\|ssl" --include="*.py" --include="*.ts" -l
grep -rn "key.*management\|kms\|vault\|secrets" --include="*.yml" --include="*.yaml" -l
```

**Audit Logging (CC7.2, HIPAA 164.312(b))**:
```bash
grep -rn "audit.*log\|access.*log\|security.*event\|log.*retention" --include="*.py" --include="*.ts" -l
```

### Operational Evidence
```bash
# Access logs sample
tail -n 100 /var/log/access.log 2>/dev/null || echo "No access log found at /var/log/access.log"

# Audit log sample
tail -n 100 /var/log/audit.log 2>/dev/null || echo "No audit log found"
```

## Step 3: Control Testing

For each control:
1. Locate the implementation (file:line)
2. Review design (does it match the requirement?)
3. Verify effectiveness (is it enforced, not just present?)
4. Document: Pass / Partial / Fail + evidence ref

### SOC2 Trust Service Criteria (key controls)
| Control | Requirement | Test |
|---------|-------------|------|
| CC6.1 | Logical access controls | Auth middleware, RBAC code |
| CC6.6 | Encryption of confidential data | AES/TLS implementation |
| CC6.7 | Transmission security | TLS config, HTTPS enforcement |
| CC7.2 | System monitoring | Logging, alerting config |

Full SOC2 + HIPAA evidence checklists: `refs/checklists-soc2-hipaa.md`
GDPR + PCI checklists: `refs/checklists-gdpr-pci-evidence.md`
Evidence collection scripts and organization: `refs/checklists-evidence-operations.md`

## Step 4: Gap Analysis

Common gaps to check:
- **Missing evidence**: no docs, no logs, no test results, no policies
- **Incomplete implementation**: partial controls, inconsistent application
- **Insufficient testing**: no control testing, no pen testing, no compliance verification

## Step 5: Bus Events

After the audit result is finalized, emit ONE event:

```bash
# On pass (all in-scope controls passing, no P0/P1 gaps):
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_bus_emit.py" wicked.garden.compliance.passed '{"framework":"{soc2|hipaa|gdpr|pci}","checks_passed_count":{N},"chain_id":"{chain_id}"}' 2>/dev/null || true

# On fail (any failing control or identified gap):
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_bus_emit.py" wicked.garden.compliance.failed '{"framework":"{soc2|hipaa|gdpr|pci}","gap_count":{N},"severity_max":"{critical|high|medium|low}","chain_id":"{chain_id}"}' 2>/dev/null || true
```

## Output Format

```markdown
## Audit Report

**Audit Date**: {date}
**Framework**: {SOC2 | HIPAA | GDPR | PCI}
**Scope**: {systems/components}
**Period**: {audit period}

### Executive Summary

**Overall Status**: {READY | NEEDS WORK | NOT READY}
**Controls Tested**: {count}  **Passing**: {count}  **Failing**: {count}
**Evidence Collected**: {count artifacts}

{1-2 sentence summary}

### Controls Tested

| Control ID | Description | Status | Evidence | Notes |
|------------|-------------|--------|----------|-------|
| CC6.1 | Access controls | PASS | auth.py:15-45 | RBAC enforced |
| CC7.2 | Monitoring | FAIL | — | Missing security alerts |

### Evidence Collected

#### Design Evidence
1. {doc name} — {path}

#### Implementation Evidence
1. Access Control — {file:line}
2. Encryption — {file:line}
3. Audit Logging — {file:line}

#### Operational Evidence
1. Access Logs — {path} ({retention days} days)

### Gaps Identified

#### Critical (P0)
1. **{gap}** — Control: {ID} — Impact: {description} — Remediation: {steps}

#### High Priority (P1)
1. **{gap}** — {fix}

### Certification Readiness

**{Framework}**: {READY | NEEDS WORK | NOT READY}
- Blockers: {P0 count} P0 findings
- Timeline: {estimate} to address
```
