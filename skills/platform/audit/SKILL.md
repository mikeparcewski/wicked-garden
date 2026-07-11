---
name: wicked-garden-platform-audit
description: |
  Audit evidence collection and trail verification. Gathers artifacts,
  validates controls, generates audit reports, and maintains compliance
  documentation.

  Use when: "audit trail", "collect evidence", "audit report",
  "control testing", "compliance documentation", "gather audit evidence for
  SOC2/HIPAA/GDPR/PCI", or any former /wicked-garden:platform:audit
  invocation. NOT for defining compliance policies (use the compliance
  sub-skill) or ad hoc security checks (use the platform domain skill's
  security action).
phase_relevance: ["build", "review", "operate"]
archetype_relevance: ["*"]
---

# Audit Skill

Collect evidence and verify audit trails for compliance.

## When to Use

- Preparing for external audit
- Collecting evidence for compliance certification
- Verifying audit trail completeness
- Generating audit reports
- User says "audit", "evidence", "audit trail", "control testing"

## Run it inline (no dispatch)

Invoked as `<framework> [control_id|all]`:

1. Parse args: `<framework> [control_id]` (framework = `soc2|hipaa|gdpr|pci`;
   control_id or `all`).
2. `Read("${CLAUDE_PLUGIN_ROOT}/skills/platform/audit/refs/audit.md")` — full
   collection rubric, control-testing checklist, SOC2/HIPAA control matrix,
   gap analysis, bus emit, and output format.
3. For framework-specific checklists:
   `Read("${CLAUDE_PLUGIN_ROOT}/skills/platform/audit/refs/checklists-soc2-hipaa.md")`
   or `refs/checklists-gdpr-pci-evidence.md`. For evidence scripts and
   organization: `refs/checklists-evidence-operations.md`.
4. Apply the rubric directly: collect evidence via code search, verify each
   control, document Pass/Partial/Fail with file:line refs, then emit the bus
   event and produce the audit report.

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

See [refs/checklists-soc2-hipaa.md](refs/checklists-soc2-hipaa.md), [refs/checklists-gdpr-pci-evidence.md](refs/checklists-gdpr-pci-evidence.md), and [refs/checklists-evidence-operations.md](refs/checklists-evidence-operations.md) for comprehensive evidence checklists.

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

See [refs/frameworks-soc2-hipaa.md](refs/frameworks-soc2-hipaa.md) and [refs/frameworks-gdpr-pci.md](refs/frameworks-gdpr-pci.md) for framework-specific control testing procedures.

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

### With native tasks

Attach audit evidence by appending to the task description (reference file paths checked into the repo):
```
TaskUpdate(
  taskId="{task_id}",
  description="{previous}\n\n## Audit Evidence: {control_id}\nEvidence file: {evidence_path}"
)
```

### With wicked-brain

Find related evidence (FTS5 over indexed code):
```bash
wicked-brain:search "audit|logging|encrypt"
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
