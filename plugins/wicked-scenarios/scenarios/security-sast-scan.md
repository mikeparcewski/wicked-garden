---
name: security-sast-scan
description: Static analysis security testing on a codebase
category: security
tools:
  required: [semgrep]
difficulty: basic
timeout: 120
---

# Security SAST Scan

Runs static application security testing (SAST) against the current codebase using Semgrep. Checks for OWASP Top 10 vulnerabilities and common security anti-patterns.

## Setup

```bash
# Target the current working directory
export SCAN_TARGET="${SCAN_TARGET:-.}"
```

## Steps

### Step 1: OWASP Top 10 scan (semgrep)

```bash
if ! command -v semgrep &>/dev/null; then
  echo "SKIP: semgrep not installed. Run /wicked-scenarios:setup to install."
  exit 0
fi
semgrep scan --config p/owasp-top-ten --json --quiet "${SCAN_TARGET}" > "${TMPDIR:-/tmp}/semgrep-results.json" 2>&1
```

**Expect**: Exit code 0 = no findings, exit code 1 = findings found (treated as FAIL — security issues detected)

### Step 2: Security audit ruleset (semgrep)

```bash
if ! command -v semgrep &>/dev/null; then
  echo "SKIP: semgrep not installed. Run /wicked-scenarios:setup to install."
  exit 0
fi
semgrep scan --config p/security-audit --json --quiet "${SCAN_TARGET}" 2>&1 | python3 -c "
import sys, json
data = json.load(sys.stdin)
findings = data.get('results', [])
high = [f for f in findings if f.get('extra', {}).get('severity', '') in ('ERROR', 'WARNING')]
print(f'Findings: {len(findings)} total, {len(high)} high/critical')
if len(high) > 0:
    for f in high[:5]:
        print(f'  - {f[\"check_id\"]}: {f[\"path\"]}:{f[\"start\"][\"line\"]}')
sys.exit(1 if len(high) > 10 else 0)
"
```

**Expect**: Exit code 0 if ≤10 high-severity findings, exit code 1 if >10

## Cleanup

```bash
rm -f "${TMPDIR:-/tmp}/semgrep-results.json"
```
