# Fix-up: Remove Dead cheatsheet_store Caller in context7_adapter

## Council Finding (PR #630)

Council voted 4-2 CONDITIONAL on PR #630 with one **unanimous blocker**: the PR
claim that "only callers of `cheatsheet_store.py` were the two deleted commands"
was incorrect. `scripts/smaht/adapters/context7_adapter.py::_lookup_cheatsheet()`
is a live third runtime caller. With the write path (`smaht:learn`) deleted in the
original PR, the adapter would silently degrade — the subprocess call still succeeds
(the script is on disk), but the store can never be populated.

## What Was Changed

Three surgical removals in `scripts/smaht/adapters/context7_adapter.py`:

1. `import subprocess` — dead import once `_lookup_cheatsheet` is gone (R1: no dead code)
2. `_CHEATSHEET_STORE` path constant (line 26 in pre-fixup file)
3. `_lookup_cheatsheet()` function body (lines 191-260 in pre-fixup file)
4. The single call-site at lines 292-297 in `query()` — the "hot tier: check local
   cheatsheet store first" block that called `asyncio.to_thread(_lookup_cheatsheet, lib_name)`

The `query()` function now falls through directly to the Context7 cache check, which
is the correct degraded behavior with no populated cheatsheet store.

Additionally, `tests/smaht/test_context7_cheatsheet.py` was deleted. That file
contained 15 tests exclusively for `_lookup_cheatsheet()` — keeping it would mean
testing dead code (R1) and would cause 14-15 new test failures.

## Why cheatsheet_store.py Was Not Deleted

`scripts/smaht/cheatsheet_store.py` and `scripts/smaht/test_cheatsheet_store.py`
are left on disk per explicit council scope guidance. Their removal is deferred to
the next cleanup batch. The council's blocker was only about severing the live
runtime caller, not about purging the store implementation itself.

## Reference

- Original PR: #630 (cluster-a/cut-smaht-learn-libs)
- Council vote: 4-2 CONDITIONAL, unanimous on the context7_adapter blocker
- Fix-up date: 2026-04-25
- Tests after fix-up: 11 pre-existing failures unchanged, 1666 passed, 0 new failures
