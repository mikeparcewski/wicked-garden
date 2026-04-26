---
name: context7-integration
title: "Context7 External Documentation Integration (RETIRED — smaht:learn cut in cluster-A)"
description: >
  RETIRED 2026-04-25 (cluster-A P0): smaht:learn was cut because it duplicated
  wicked-brain:ingest workflow. Context7 doc fetching still works via direct
  wicked-brain:ingest calls. This scenario file is kept as a tombstone only —
  do not run it.
type: integration
difficulty: intermediate
estimated_minutes: 5
status: retired
---

# Context7 External Documentation Integration (RETIRED)

> **RETIRED 2026-04-25** — `smaht:learn` and `smaht:libs` were cut in
> cluster-A P0 (decision record:
> `cluster-a-workflow-surface-review-v8-decision.md`).
> `smaht:learn` duplicated `wicked-brain:ingest`; `smaht:libs` was orphaned
> by the v8 daemon-first refactor.
>
> Context7 library doc fetching is still possible via `wicked-brain:ingest`.
> A replacement scenario in `scenarios/smaht/` should be authored separately
> if context7 integration coverage is required.

## Overview (historical)

v6 deleted the v5 push-model orchestrator in #428. Context7 (external library
documentation) is still available, but now it's pulled on demand by subagents
or skills that need it — there is no automatic per-prompt enrichment.

This scenario validated:

1. Library detection + fetching still worked from the (now cut) `smaht:learn` command
2. Failures degrade gracefully (missing MCP, timeouts) without stack traces
3. Brain can search the resulting cheatsheet after it's been stored

## Setup

No external setup required. If context7 MCP is not installed, Steps 2-3 should
fall through with "not available" messaging — that's the graceful-degradation
contract.

## Steps

### Step 1: Invoke the smaht:learn command

The v6 entry point for library cheatsheet fetching is
`/wicked-garden:smaht:learn <library>`. This replaces the v5 push-mode
"auto-fetch on prompt" behavior.

```
/wicked-garden:smaht:learn react
```

**Expected**:

- If context7 MCP is installed: a cheatsheet is written under
  a cheatsheet under the script-resolved libs path
  (`sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_path.py" wicked-smaht libs`
  → `react.md` inside that directory).
- If context7 MCP is NOT installed: a friendly "context7 MCP not available"
  message is emitted. No stack trace.

### Step 2: Verify the cheatsheet lives locally

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/resolve_path.py wicked-smaht libs
```

`ls` the returned path. If Step 1 succeeded, `react.md` (or similar) should be
present. If the MCP wasn't installed, the directory may be empty — that is
acceptable.

### Step 3: Brain can search the cheatsheet

Assuming the cheatsheet was stored, the wicked-brain ingest pipeline picks it
up on next ingest. Verify with:

```
Skill(skill="wicked-brain:search", args={"query": "react hook useEffect"})
```

**Expected**: brain returns at least one chunk whose `path` starts with the
wicked-smaht libs directory OR an empty result if either (a) the cheatsheet
wasn't written, or (b) the ingest pipeline hasn't run yet. Neither is a
failure — it's a "learn then ingest then search" sequence.

### Step 4: Graceful degradation

Run `smaht:learn` on a library name that context7 is unlikely to have:

```
/wicked-garden:smaht:learn this-library-probably-does-not-exist
```

**Expected**: no stack trace. Either an "unknown library" message or an empty
result. The session must continue normally.

## Success Criteria

- [ ] `smaht:learn` invokes without error on a known library (react)
- [ ] Cheatsheet lands under the wicked-smaht libs path when context7 is available
- [ ] Brain search can find stored cheatsheet content after ingest
- [ ] Degradation path (missing MCP / unknown library) does not raise stack traces

## v5 → v6 Notes

The v5 behavior — the orchestrator auto-detected library names in every prompt
and pre-fetched docs — was part of the push-model that was deleted with
`scripts/smaht/v2/orchestrator.py` in #428. v6 is explicit: the user (or a
subagent) invokes `smaht:learn` when docs are wanted, and the result is
persisted for brain search.
