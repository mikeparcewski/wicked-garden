---
name: perf-load-test
description: API endpoint load test with response time thresholds
category: perf
tools:
  required: [hey]
  optional: [k6]
difficulty: intermediate
timeout: 120
---

# Performance Load Test

Runs a quick load test against an API endpoint and validates response time thresholds.

## Setup

```bash
export TARGET_URL="https://httpbin.org/get"
```

## Steps

### Step 1: Quick load test with hey (hey)

```bash
if ! command -v hey &>/dev/null; then
  echo "SKIP: hey not installed. Run /wicked-garden:scenarios:setup to install."
  exit 0
fi
hey -n 100 -c 10 -t 10 "${TARGET_URL}" 2>&1 | tee "${TMPDIR:-/tmp}/hey-results.txt" && grep -q "Status code distribution" "${TMPDIR:-/tmp}/hey-results.txt"
```

**Expect**: Exit code 0, 100 requests complete with status code distribution shown

### Step 2: Threshold-based load test with k6 (k6)

```bash
if ! command -v k6 &>/dev/null; then
  echo "SKIP: k6 not installed. Run /wicked-garden:scenarios:setup to install."
  exit 0
fi
cat > "${TMPDIR:-/tmp}/wicked-scenario-k6.js" << 'K6_EOF'
import http from 'k6/http';
import { check } from 'k6';

export const options = {
  vus: 5,
  duration: '10s',
  thresholds: {
    http_req_duration: ['p(95)<2000'],
    http_req_failed: ['rate<0.1'],
  },
};

export default function () {
  const res = http.get('https://httpbin.org/get');
  check(res, { 'status is 200': (r) => r.status === 200 });
}
K6_EOF
k6 run "${TMPDIR:-/tmp}/wicked-scenario-k6.js"
```

**Expect**: Exit code 0 if thresholds met, non-zero if p95 > 2s or error rate > 10%

## Cleanup

```bash
rm -f "${TMPDIR:-/tmp}/hey-results.txt" "${TMPDIR:-/tmp}/wicked-scenario-k6.js"
```
