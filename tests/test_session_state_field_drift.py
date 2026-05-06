"""tests/test_session_state_field_drift.py — prevent silent SessionState drops.

Provenance: this test was added in v9.2.3 after a single cleanup pass found
SIX undeclared SessionState fields that hooks were `state.update(...)`-ing
or `getattr(state, ...)`-reading without the field being declared in the
dataclass. `SessionState.update(**kwargs)` silently drops unknown keys, so
every one of those was a write-only orphan or a constant-default read.

The drift bit us three times in this same session before being fixed:
  v9.2.0 — pull_phase / pull_count / unpulled_ok / corrections / pull_regress_at
  v9.2.2 — instruction_sync_fired (`[Sync]` reminder latch)
  v9.2.3 — active_chain_id, crew_project, last_reeval_ts, last_reeval_task_count,
           legacy_reeval_entries_detected, unready_plugins

Same anti-pattern class as v9.2.1's `run_semantic_review` ImportError —
silent contract drift that nobody noticed because the failure was indistinguishable
from intentional behavior.

This test scans the hooks directory and asserts every SessionState field
reference resolves to a declared field. Adding a `state.update(new_field=...)`
or `getattr(state, "new_field", ...)` call without declaring `new_field`
in `SessionState` will now fail CI rather than silently no-op in production.

T1: deterministic — pure file scanning, no I/O on SessionState
T3: isolated — reads files only, no fixtures
T4: single focus — the SessionState/hook field-name contract
T6: docstring cites v9.2.3 (this PR) and the historical regressions
"""
from __future__ import annotations

import re
from pathlib import Path

# False-positive guard. Some scripts use `state` to refer to a non-SessionState
# object (crew project state, dataclass instances of other shapes). Field
# names on those don't need to match SessionState. Listed explicitly so a
# reviewer adding a new field can see why it's exempt.
KNOWN_NON_SESSIONSTATE_FIELDS = {
    "name",       # ProjectState.name in scripts/crew/phase_manager.py + solo_mode.py
    "chain_id",   # ProjectState.chain_id in scripts/crew/phase_manager.py
    "topics",     # `state.topics` in prompt_submit's session-goal capture (different state object)
}

REPO_ROOT = Path(__file__).resolve().parent.parent
SESSION_FILE = REPO_ROOT / "scripts" / "_session.py"
HOOKS_DIR = REPO_ROOT / "hooks" / "scripts"


def _declared_fields() -> set[str]:
    """Parse SessionState dataclass field declarations."""
    text = SESSION_FILE.read_text(encoding="utf-8")
    fields = set()
    # Match dataclass field lines: "    name: type = value" or "    name: type"
    for m in re.finditer(r"^    ([a-z_][a-z_0-9]*)\s*:\s*[^#=]", text, re.MULTILINE):
        fields.add(m.group(1))
    return fields


def _used_fields_in_hooks() -> set[str]:
    """Walk hook scripts, return all field names referenced via
    `state.update(name=...)` or `getattr(state, "name", ...)`.

    Hooks are the canonical SessionState consumers — scripts/ has more noise
    from non-SessionState `state` references (ProjectState, dataclass
    parameters), so this scan is hooks-only by design.
    """
    used = set()
    for f in HOOKS_DIR.rglob("*.py"):
        text = f.read_text(encoding="utf-8")
        for m in re.finditer(r"state\.update\(([a-z_][a-z_0-9]*)\s*=", text):
            used.add(m.group(1))
        for m in re.finditer(r"""getattr\(state,\s*['"]([a-z_][a-z_0-9]*)['"]""", text):
            used.add(m.group(1))
    return used


def test_every_hook_state_reference_matches_a_declared_field():
    """v9.2.3 contract: every `state.update(X=...)` or `getattr(state, "X", ...)`
    in hook scripts must reference a declared SessionState field.

    Failure means the same anti-pattern that bit v9.2.0 / v9.2.2 / v9.2.3 has
    re-shipped. Add the field to SessionState in scripts/_session.py — or, if
    `state` here is a different state object, add the name to
    KNOWN_NON_SESSIONSTATE_FIELDS above with a comment explaining why.
    """
    declared = _declared_fields()
    used = _used_fields_in_hooks()
    drift = used - declared - KNOWN_NON_SESSIONSTATE_FIELDS
    assert not drift, (
        f"SessionState field drift detected — {len(drift)} field(s) referenced "
        f"in hook scripts but not declared in scripts/_session.py:\n"
        f"  {sorted(drift)}\n"
        f"Either declare the field in SessionState (preferred — silent-drop "
        f"is the bug) or add to KNOWN_NON_SESSIONSTATE_FIELDS with a comment."
    )


def test_session_state_declares_at_least_60_fields():
    """Sanity check — if someone deletes the SessionState dataclass, the
    drift test would pass vacuously. Anchor on the field count expected
    after v9.2.3 (62 fields)."""
    declared = _declared_fields()
    assert len(declared) >= 60, (
        f"SessionState only has {len(declared)} declared fields; "
        f"expected ~62 after v9.2.3. Did the dataclass shrink unexpectedly?"
    )
