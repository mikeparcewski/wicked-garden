# Scenario Disposition — scenarios/mem/
**PR**: cluster-a/mem-zombie-cleanup
**Date**: 2026-04-25
**Decision basis**: All 9 scenarios exercise dead `/wicked-garden:mem:*` slash commands removed in v8.0.0. Default disposition per memo Section 5.4: delete.

---

## scenarios/mem/automatic-learning.md
**Disposition**: DELETED
**Rationale**: Exercises `/wicked-garden:mem:store` and the automatic learning pipeline from the defunct local-JSON mem store. The capability (auto-storing facts) is now handled by `hooks/scripts/stop.py` + `scripts/_brain_ingest/session_fact_extractor.py` + wicked-brain. No live test scenario coverage needed here — `scenarios/crew/01-memory-storage.md` already tests the task_completed.py hook that fires the directives. No rewrite value: the test subject (mem:store command) doesn't exist.

## scenarios/mem/debug-pattern.md
**Disposition**: DELETED
**Rationale**: Tests the `/wicked-garden:mem:recall` + `/wicked-garden:mem:stats` commands in a debug workflow. Both commands are removed in v8.0.0. The underlying capability (recalling patterns) is now via `wicked-brain:search`. No rewrite warranted — a brain search scenario belongs in `scenarios/smaht/` or a new `scenarios/crew/` if needed; recreating a mem-domain scenario would be dead code.

## scenarios/mem/decision-recall.md
**Disposition**: DELETED
**Rationale**: Tests `/wicked-garden:mem:recall` for surfacing past decisions. Command removed in v8.0.0. The capability is now `wicked-brain:memory` (recall mode). The `scenarios/jam/04-integration-with-wicked-mem.md` scenario (rewritten in this PR) covers the jam + brain recall integration path. No additional scenario needed.

## scenarios/mem/end-to-end-workflow.md
**Disposition**: DELETED
**Rationale**: Full end-to-end scenario exercising store → recall → consolidate → stats cycle using dead slash commands. All five commands involved (`mem:store`, `mem:recall`, `mem:consolidate`, `mem:stats`) are removed in v8.0.0. Rewriting would require a full brain integration test, which is out of scope for this cleanup PR.

## scenarios/mem/memory-lifecycle.md
**Disposition**: DELETED
**Rationale**: Tests the 3-tier lifecycle (working → episodic → semantic) of the local-JSON mem store. This lifecycle is now entirely managed inside wicked-brain (tiering, decay, consolidation). The test subject no longer exists in this plugin.

## scenarios/mem/memory-promotion.md
**Disposition**: DELETED
**Rationale**: Tests `/wicked-garden:mem:promote` — a command that was part of the v6/v7 mem surface and was removed in v8.0.0. No live callers. The promotion concept maps to wicked-brain's consolidation pipeline.

## scenarios/mem/phase-aware-recall.md
**Disposition**: DELETED (Path A from Section 2C)
**Rationale**: Tests `scripts/mem/phase_scoring.py` which was deleted (Path A: zero live callers confirmed by pre-flight grep). With the script gone, this scenario has no test subject. Phase affinity ranking is now handled by wicked-brain's FTS5/BM25.

## scenarios/mem/returning-user.md
**Disposition**: DELETED
**Rationale**: Tests the "returning user" flow where `/wicked-garden:mem:recall` surfaces prior session context on re-opening a project. Command removed in v8.0.0. The smaht briefing system + wicked-brain cover this use case natively.

## scenarios/mem/tag-based-discovery.md
**Disposition**: DELETED
**Rationale**: Tests tag-based search via the dead `/wicked-garden:mem:recall` with tag filters. The capability is now `wicked-brain:search` or `wicked-brain:memory` (recall with filter_type). A new scenario would belong in a brain-specific test suite, not the wicked-garden mem domain.

---

## scenarios/jam/04-integration-with-wicked-mem.md
**Disposition**: REWRITTEN (not deleted)
**Rationale**: The intent of this scenario (jam can recall past decisions from persistent memory) is preserved by the new `wicked-brain:memory` wiring in `agents/jam/brainstorm-facilitator.md`. The scenario was rewritten in-place to use `wicked-brain:memory` skill calls instead of the dead `wicked-garden:mem:*` commands. The filename is retained (renamed from "wicked-mem" to "wicked-brain memory" in the description/title fields). Deleting it would leave no integration-level test coverage for the jam+brain recall path.

---

## scenarios/crew/cross-module-integration.md
**Disposition**: EDITED (step 7 removed, renumbered)
**Rationale**: Step 7 ("Enrich a memory record with phase info") depended on `scripts/mem/phase_scoring.py` which was deleted under Path A. The step was removed and subsequent steps renumbered. The rest of the scenario (project registry, knowledge graph, traceability, artifact state, impact analysis, domain adapter fan-out, verification protocol, consensus) remains valid and covers 7 scripts. Title and description updated to reflect 7 scripts (was 8).
