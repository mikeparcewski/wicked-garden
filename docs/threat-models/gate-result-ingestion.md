# Threat Model — `gate-result.json` Ingestion

**Scope:** The validation + sanitization + orphan-detection pipeline in
`scripts/crew/phase_manager.py::_load_gate_result` and its helpers
(`gate_result_schema.py`, `content_sanitizer.py`, `dispatch_log.py`,
`gate_ingest_audit.py`).

**Framing (per challenge-phase mutation CH-01):** This control is a
**FLOOR** against accidental content drift and trivial prompt-injection
in reviewer-authored free-text fields. It is **NOT** a wall against a
motivated attacker with local disk-write access. Capable attackers
remain out of scope; see §5.3.

**Issues bundled:** #479 (schema hardening) + #471 (content sanitization,
orphan detection, audit, threat model, performance cache).

---

## 1. Ingestion surface

Every call to `approve_phase` reads `phases/{phase}/gate-result.json`
and feeds the result into the rubric + consensus decision tree.
Pre-hardening, a malformed or adversarial file could:

1. Silently pass through as `None` (JSONDecodeError swallowed).
2. Carry an oversize `reason` or `conditions[]` payload that flows into
   downstream LLM prompts.
3. Carry prompt-injection text aimed at the next agent that reads the
   audit-log or consensus summary.
4. Name a banned auto-approve reviewer that the post-load banned check
   was supposed to catch but was sidesteppable by the JSONDecodeError
   silent-pass bug.

## 2. Defended attack surfaces

| Surface                              | Primary defense                      | AC    |
|--------------------------------------|--------------------------------------|-------|
| `gate-result.json` file read         | Schema validator + size caps         | AC-1, AC-2 |
| `verdict` / `result` enum            | Strict enum check                    | AC-1  |
| Required fields                      | Validator raises on missing          | AC-3  |
| Reviewer identity                    | Banned-list at load time             | AC-4  |
| Prompt-injection in free-text        | Pattern scan + allow-list            | AC-5, AC-6 |
| Unauthorized / orphan dispatch       | dispatch-log cross-reference         | AC-7  |
| Forensic trail                       | audit-log append-only (hashed)       | AC-8  |
| Hot-path latency                     | Content-hash memoization cache       | AC-11 |
| Rollback lever (per-check scoped)    | `WG_GATE_RESULT_*_VALIDATION=off`    | AC-10 |

## 3. STRIDE analysis

| STRIDE         | Attack                                                | Defense                                       | AC    |
|----------------|-------------------------------------------------------|-----------------------------------------------|-------|
| **S**poofing   | Attacker writes `gate-result.json` without dispatch   | `check_orphan` cross-references dispatch-log (orphan detection, NOT authentication — see §4 and CH-04) | AC-7 |
| **T**ampering  | Adversarial content in `reason` / `notes` / `summary` | Allow-list (permissive / strict) + injection patterns | AC-5, AC-6 |
| **R**epudiation| Reject happened but no record                         | audit-log is append-only at application layer; **degrades under the same adversary profile as S** (attacker with direct disk write can rewrite history) — cross-ref §5.3 residual risk #2 | AC-8 |
| **I**nfo-disc  | Crafted content exfiltrates session state to LLM log  | Allow-list rejects most exfil payloads        | AC-5, AC-6 |
| **D**enial-of-service | Gigabyte `reason`, deeply nested tree            | Field caps + 64 KB doc cap + list caps        | AC-2  |
| **E**levation  | `auto-approve-*` reviewer slips through               | Load-time banned-reviewer check               | AC-4  |

## 4. Honest labeling of each defense

### 4.1 Orphan detection (AC-7) — NOT authentication

Per challenge CH-04, the dispatch-log cross-reference detects **orphan**
gate-results — files written without a matching dispatch entry, typical
of a subagent that bypasses the dispatch helper. It **does not**
authenticate that the gate-result actually came from the dispatched
reviewer (that requires HMAC — see follow-up #500). The trust boundary
is "trust disk writes"; capable local attackers are explicitly out of
scope.

The soft-deprecation window (`WG_GATE_RESULT_STRICT_AFTER`, default
`2026-06-18`) accepts-with-warn for in-flight projects; after that date
the same orphan is a hard REJECT.

### 4.2 Audit log (AC-8) — NOT tamper-evident

The audit log is JSONL append-only at the filesystem layer. It records
`(event, phase, gate, reason, offending_field, violation_snippet_hash,
file_sha256, rejected_at)`. The hash of the offending value — never the
raw value — is stored so the audit log itself does not become a
re-injection vector.

Audit write failures are **non-fatal**: the reject still propagates.
This is a deliberate trade-off: we choose "reject the gate-result" over
"perfect logging" when forced to pick.

### 4.3 Threat-model limits & deferred vectors (per CH-05)

1. **Supply chain** (deferred): compromised reviewer agent via pip/npm
   dependency or malicious agent PR. Out of scope — no agent-signing
   story exists in the plugin today. Follow-up: investigate agent-
   artifact signing (large scope, separate project).
2. **Side-channel timing** (deferred): timing differences in validator
   rejection paths can leak which fields are present or which reviewer
   produced which finding. Theoretical at current load; revisit if
   crew ever runs in an adversarial / shared-tenancy deployment.
3. **Rate amplification** (mitigated inline): reject-and-retry loops
   could amplify downstream load. Mitigation plan: circuit-breaker on
   repeated rejects within a window (simple counter in `SessionState`;
   trip after N=10 rejects / 60s → refuse further ingests from that
   phase until manually reset). Landed as a follow-up, not part of
   this rollout.

## 5. Residual risks

1. **No crypto signing on `gate-result.json`** — a local attacker with
   write access can still author a valid-looking result that passes
   schema + sanitization + orphan check (by also forging a dispatch-log
   entry). Signing deferred to **#500**.
2. **Dispatch-log is append-only JSONL, not tamper-evident** — an
   attacker with disk write could rewrite history. Hash-chained
   dispatch-log is a future enhancement.
3. **Audit-log I/O failures are swallowed** (AC-8 design choice). A
   coordinated DoS on disk writes + schema attack could leave gaps in
   the audit record.
4. **Allow-list rejects some legitimate content** in strict-mode fields
   — the permissive mode (reason / conditions / notes / summary) was
   widened per CH-03 to cover CJK, Cyrillic, Greek, math, currency, em
   and en dashes, and curly quotes; machine-generated fields stay
   strict. Still, strict-mode reviewer names are ASCII-only.
5. **Regex DoS (ReDoS)** — patterns are bounded, but a future-added
   pattern could regress. Mitigation: all patterns compiled with
   explicit repetition limits; the fuzz suite includes a pattern-cost
   check.
6. **The 60-day deprecation window creates a known-soft period** for
   orphan detection. Attackers who know the timing could exploit it.
   Mitigation: the warning is audit-logged under
   `unauthorized_dispatch_accepted_legacy`, the window is deliberately
   short, and the end-date is runtime-overridable.

## 6. Ownership + runbook

- **Owner:** `repo:maintainer` — whoever merges the next release
  branch. Role-based (not an individual) so handoff is zero-ceremony.
- **Flip date:** `WG_GATE_RESULT_STRICT_AFTER` (default `2026-06-18`).
  Runtime-overridable per invocation.
- **Rollback lever — ops emergency:** push the flip date forward
  (`WG_GATE_RESULT_STRICT_AFTER=2099-01-01`), or disable a specific
  check via its scoped flag:
  - `WG_GATE_RESULT_SCHEMA_VALIDATION=off` — schema + banned-reviewer
  - `WG_GATE_RESULT_CONTENT_SANITIZATION=off` — sanitizer
  - `WG_GATE_RESULT_DISPATCH_CHECK=off` — orphan detection
  Each flag emits a stderr WARN on every invocation and auto-expires at
  `WG_GATE_RESULT_STRICT_AFTER`.
- **Debug cache bypass:** `WG_GATE_RESULT_CACHE=off` (does NOT bypass
  validation — only skips the memoization short-circuit).

## 7. Test coverage

- **Schema / caps / enums / banned-reviewer:**
  `tests/crew/test_gate_result_schema.py`
- **Sanitizer allow-list + injection patterns + i18n:**
  `tests/crew/test_content_sanitizer.py`
- **Orphan detection + soft/strict window + scoped bypass:**
  `tests/crew/test_dispatch_log.py`
- **Audit log hashing + non-fatal I/O:**
  `tests/crew/test_audit_log.py`
- **AC-11 perf SLO + cache identity:**
  `tests/crew/test_gate_result_perf.py`

## 8. Related issues

- **#479** — schema validator floor (increment 1)
- **#471** — content sanitization + orphan detection + audit + threat
  model + perf cache (increments 2 and 3)
- **#500** — HMAC-signed dispatch-log for authenticated gate-result
  verification (deferred)
