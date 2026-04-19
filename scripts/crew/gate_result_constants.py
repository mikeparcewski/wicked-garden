"""Named byte-cap and count-cap constants for gate-result validation.

All caps are encoded here — never as magic literals at call sites. This
prevents R3 drift between the spec, error messages, and enforcement.
Every cap has a docstring explaining why it is sized the way it is.

Imported by:
  - gate_result_schema.py (size enforcement + error-message formatting)
  - content_sanitizer.py  (default-cap fallback for unknown string fields)
  - dispatch_log.py       (entry-size sanity check)
  - gate_ingest_audit.py  (snippet-excerpt cap)
  - tests/crew/*          (boundary-case parametrization)

Stdlib-only. No runtime side effects.
"""

from __future__ import annotations

# --- Per-field string byte caps (UTF-8 encoded length) ---

MAX_REASON_BYTES: int = 8192
"""Cap for gate-result.reason and per_reviewer_verdicts[i].reason.

Rationale: a reviewer's top-level reason is machine-consumed downstream
(surfaced by approve_phase, crew:status, smaht adapters). 8 KB is
enough for a dense two-page rationale; beyond that is almost always
a paste accident or adversarial payload (AC-2).
"""

MAX_CONDITION_BYTES: int = 2048
"""Cap for each conditions[i] string (or ConditionObj.description).

Rationale: conditions should be terse actionable imperatives. 2 KB
fits ~300 words — plenty for a well-phrased fix requirement; anything
longer belongs in a linked design doc, not inline (AC-2).
"""

MAX_REVIEWER_NAME_CHARS: int = 128
"""Cap for the reviewer string (and per_reviewer_verdicts[i].reviewer,
and rubric_breakdown implicit reviewer). Measured in CHARS not bytes —
mirrors _event_schema chain-segment limits.

Rationale: reviewer names are agent slugs (kebab-case, typically 20-60
chars); 128 absorbs the wicked-garden: namespace prefix and a long
specialist name with headroom (AC-4).
"""

MAX_SUMMARY_BYTES: int = 65536
"""Cap for the top-level summary field AND the total document size.

Rationale: 64 KB is the whole-document ceiling from design §1.4 —
rejects 'many small strings that sum large' DoS. The summary field
alone can approach the doc cap because it is the one field designed
to carry a full prose narrative (AC-2).
"""

# --- Per-field count caps ---

MAX_CONDITIONS_COUNT: int = 64
"""Max entries in conditions[]. Rationale: more than 64 conditions
means the gate needs re-architecting, not a bigger list."""

MAX_REVIEWER_VERDICTS_COUNT: int = 16
"""Max entries in per_reviewer_verdicts[]. Rationale: the largest
known rigor tier is 'full' with 4-6 reviewers; 16 gives 2.5x
headroom against future expansion."""

MAX_RUBRIC_DIMS_COUNT: int = 32
"""Max keys in rubric_breakdown. Rationale: spec_rubric.py factors
currently total 9; 32 gives room for phase-specific extensions."""

MAX_RUBRIC_NOTES_BYTES: int = 4096
"""Cap for each rubric_breakdown.<dim>.notes string. Rationale:
per-dimension notes are supporting evidence, not the primary reason
narrative. 4 KB matches the default-cap fallback for unknown nested
string fields (design §1.4)."""

MAX_PHASE_SLUG_CHARS: int = 64
"""Cap for the phase string. Mirrors chain-segment length limit
in _event_schema.CHAIN_ID_RE."""

MAX_GATE_SLUG_CHARS: int = 128
"""Cap for the gate string. Slightly more permissive than phase —
gates occasionally carry qualifier suffixes."""

# --- Default cap for unknown nested string fields ---

DEFAULT_STRING_CAP_BYTES: int = 4096
"""Applied to any string field encountered in the recursive walk
whose JSON path is not in FIELD_CAPS. Protects against a crafted
deep tree with an un-capped payload in a nested/unknown location
(design §1.4)."""

# --- Regex/pattern scan budget ---

MAX_PATTERN_SCAN_LATENCY_MS: int = 10
"""Soft-budget for the §2 injection-pattern scan (AC-2 p95 target).
Used as a test-harness assertion, not a runtime check (runtime
enforcement would itself cost overhead)."""

# --- Audit-log + forensic caps ---

AUDIT_SNIPPET_HASH_MAX_BYTES: int = 4096
"""Max bytes of the offending value hashed for the audit log.

The full offending value is NEVER stored in the audit log (would
make the log itself an injection vector). We hash the first 4 KB —
enough for forensic deduplication without re-ingestion risk (AC-8,
design §4.2)."""


__all__ = [
    "MAX_REASON_BYTES",
    "MAX_CONDITION_BYTES",
    "MAX_REVIEWER_NAME_CHARS",
    "MAX_SUMMARY_BYTES",
    "MAX_CONDITIONS_COUNT",
    "MAX_REVIEWER_VERDICTS_COUNT",
    "MAX_RUBRIC_DIMS_COUNT",
    "MAX_RUBRIC_NOTES_BYTES",
    "MAX_PHASE_SLUG_CHARS",
    "MAX_GATE_SLUG_CHARS",
    "DEFAULT_STRING_CAP_BYTES",
    "MAX_PATTERN_SCAN_LATENCY_MS",
    "AUDIT_SNIPPET_HASH_MAX_BYTES",
]
