---
name: api-health-check
description: Validate API health endpoint returns 200 with expected JSON payload
category: api
tools:
  required: [curl]
  optional: [hurl]
difficulty: basic
timeout: 30
---

# API Health Check

Validates that an API health endpoint is responsive and returns the expected JSON structure.

## Setup

```bash
# Using httpbin.org as a reliable public test endpoint
export API_URL="https://httpbin.org"
```

## Steps

### Step 1: Basic connectivity check (curl)

```bash
curl -sf --max-time 10 "${API_URL}/get" -o /dev/null -w '%{http_code}'
```

**Expect**: Exit code 0, HTTP 200 response

### Step 2: JSON response validation (curl)

```bash
curl -sf --max-time 10 "${API_URL}/get" -H "Accept: application/json" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'url' in d, 'Missing url field'; print('OK: JSON valid with url field')"
```

**Expect**: Exit code 0, JSON parsed successfully with expected field

### Step 3: Detailed assertions with hurl (hurl)

```bash
if ! command -v hurl &>/dev/null; then
  echo "SKIP: hurl not installed. Run /wicked-garden:scenarios:setup to install."
  exit 0
fi
cat > "${TMPDIR:-/tmp}/wicked-scenario-hurl.hurl" << 'HURL_EOF'
GET https://httpbin.org/get
HTTP 200
[Asserts]
header "Content-Type" contains "application/json"
jsonpath "$.url" == "https://httpbin.org/get"
HURL_EOF
hurl --test "${TMPDIR:-/tmp}/wicked-scenario-hurl.hurl"
```

**Expect**: All hurl assertions pass

## Cleanup

```bash
rm -f "${TMPDIR:-/tmp}/wicked-scenario-hurl.hurl"
```
