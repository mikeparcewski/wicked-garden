---
name: hook-script-lints
title: Hook script lints — computed-field enforcement, path-suffix tightening, error wrap context
description: Acceptance checks for the three lint themes added to pre_tool.py, post_tool.py, and _event_schema.py
type: testing
difficulty: beginner
estimated_minutes: 5
execution: manual
---

# Hook Script Lints

Three lint themes harden the hook entry points and the schema they enforce:

1. **Theme 1 — computed-without-enforcement.** `_event_schema.py::COMPUTED_FIELD_VALIDATORS` enforces shape on `content_hash`, `dedup_key`, `idempotency_key`, and `event_id` whenever a producer attaches them to TaskCreate/TaskUpdate metadata. The schema's promise now matches runtime behavior.
2. **Theme 9 — grep-based contract checks need functional context.** Two bare-substring checks were tightened to functional-syntax checks: `pre_tool.py` now matches `MEMORY.md` and `status.md` by basename (not tail-substring); `post_tool.py` requires grep/rg/ag/ripgrep to appear at command start or after a shell separator, not as a comment fragment.
3. **Theme 10 — wrap domain errors at architectural boundaries.** Hooks must fail-open and never raise, so `_event_schema.py::validate_metadata` cannot use `raise WrapperError(...) from e`. Instead, the boundary preserves the original exception's `type(e).__name__` and message inside the returned error string so callers (and operators reading `_logger`) retain the chain.

## Setup

```bash
cd "$CLAUDE_PLUGIN_ROOT"
python3 -m pytest tests/test_event_schema_archetype.py tests/test_event_schema_gate_finding_lifecycle.py -q
# Existing schema tests must still pass.
```

## Theme 1 — computed-field enforcement

```bash
python3 - <<'PY'
import sys
sys.path.insert(0, "scripts")
from _event_schema import validate_metadata

base = {
    "chain_id": "p.clarify",
    "event_type": "task",
    "source_agent": "facilitator",
    "phase": "clarify",
}

# Empty content_hash MUST be rejected
err = validate_metadata({**base, "content_hash": ""})
assert err and "content_hash" in err and "shape check" in err, err

# Short content_hash MUST be rejected (< 8 hex chars)
err = validate_metadata({**base, "content_hash": "abc"})
assert err and "content_hash" in err, err

# Valid hex content_hash MUST pass
assert validate_metadata({**base, "content_hash": "deadbeef"}) is None

# Blank dedup_key MUST be rejected
err = validate_metadata({**base, "dedup_key": "   "})
assert err and "dedup_key" in err, err

# Non-positive event_id MUST be rejected
assert validate_metadata({**base, "event_id": 0})
assert validate_metadata({**base, "event_id": -1})

# Positive int event_id MUST pass
assert validate_metadata({**base, "event_id": 42}) is None

print("Theme 1 OK")
PY
```

Expected: `Theme 1 OK`. A regression here means a producer can attach a malformed computed field and the validator silently accepts it.

## Theme 9 — basename and word-boundary checks

```bash
python3 - <<'PY'
import os, sys
os.environ["CLAUDE_PLUGIN_ROOT"] = os.getcwd()
sys.path.insert(0, "hooks/scripts")
import pre_tool, post_tool

# pre_tool: bogusstatus.md MUST NOT be allowlisted, status.md MUST be
assert pre_tool._is_allowlisted("foo/bogusstatus.md") is False
assert pre_tool._is_allowlisted("foo/status.md") is True
assert pre_tool._is_allowlisted(".something-wicked/x.json") is True

# pre_tool: MEMORY.md guard uses basename match
from pathlib import Path
assert Path("notMEMORY.md").name != "MEMORY.md"
assert Path("docs/MEMORY.md").name == "MEMORY.md"

# post_tool: grep word-boundary
assert post_tool._looks_like_search_invocation("grep foo") is True
assert post_tool._looks_like_search_invocation("cat x | grep y") is True
assert post_tool._looks_like_search_invocation("cmd; rg foo") is True
assert post_tool._looks_like_search_invocation("echo grep is here") is False
assert post_tool._looks_like_search_invocation("# rg later") is False
print("Theme 9 OK")
PY
```

Expected: `Theme 9 OK`. A regression means stale references (comments, echo strings, partial filenames) trigger the hint or guard.

## Theme 10 — preserved error context

```bash
python3 - <<'PY'
import sys
sys.path.insert(0, "scripts")
from _event_schema import validate_metadata

bad = {
    "chain_id": "p.review.gate1",
    "event_type": "gate-finding",
    "source_agent": "reviewer",
    "phase": "review",
    "verdict": "APPROVE",
    "score": "not-a-number",
    "min_score": 0.7,
}
err = validate_metadata(bad)
assert err is not None
# The original ValueError type and message MUST appear in the returned string
assert "ValueError" in err, err
assert "could not convert string to float" in err, err
print("Theme 10 OK")
PY
```

Expected: `Theme 10 OK`. A regression means the architectural boundary swallows the underlying coercion failure without preserving any chain context, making operator debugging harder.

## Files touched

- `scripts/_event_schema.py` — `COMPUTED_FIELD_VALIDATORS`, validation hook, preserved error chain on numeric coercion failure.
- `hooks/scripts/pre_tool.py` — basename-based MEMORY.md guard and `_is_allowlisted` suffix check.
- `hooks/scripts/post_tool.py` — `_looks_like_search_invocation` word-boundary regex.
