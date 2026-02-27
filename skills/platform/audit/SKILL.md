---
name: audit
description: |
  Audit evidence collection and trail verification. Gathers artifacts,
  validates controls, generates audit reports, and maintains compliance
  documentation.

  Use when: "audit trail", "collect evidence", "audit report",
  "control testing", "compliance documentation"
---

# Audit Skill

Collect evidence and verify audit trails for compliance.

## When to Use

- Preparing for external audit
- Collecting evidence for compliance certification
- Verifying audit trail completeness
- Generating audit reports
- User says "audit", "evidence", "audit trail", "control testing"

## Commands

```bash
/wicked-garden:platform:audit [--controls] [--trail] [--report]
```

## Audit Process

### 1. Define Scope

Identify audit targets:
- Code components
- Data flows
- Access controls
- Infrastructure
- Processes

### 2. Collect Evidence

**Code Evidence**:
- Access control implementation
- Encryption usage
- Input validation
- Error handling
- Logging statements

**Configuration Evidence**:
- TLS/SSL settings
- Database encryption
- Key management
- Network policies
- IAM roles

**Documentation Evidence**:
- Architecture diagrams
- Data flow diagrams
- Security policies
- Incident response plans

**Operational Evidence**:
- Access logs
- Audit logs
- Security events
- Change logs

See [refs/checklists.md](refs/checklists.md) for comprehensive evidence checklists.

### 3. Verify Controls

Test each control:

```bash
# Check encryption
grep -r "encrypt\|cipher\|AES\|TLS" {target}

# Check access controls
grep -r "authorize\|authenticate\|require.*auth" {target}

# Check audit logging
grep -r "log\|audit\|event" {target}
```

See [refs/frameworks.md](refs/frameworks.md) for framework-specific control testing procedures.

### 4. Document Gaps

Identify:
- Controls without evidence
- Incomplete audit trails
- Missing documentation
- Configuration gaps

### 5. Generate Report

Create report with:
- Controls tested
- Evidence collected
- Gaps identified
- Recommendations
- Risk assessment

## Evidence Types

| Type | Description | Examples |
|------|-------------|----------|
| **Design** | Architecture | Diagrams, specs, policies |
| **Implementation** | Code | Functions, configs, tests |
| **Operational** | Runtime | Logs, metrics, incidents |
| **Process** | Procedural | Approvals, reviews, training |

## Integration

### With wicked-kanban

Store evidence as artifacts:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py" add-artifact \
  "{task_id}" "file" \
  --file-path "{evidence_path}" \
  --label "Audit Evidence: {control_id}"
```

### With wicked-search

Find related evidence:
```bash
/wicked-garden:search:code "audit|logging|encrypt" --path {target}
```

## Output Format

```markdown
## Audit Report: {Framework}

**Status**: {READY|NEEDS WORK|NOT READY}
**Controls Tested**: {count} | **Gaps**: {count}

### Controls Tested
| ID | Status | Evidence |
|----|--------|----------|
| CC6.1 | PASS | auth.py:15 |
| CC7.2 | FAIL | Missing |

### Evidence
- Design: docs/arch.md
- Code: src/auth.py, src/crypto.py
- Operational: /var/log/audit.log

### Critical Gaps (P0)
1. Missing admin audit trail
2. No TLS for PII endpoints

### Recommendations
1. Fix P0 gaps before certification
2. Schedule follow-up audit
```

## Quality Standards

Good audit evidence:
- Specific file/line references
- Clear control mapping
- Complete artifact trails
- Risk-prioritized gaps

Bad audit evidence:
- Generic statements
- No source references
- Missing artifacts
