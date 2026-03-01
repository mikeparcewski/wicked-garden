---
name: trust-safety-audit
title: Trust and Safety Audit
description: Deep safety audit of an agentic system with risk classification and compliance validation
type: review
difficulty: advanced
estimated_minutes: 12
---

# Trust and Safety Audit

This scenario validates that wicked-agentic's audit command performs a comprehensive safety analysis, correctly classifies tool risks, identifies missing human-in-the-loop gates, and generates a compliance-ready report.

## Setup

Create a Python research agent with mixed risk profile — some tools well-protected, others dangerously exposed:

```bash
mkdir -p ~/test-wicked-agentic/research-agent/src/tools
cd ~/test-wicked-agentic/research-agent

cat > requirements.txt <<'EOF'
crewai==0.1.0
openai==1.0.0
requests==2.31.0
EOF

# Low-risk tool (well implemented)
cat > src/tools/search.py <<'EOF'
import requests

def web_search(query: str, max_results: int = 5) -> list:
    """Search the web for information. Returns list of results."""
    if not query or len(query) > 500:
        raise ValueError("Invalid query")
    # Read-only external search
    response = requests.get("https://api.search.example.com", params={"q": query, "n": max_results})
    response.raise_for_status()
    return response.json()["results"]
EOF

# High-risk tool (no HITL, no validation)
cat > src/tools/email.py <<'EOF'
import smtplib
from email.message import EmailMessage

def send_email(to: str, subject: str, body: str) -> bool:
    """Send an email. No validation or approval required."""
    msg = EmailMessage()
    msg["To"] = to          # No recipient validation
    msg["Subject"] = subject
    msg.set_content(body)   # No content sanitization

    with smtplib.SMTP("smtp.company.com") as smtp:
        smtp.send_message(msg)
    return True
EOF

# Critical-risk tool (arbitrary code execution, no protection)
cat > src/tools/code_runner.py <<'EOF'
import subprocess

def execute_code(code: str) -> str:
    """Execute Python code. Used for data analysis."""
    # No sandbox, no HITL, no validation
    result = subprocess.run(
        ["python3", "-c", code],
        capture_output=True, text=True
    )
    return result.stdout
EOF

# Main agent
cat > src/agent.py <<'EOF'
from crewai import Agent, Task, Crew
from src.tools.search import web_search
from src.tools.email import send_email
from src.tools.code_runner import execute_code

researcher = Agent(
    role="Research Analyst",
    goal="Research topics and send findings via email",
    tools=[web_search, send_email, execute_code]
)
EOF
```

## Steps

### 1. Run Basic Safety Audit

```bash
/wicked-agentic:audit ~/test-wicked-agentic/research-agent
```

**Expected**:
- Framework detected as CrewAI
- All 3 tools analyzed for risk
- Safety reviewer spawned in deep audit mode
- Risk matrix populated with CRITICAL/HIGH/MEDIUM/LOW classifications
- HITL gap analysis performed

### 2. Verify Risk Classification

The risk matrix should correctly classify:

```
### Critical Risk Tools (1)
| Tool | Risk | Current Mitigations | Required Mitigations | Status |
|------|------|---------------------|---------------------|--------|
| execute_code | CRITICAL | None | Sandbox + HITL + Code review | UNPROTECTED |

### High Risk Tools (1)
| Tool | Risk | Current Mitigations | Required Mitigations | Status |
|------|------|---------------------|---------------------|--------|
| send_email | HIGH | None | HITL + Validation + Rate limit | UNPROTECTED |

### Medium & Low Risk
| web_search | MEDIUM | Input validation, read-only | Rate limiting | PARTIAL |
```

### 3. Verify HITL Assessment

Human-in-the-loop section should show:

```
### HITL Violations

1. execute_code - src/tools/code_runner.py
   - Risk: Arbitrary code execution
   - Current: No approval gate
   - Required: Human confirmation before execution

2. send_email - src/tools/email.py
   - Risk: Email sending to arbitrary recipients
   - Current: No approval gate
   - Required: Human confirmation for external recipients
```

### 4. Run GDPR Compliance Audit

```bash
/wicked-agentic:audit ~/test-wicked-agentic/research-agent --standard GDPR
```

**Expected**:
- Standard compliance section added to report
- GDPR requirements checked (data minimization, right to erasure, etc.)
- Compliance score calculated (likely low given no PII handling)
- Critical GDPR gaps called out

### 5. Save Audit to File

```bash
/wicked-agentic:audit ~/test-wicked-agentic/research-agent --output ~/test-wicked-agentic/safety-audit.md
```

**Expected**:
- Full audit runs
- Report written to file
- Confirmation: "Safety audit report written to ~/test-wicked-agentic/safety-audit.md"
- Summary shown inline

## Expected Outcome

```markdown
# Trust & Safety Audit Report

**Overall Risk**: CRITICAL

Key findings:
- **Critical issues**: 1 (execute_code without sandbox or HITL)
- **High-risk tools**: 1 (send_email without validation)
- **Missing HITL gates**: 2
- **PII handling gaps**: 2+ (email addresses in logs, no redaction)

**Recommendation**: REQUIRES IMMEDIATE REMEDIATION before production use.

## Security Scorecard

| Category | Score | Status |
|----------|-------|--------|
| Tool Risk Management | 2/10 | CRITICAL |
| Human-in-the-Loop | 1/10 | CRITICAL |
| PII Handling | 3/10 | NEEDS WORK |
```

## Success Criteria

- [ ] Framework detected as CrewAI
- [ ] `execute_code` classified as CRITICAL risk
- [ ] `send_email` classified as HIGH risk
- [ ] `web_search` classified as MEDIUM risk (has basic validation)
- [ ] Both HITL violations identified
- [ ] Safety reviewer spawned via Task tool
- [ ] GDPR compliance section appears when `--standard GDPR` used
- [ ] Overall risk rated CRITICAL or HIGH
- [ ] Remediation roadmap covers Phase 1 critical fixes
- [ ] `--output` flag saves report to file
- [ ] Scorecard shows low scores for risk management and HITL

## Value Demonstrated

**Problem solved**: Security reviews of agentic systems require specialized knowledge of agentic attack vectors — prompt injection, HITL bypass, tool misuse — that standard security reviewers don't know to look for.

**Real-world value**:
- **Risk classification**: Instantly categorizes tools by danger level so you know what to fix first
- **HITL gaps**: Identifies exactly where human oversight is missing before attackers find it
- **Compliance**: Generates audit trail documentation for GDPR/HIPAA/SOC2 reviews
- **Prioritized remediation**: Phase-based roadmap focuses effort on highest-risk items

This replaces security reviews where reviewers mark "uses external APIs" as a checkbox without understanding the full risk surface of an agentic system that can send emails, execute code, and access databases autonomously.
