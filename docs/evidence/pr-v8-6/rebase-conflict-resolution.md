# Rebase Conflict Resolution — v8/pr-6-single-autonomy-flag onto main

Performed: 2026-04-23

## Summary

PR-6 was branched from main before PR-5 (#617) merged. PR-5 added the full
production `scripts/crew/acceptance_criteria.py` (446 LOC). PR-6 contained a
244-LOC stub with the same filename. Rebasing on `origin/main` surfaced an
add/add conflict on that file.

## Conflicts encountered

| File | Conflict type | Resolution |
|------|---------------|------------|
| `scripts/crew/acceptance_criteria.py` | add/add — PR-5 production module vs PR-6 stub | **Took main's (PR-5) version verbatim via `git checkout origin/main --`** |

No other conflicts. `daemon/db.py` and `daemon/projector.py` were additive
on main (PR-5 added AC tables/handlers) and did not conflict because PR-6
did not modify those files on its branch.

## Verification

Post-rebase bit-identity check:

```
git diff origin/main:scripts/crew/acceptance_criteria.py HEAD:scripts/crew/acceptance_criteria.py
```

Output: empty (zero bytes). PR-5's module is preserved exactly.

## Stub disposition

PR-6's `acceptance_criteria.py` stub is DEAD and deleted entirely. It is not
merged, not cherry-picked, not referenced anywhere. PR-5's production module
is the sole implementation on the branch.
