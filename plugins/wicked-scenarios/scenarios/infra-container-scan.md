---
name: infra-container-scan
description: Scan a container image for vulnerabilities and misconfigurations
category: infra
tools:
  required: [trivy]
difficulty: basic
timeout: 120
---

# Infrastructure Container Scan

Scans a container image for known vulnerabilities using Trivy. Step 1 collects all HIGH/CRITICAL findings as JSON. Step 2 fails if CRITICAL vulnerabilities are found.

## Setup

```bash
# Using a well-known public image for testing
export IMAGE="alpine:3.19"
```

## Steps

### Step 1: Vulnerability scan (trivy)

```bash
trivy image --severity HIGH,CRITICAL --exit-code 0 --format json --output "${TMPDIR:-/tmp}/trivy-results.json" "${IMAGE}" && echo "Scan complete"
```

**Expect**: Exit code 0, scan completes with JSON results

### Step 2: Check for critical vulnerabilities (trivy)

```bash
trivy image --severity CRITICAL --exit-code 1 "${IMAGE}"
```

**Expect**: Exit code 0 if no critical vulns, exit code 1 if critical vulns found

## Cleanup

```bash
rm -f "${TMPDIR:-/tmp}/trivy-results.json"
```
