# Evidence Schema

Full field definitions with natural language detection indicators per tier.
These replace the 58 regex patterns from evidence.py with human-readable
detection instructions. A single indicator match is sufficient.

Detection is case-insensitive in all cases.

---

## Low Tier (complexity 1-2)

Required: `test_results`, `code_diff`

---

### Field: test_results

**Label**: `"Test results (e.g. '- Test: test_name — PASS/FAIL')"`

Detect as present if the description contains ANY of:

| Indicator | Example |
|-----------|---------|
| Word "test" near word "pass/fail/passed/failed" (same sentence) | "unit tests passed" |
| Word "pass/fail/passed/failed" near word "test" (same sentence) | "failed 2 tests" |
| Pattern `- Test:` followed by `— PASS` or `— FAIL` | `- Test: auth_test — PASS` |
| Phrase "tests pass" / "tests fail" / "tests passing" / "tests failing" | "all tests passing" |
| Phrase "unit test" | "unit test coverage" |
| Phrase "test results" | "see test results below" |

Not present if: description only mentions "test" without any pass/fail signal
(e.g., "will test later" does NOT count).

---

### Field: code_diff

**Label**: `"Code diff reference (e.g. '- Code diff: ...' or '- File: path — modified/created')"`

Detect as present if the description contains ANY of:

| Indicator | Example |
|-----------|---------|
| Phrase "code diff" | "code diff applied" |
| Pattern `- File:` followed by `— modified/created/updated/deleted/added` | `- File: auth.py — modified` |
| Phrase "changed files" or "changed file" | "changed files: auth.py" |
| Word "modified" near a known source extension (.py, .ts, .js, .go, .rs, .java, .rb, .tsx, .jsx, .cs, .swift, .kt) | "modified auth.py" |
| Known source extension near "modified/created/updated" | "auth.py updated" |
| Standalone word "patch" | "patch applied" |
| Phrase "diff" near "line" | "diff shows 12 lines changed" |

Not present if: description mentions file names without any action word (e.g.,
"see auth.py" without modified/created/updated).

---

## Medium Tier (complexity 3-4)

Required: all Low fields + `verification`

---

### Field: verification

**Label**: `"Verification step (e.g. '- Verification: curl ... returns 200' or command output)"`

Detect as present if the description contains ANY of:

| Indicator | Example |
|-----------|---------|
| Word "verify", "verified", "verification" | "verified in staging" |
| Pattern `- Verification:` | `- Verification: curl /api/health → 200` |
| Phrase "confirmed working" | "confirmed working in dev" |
| Phrase "manually tested" | "manually tested the flow" |
| Phrase "smoke test" | "smoke test passed" |
| Phrase "checked in staging" | "checked in staging — OK" |
| Phrase "staging confirmed" | "staging confirmed behavior" |
| Word "validated" | "validated against acceptance criteria" |
| Word "curl" near "return/returns/returned" | "curl returns 200" |
| Word "response" near HTTP status code (200/201/204) | "response 200 OK" |

Not present if: description says "needs verification" or "to be verified"
without actually reporting a result.

---

## High Tier (complexity 5-7)

Required: all Medium fields + `performance` + `assumptions`

---

### Field: performance

**Label**: `"Performance data (e.g. latency, throughput, benchmark results)"`

Detect as present if the description contains ANY of:

| Indicator | Example |
|-----------|---------|
| Word "performance" near "test/metric/benchmark/result/data" | "performance test results" |
| Pattern `- Performance:` | `- Performance: p99 = 45ms` |
| Pattern `- Benchmark:` | `- Benchmark: 1200 rps` |
| Word "latency" | "latency improved" |
| Word "throughput" | "throughput: 500 rps" |
| Pattern like "p50/p95/p99" near "ms" | "p99 = 120ms" |
| Word "rps" | "sustained 800 rps" |
| Phrase "ops/sec" | "5000 ops/sec" |
| Word "benchmark" | "benchmark shows improvement" |
| Word "profile" near "result/output/data" | "profiler output attached" |
| Word "metric" or "metrics" near "show/indicate/report" | "metrics indicate 30% improvement" |
| Phrase "load test" | "load test passed" |

---

### Field: assumptions

**Label**: `"Documented assumptions (e.g. '## Assumptions' section or '- Assumption:')"`

Detect as present if the description contains ANY of:

| Indicator | Example |
|-----------|---------|
| Header `## Assumptions` | `## Assumptions` section |
| Pattern `- Assumption:` | `- Assumption: Python 3.10+` |
| Word "assuming" | "assuming the DB is available" |
| Word "assumption" or "assumptions" followed by `:` | "Assumptions: X, Y" |
| Word "precondition" | "precondition: service running" |
| Phrase "requires" near "pre-exist" | "requires pre-existing config" |

---

## Summary Table

| Field | Tier | Simplest indicator |
|-------|------|-------------------|
| test_results | low+ | `- Test: name — PASS` |
| code_diff | low+ | `- File: path — modified` |
| verification | medium+ | `- Verification: ...` |
| performance | high | `- Performance: ...` or `- Benchmark: ...` |
| assumptions | high | `## Assumptions` section |

---

## Important: What Does NOT Count

These do NOT satisfy evidence requirements:

- Future tense: "will test", "to be verified", "benchmark TBD"
- Vague assertion without specifics: "tests pass" with no actual test named
- File name mention without action: "see auth.py" is not a code diff reference
- Plans: "I will add a benchmark" is not a performance data entry
