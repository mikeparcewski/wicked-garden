# Before/After: cluster-A followup #637 — crew:guide hygiene fixes

Issue: #640 — 6 bot-flagged hygiene items from PR #637 review.

---

## Fix 1: Hardcoded brain port (scripts/crew/guide.py)

**Before** (`_probe_brain_context`):
```python
port = int(os.environ.get("WICKED_BRAIN_PORT", "4243"))
```
Hardcoded fallback 4243 ignores project-level brain config. Breaks multi-project setups.

**After**:
```python
from _brain_port import resolve_port as _resolve_brain_port
# ...
port = _resolve_brain_port()
```
Uses the centralized `scripts/_brain_port.py` helper (env override → project config → root config → fallback 4242), consistent with every other brain consumer in the codebase.

---

## Fix 2: Dead constants — R1 violation (scripts/crew/guide.py)

**Before** (constants block):
```python
_PHASE_MANAGER = Path(__file__).resolve().parent / "phase_manager.py"
_STATUS_CMD = "/wicked-garden:crew:status"
_APPROVE_CMD = "/wicked-garden:crew:approve"
```
None of these were referenced anywhere in the module.

**After**: All three deleted. `_CREW_PY` and `_PYTHON_SH` (actually used) are retained.

---

## Fix 3: Wasted brain probe (scripts/crew/guide.py)

**Before** (`build_suggestions`):
```python
suggestions.extend(_probe_brain_context())  # called unconditionally
```
Called even when `len(suggestions) >= MAX_SUGGESTIONS`, wasting a localhost HTTP round-trip.

**After**:
```python
if len(suggestions) < MAX_SUGGESTIONS:
    suggestions.extend(_probe_brain_context())
```
Applied in both the `if project:` and `else:` branches. Brain probe docstring now matches implementation.

---

## Fix 4: Docstring/code mismatch (scripts/crew/guide.py)

**Before** (module docstring):
```
Signals inspected (priority order):
  1. Open CONDITIONAL gate ...
  2. Active project on stalled phase ...
  3. Uncommitted work in git ...
  4. No active crew project
```
4 signals listed; 5 implemented.

**After**:
```
Signals inspected (priority order):
  1. Open CONDITIONAL gate ...
  2. Active project on stalled phase ...
  3. Uncommitted work in git ...
  4. No active crew project
  5. Brain context nudge (wicked-brain reachable — surface relevant context)
```

---

## Fix 5: Test sys.path mutation (tests/crew/test_guide.py)

**Before**:
```python
sys.path.insert(0, str(_REPO_ROOT / "scripts"))
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "crew"))
```
Both inserts at index 0. The `scripts/crew/` insert at index 0 could shadow the `crew/` namespace package, breaking `from crew.archetype_detect import ...` in other tests.

**After**:
```python
_SCRIPTS_CREW = str(_REPO_ROOT / "scripts" / "crew")
if _SCRIPTS_CREW not in sys.path:
    sys.path.append(_SCRIPTS_CREW)
```
conftest.py already inserts `scripts/` at index 0 and appends `scripts/crew/` before any test module is imported. The test file now only guards the append (idempotent). No index 0 insertion.

---

## Fix 6: iterdir without directory filter (scripts/crew/guide.py)

**Before** (`_probe_open_conditions`):
```python
for phase_dir in sorted(base.iterdir()):
```
Iterates all entries including `.DS_Store`, stray files, symlinks.

**After**:
```python
for phase_dir in sorted(p for p in base.iterdir() if p.is_dir()):
```
Only directories are processed; non-directory entries are silently skipped.
