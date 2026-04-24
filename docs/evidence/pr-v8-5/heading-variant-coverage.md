# Heading Variant Coverage — TestNumberedUnderHeadingIsolated

**Test class**: `TestNumberedUnderHeadingIsolated`
**File**: `tests/crew/test_acceptance_criteria.py`
**PR**: v8/pr-5-structured-acs
**Council condition**: Isolated unit test for `_RE_NUMBERED` + `_RE_AC_SECTION` (PR #617)

---

## Case 1: _RE_AC_SECTION heading variant coverage

| Heading variant | Test method | _RE_AC_SECTION matches | Parser activates | Result |
|---|---|---|---|---|
| `## Acceptance Criteria` | `test_heading_variant_standard` | YES | YES | **PASS** |
| `## ACs` | `test_heading_variant_acs_short` | NO | NO | **FAIL** |
| `## Acceptance Criteria (Draft)` | `test_heading_variant_draft_suffix` | YES | YES | **PASS** |
| `### Acceptance Criteria` | `test_heading_variant_h3` | YES | YES | **PASS** |
| `# Acceptance Criteria` | `test_heading_variant_h1` | YES | YES | **PASS** |

**4 of 5 variants pass. `## ACs` is a confirmed bug.**

### Bug 1: `## ACs` not recognised

**Regex**: `r"#{1,4}\s+(?:acceptance[\s_-]*criteri|ac\b)"`

The pattern `ac\b` requires a word boundary after "ac". In "ACs", the character after "ac" is "s"
(case-insensitive), so `\bac\b` does not match "acs". The trailing `\b` consumes the boundary
before "s", so "ACs" (case-folded to "acs") does not satisfy `ac\b` — the word boundary is
between "s" and end-of-word, not between "ac" and "s".

**Impact**: Any clarify document using `## ACs` as the section heading will silently produce zero
ACs during migration. Migration is one-shot (load_acs writes JSON and early-returns). Parse miss
= permanent silent data loss.

**Fix (not applied — production code is UNTOUCHED per instructions)**:
Change `ac\b` to `acs?\b` in `_RE_AC_SECTION`, or use `(?:ac|acs)\b`.

---

## Case 2: Numbered items under AC section ARE captured

| Input | Expected ACs | Got ACs | Result |
|---|---|---|---|
| 3 numbered items under `## Acceptance Criteria` | 3 (AC-1, AC-2, AC-3) | 3 | **PASS** |
| Statements preserved verbatim | yes | yes | **PASS** |

---

## Case 3: Numbered items OUTSIDE the AC section are NOT captured

| Scenario | Expected | Got | Result |
|---|---|---|---|
| Items under `## Other Heading` pre-AC section | NOT captured | CAPTURED (AC-1, AC-2) | **FAIL** |
| Items under `## Acceptance Criteria` | captured | NOT captured (pre-section consumed IDs) | **FAIL** |
| Items under `## Later Heading` post-AC section | NOT captured | (deduplicated out) | incidental |

**This is a confirmed bug.**

### Bug 2: Numbered items in ALL sections captured, not just the AC section

**Root cause**: `parse_acs_from_markdown` performs a document-wide `_RE_NUMBERED.finditer(text)`
whenever `_RE_AC_SECTION` matches anywhere in the document. It does NOT restrict the scan to
lines within the AC section. Every ordered list in the document is captured.

**Code location**: `scripts/crew/acceptance_criteria.py` lines 194–199:
```python
if _RE_AC_SECTION.search(text):
    for m in _RE_NUMBERED.finditer(text):   # <-- whole-document scan
        raw_id = m.group("id")
        canonical = f"AC-{raw_id}"
        _add(canonical, m.group("desc"))
```

**Impact**: Numbered lists in any section (Introduction, Steps, References, etc.) are treated as
ACs if the document also contains an AC section heading. The wrong items are migrated to
`acceptance-criteria.json` — permanently, since migration is one-shot.

**Fix (not applied — production code is UNTOUCHED per instructions)**:
Parse the document into sections first, extract lines only within the AC section, then apply
`_RE_NUMBERED` to that slice.

---

## Summary

| Case | Tests | Pass | Fail |
|---|---|---|---|
| Case 1: heading variants | 5 | 4 | 1 (`## ACs`) |
| Case 2: items under AC section captured | 1 | 1 | 0 |
| Case 3: items outside AC section excluded | 1 | 0 | 1 |
| **Total** | **7** | **5** | **2** |

**Both failures are real bugs in `scripts/crew/acceptance_criteria.py`. Production code was not
modified. Findings are escalated to council.**
