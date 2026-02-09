---
name: policy
description: |
  Policy interpretation and compliance guidance. Translates regulatory
  requirements into actionable controls, maps policies to code, and
  provides implementation guidance.

  Use when: "policy", "what does this mean", "how to implement",
  "policy guidance", "requirements translation"
---

# Policy Skill

Interpret policies and translate into actionable requirements.

## When to Use

- User needs policy interpretation
- Translating regulatory requirements to controls
- Mapping policies to implementation
- Gap analysis against policies
- User says "policy", "requirement", "what does this mean", "how do I comply"

## Commands

```bash
/wicked-platform:policy [--map] [--gap] [--guide]
```

## Policy Types

| Type | Examples | Focus |
|------|----------|-------|
| **Regulatory** | GDPR, HIPAA, PCI | Legal requirements |
| **Industry** | ISO 27001, NIST | Best practices |
| **Corporate** | Security, Data policies | Internal rules |
| **Contractual** | SLA, BAA, DPA | Agreement terms |

## Analysis Process

### 1. Parse Policy

Extract requirements:
- MUST requirements (mandatory)
- SHOULD requirements (recommended)
- MAY requirements (optional)
- Exceptions and conditions

### 2. Map to Controls

Translate to technical controls:

**Policy**: "Personal data must be encrypted"

**Controls**:
- Encryption at rest (database, files)
- Encryption in transit (TLS)
- Key management
- Encryption verification

See [refs/frameworks.md](refs/frameworks.md) for detailed policy-to-control mappings.

### 3. Identify Applicability

Determine scope:
- Which systems
- Which data types
- Which processes
- Which roles responsible

### 4. Assess Current State

Check what exists:
- Controls implemented
- Controls documented
- Controls tested
- Evidence collected

### 5. Identify Gaps

Find missing:
- Missing controls
- Incomplete implementation
- Insufficient documentation
- Inadequate testing

See [refs/checklists.md](refs/checklists.md) for implementation checklists and gap analysis templates.

### 6. Provide Guidance

Recommend:
- Implementation steps
- Code examples
- Configuration guidance
- Documentation templates

## Gap Analysis

### Assessment Matrix

| Requirement | Current | Gap | Priority | Action |
|-------------|---------|-----|----------|--------|
| Encrypt PII | DB only | Files missing | P0 | Add file encryption |
| Access logs | Basic | Missing details | P1 | Enhance logging |
| Retention | None | No policy | P1 | Define policy |

### Gap Categories

**P0 - Critical**: Legal violation, must fix immediately
**P1 - High**: Best practice gap, fix soon
**P2 - Medium**: Improvement, plan for next iteration

## Integration

### With wicked-kanban

Create remediation tasks:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/../wicked-kanban/scripts/kanban.py" add-task \
  --name "Implement {control}" \
  --description "Policy: {policy}\nGap: {gap}" \
  --priority {P0|P1|P2}
```

### With wicked-mem

Store interpretations:
```bash
/wicked-mem:store "Policy: {name}\nInterpretation: {guidance}"
```

## Output Format

```markdown
## Policy Analysis: {Policy Name}

**Framework**: {GDPR|HIPAA|SOC2}
**Scope**: {what applies}
**Intent**: {what it achieves}

### Control Mapping
| Requirement | Control | Implementation |
|-------------|---------|----------------|
| Encrypt data | Technical | AES-256 |
| Access control | Technical | RBAC |

### Gap Analysis
| Gap | Priority | Action |
|-----|----------|--------|
| File encryption | P0 | Add AES-256 |
| Enhanced logging | P1 | Add details |

### Implementation
{Code examples}

### Next Steps
1. Fix P0 gaps
2. Collect evidence
```

## Quality Standards

Good analysis:
- Clear interpretation
- Specific controls
- Code examples
- Gap assessment

Bad analysis:
- Copying policy text
- Vague recommendations
- No implementation details
