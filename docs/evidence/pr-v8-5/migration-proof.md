# Migration Proof — v8-PR-5 Structured ACs

## Scenario

A project has only a clarify markdown file — no `acceptance-criteria.json`.
The markdown contains: `- **AC-3**: User can log in`

## Step 1: First call to load_acs()

```python
from pathlib import Path
from scripts.crew.acceptance_criteria import load_acs, link_evidence

project_dir = Path("phases/my-project")
# phases/my-project/phases/clarify/spec.md contains:
#   - **AC-3**: User can log in

acs = load_acs(project_dir)
# → [AcceptanceCriterion(id="AC-3", statement="User can log in", satisfied_by=(), verification=None)]
```

`acceptance-criteria.json` is written alongside spec.md:
```json
{
  "version": "1",
  "acs": [
    {
      "id": "AC-3",
      "statement": "User can log in",
      "satisfied_by": [],
      "verification": null
    }
  ]
}
```

## Step 2: Second call (idempotent)

```python
acs2 = load_acs(project_dir)
# → reads from JSON directly (no re-parse)
# → same record: AcceptanceCriterion(id="AC-3", statement="User can log in", satisfied_by=(), verification=None)
```

No file is re-written. Idempotent.

## Step 3: Build artifact links evidence

```python
link_evidence(project_dir, "AC-3", "tests/test_login.py")
# AC-3.satisfied_by = ("tests/test_login.py",)
```

## Step 4: Coverage check

```python
from scripts.crew.verification_protocol import check_acceptance_criteria

result = check_acceptance_criteria("my-project", project_dir / "phases")
# Primary path: reads acceptance-criteria.json
# AC-3: satisfied_by = ("tests/test_login.py",) → LINKED
# Result: CheckResult(status="PASS", evidence="1/1 AC linked [structured]")
```

## Key invariants demonstrated

1. Prose statement `"User can log in"` is preserved in `statement` field — no content loss.
2. `satisfied_by` starts as `()` (empty tuple) — not pre-populated from text scanning.
3. Evidence is added explicitly via `link_evidence()` — a reference, not a heuristic.
4. Coverage check reads only `satisfied_by` — no substring scan on `statement`.
5. Re-run is idempotent — the JSON is not re-written after the first migration.

## Test verification

`TestMigration::test_clarify_md_creates_json` — passes  
`TestMigration::test_migrated_satisfied_by_is_empty` — passes  
`TestMigration::test_rerun_is_idempotent` — passes  
`TestMigration::test_prose_project_verification_still_works` — passes
