# Mem Zombie — Postmortem & Remediation Plan

**Status**: POSTMORTEM (cuts already shipped) + REMEDIATION BRIEF (cleanup scoped)
**Cluster**: A (P0)
**Authored**: 2026-04-25
**Author role**: safety-reviewer
**Linked**: PR #603 (v8.0.0 surface cuts), `docs/v9/audit.md`, `docs/cluster-a/cluster-a-workflow-surface-review-v8-decision.md` (brainstorm decision record)
**Deliverable scope**: Memo only. Implementer dispatch is a separate task after this memo lands and is reviewed.

---

## Section 1 — Postmortem on the v8.0.0 mem cuts

### 1.1 What shipped

In v8.0.0 (released 2026-04-24, PR #603 / commit `fd9517d`, "feat(v9-PR-2): execute 85 surface cuts"), the entire `commands/mem/` directory was removed. That deleted **8 user-facing slash commands** with no deprecation window:

- `/wicked-garden:mem:store`
- `/wicked-garden:mem:recall`
- `/wicked-garden:mem:forget`
- `/wicked-garden:mem:stats`
- `/wicked-garden:mem:consolidate`
- `/wicked-garden:mem:retag`
- `/wicked-garden:mem:review`
- `/wicked-garden:mem:help`

The v9 surface audit (`docs/v9/audit.md` lines 116-127) verdict on every one of these was `CUT`, with the rationale "thin wrapper over `wicked-brain:*`". The audit verdict was correct on the merits — these were genuinely thin wrappers and `wicked-brain` is the canonical replacement. The execution of the cut, however, was incomplete: the commands were removed without a migration window and without sweeping the surfaces that depended on them.

### 1.2 What broke for users

The plugin is **marketplace-distributed**. A v8.0.0 install update is synchronized across every consumer that has the plugin enabled. Anyone with:

- Shell history containing `/wicked-garden:mem:store|recall|...`
- Aliases or shell completions wired to those commands
- Personal scripts, runbooks, or playbooks that invoke those commands
- Documentation (their own or wicked-garden's `README.md` / `docs/getting-started.md` / `docs/advanced.md`) that referenced those commands

…got `command-not-found` style failures with no in-product hint that the replacement is `wicked-brain:memory`. The README (line 143) still advertises `mem:store`, `mem:recall`, `mem:consolidate` as live, which compounds the confusion: a new user reading the README on the v8.0.0 install will type a command that doesn't exist.

### 1.3 Severity scoring

Using the post-calibration questionnaire scorer (the same one field-tested in cluster-A — see `docs/cluster-a/` brainstorm record):

- **reversibility**: `r3` / `r4` (high_risk band) — marketplace-distributed = synchronized break across all installs; rolling forward is a release; rolling back is a release; users in between are stuck on `command-not-found`.
- **blast_radius**: `B3` (broad) — any user of any mem slash command is affected, plus every doc/runbook/script reference.
- **user_facing_impact**: `U2`/`U3` — silent surface removal with no in-product migration path is a meaningful UX regression even though the underlying capability (memory) is preserved via `wicked-brain:memory`.

This matches the "high_risk" reversibility band the scorer was calibrated to flag for exactly this class of change.

### 1.4 Why this happened

The v9 surface refactor was scoped as **ruthless cuts** — discovery-first, kill the wrappers, route users to canonical providers. That scoping was correct.

The brainstorm decision record (`docs/cluster-a/cluster-a-workflow-surface-review-v8-decision.md`) flagged "mem zombie state" as a known consequence of the cuts, but the cut PR (#603) shipped **before** the cleanup work was scheduled or scoped. As a result:

1. The slash commands were deleted (the visible surface).
2. The supporting infrastructure was left in place (the invisible zombie state).
3. The cross-references were not swept.
4. The CHANGELOG entry for v8.0.0 did not flag the breaking change in user-facing terms — it appears under "Features" as `feat(v9-PR-2): execute 85 surface cuts (#601)`, with no "Breaking" sub-section calling out the consumer-visible impact.

The migration was half-finished and shipped.

### 1.5 What we'd do differently

For future **marketplace-distributed surface cuts** affecting documented commands:

- **Deprecation-grace pattern**: one release with the old command emitting a deprecation warning + a structured `[deprecated -> use wicked-brain:memory ...]` message before the next release removes it. Aliasing-shim cost is low when the replacement is a sibling skill that already exists.
- **Mandatory CHANGELOG `Breaking` sub-section** for any removed user-facing slash command, with the migration path inline.
- **Standing merge gate** should add a "consumer breakage" check that triggers when a `commands/**/*.md` file is deleted in a PR that also bumps a marketplace version number.
- **Cross-ref sweep is part of the cut**, not a follow-up. A surface cut PR that ships before the cross-refs are clean leaves zombie state by definition.

These are candidate process changes to be tracked separately; this memo's scope is the cleanup of the existing zombie, not the process fix.

### 1.6 What's still broken (residual zombie state)

Four classes of residual artifact, enumerated below and addressed in Section 2:

- **A.** `skills/mem/` — half-redirected SKILL.md and refs that still document the dead slash commands.
- **B.** `agents/mem/` — three subagents (`memory-recaller`, `memory-learner`, `memory-archivist`) wired to a dead local-JSON store path (`${SM_LOCAL_ROOT}/wicked-garden:mem/`), still **live-dispatched** by two jam files.
- **C.** `scripts/mem/` — one **load-bearing** file (`session_fact_extractor.py`, imported by `hooks/scripts/stop.py:145`) plus one likely-orphan (`phase_scoring.py`, referenced by 2 scenario fixtures).
- **D.** Cross-reference drift — **290 occurrences across 117 files** of `wicked-garden:mem` strings, plus **139 occurrences** of dead slash-command syntax (`mem:store|recall|forget|...`) across docs, agents, skills, and scripts.

---

## Section 2 — Remediation plan

### 2A. Cut `skills/mem/` (per Q2)

The user has overridden the v9 audit doc's "stays as discovery handle" choice. Cut the entire skills/mem tree.

**Files to delete:**

- `skills/mem/SKILL.md`
- `skills/mem/refs/effective-recall.md`
- `skills/mem/refs/memory-lifecycle.md`
- `skills/mem/refs/storing-decisions.md`
- `skills/mem/refs/` (the directory itself if empty after the above)
- `skills/mem/` (the directory itself)

**Verification step:** `grep -rn "skills/mem" --include="*.md" --include="*.py" --include="*.json" .` to find any remaining references to the skill path. Most likely candidates are doc cross-refs (handled in 2D) and scenarios (handled below).

**Scenario impact:** `scenarios/mem/*.md` reference the dead slash commands; these scenarios are already invalid. Implementer should propose deletion of `scenarios/mem/` as part of 2D, or escalate if any scenario covers a still-live capability that needs preserving.

**CHANGELOG entry** (under upcoming release `Removed`):

> Skill `wicked-garden:mem` (SKILL.md + refs/) — superseded by `wicked-brain:memory`. The mem slash commands were removed in v8.0.0; this cleans up the orphaned discovery surface. Migration: use `wicked-brain:memory` (store/recall/forget modes) directly.

---

### 2B. Rewrite jam callers + delete mem agents (per Q3)

The three mem agents are wired to `${SM_LOCAL_ROOT}/wicked-garden:mem/` — the v5/v6 local-JSON store path. That store layout is no longer how memory is persisted; brain handles it now. The agents are zombies in the strict sense: they still execute but write to a path nothing else reads.

**Verified call sites** (full sweep of `wicked-garden:mem:memory-*` across the repo, excluding evidence/council/cluster-a docs and `.aider`):

```
agents/jam/brainstorm-facilitator.md:40
agents/jam/brainstorm-facilitator.md:53
commands/jam/revisit.md:17
agents/mem/memory-recaller.md:3            # frontmatter — the agent definition itself
agents/mem/memory-learner.md:3             # frontmatter — the agent definition itself
agents/mem/memory-archivist.md:3           # frontmatter — the agent definition itself
```

**No other live callers.** Spot-check confirmed via `grep -rn "wicked-garden:mem:memory-" --include="*.md" .`.

**Step 1 — rewrite `agents/jam/brainstorm-facilitator.md`:**

Lines 39-43 (Step 1a): replace
```
Task(subagent_type="wicked-garden:mem:memory-recaller",
     prompt="Search for past decisions related to: {topic}. Return decisions, outcomes, and any gotchas.")
```
with a `wicked-brain:memory` skill call in recall mode. Recommended replacement (implementer to verify the exact skill invocation grammar — see how `wicked-brain:memory` is called elsewhere in the repo, e.g. `grep -rn "wicked-brain:memory" agents/ commands/` for canonical patterns):

```
Use wicked-brain:memory in recall mode:
  query: "past decisions related to: {topic}"
  filter: type=decision
  return: decisions, outcomes, gotchas
```

Lines 52-55 (Step 1c): same replacement pattern, query `"brainstorm outcomes tagged jam,outcome"`, filter `type=decision`.

**Step 2 — rewrite `commands/jam/revisit.md`:**

Lines 16-19: same pattern, query `"decisions tagged 'jam,decision' related to: {topic}"`, filter `type=decision`. Behavior preserved: "if no matching decision found, inform user and suggest `/wicked-garden:jam:brainstorm`."

**Step 3 — delete the three agents:**

- `agents/mem/memory-recaller.md`
- `agents/mem/memory-learner.md`
- `agents/mem/memory-archivist.md`
- `agents/mem/` (directory itself if empty after the above)

**Verification:** after edits, re-run
```
grep -rn "wicked-garden:mem:memory-" --include="*.md" --include="*.py" --include="*.json" .
```
Expected: zero hits outside `docs/cluster-a/` (this memo) and `docs/evidence/`.

**Scenario impact:** `scenarios/jam/04-integration-with-wicked-mem.md` likely still references this integration path. Implementer must rewrite or delete depending on whether the scenario's intent (jam can recall past decisions) is preserved by the new `wicked-brain:memory` wiring — if so, rewrite to test the new path.

**CHANGELOG entry** (under upcoming release `Removed` and `Changed`):

> Removed: agents `wicked-garden:mem:memory-recaller`, `wicked-garden:mem:memory-learner`, `wicked-garden:mem:memory-archivist` — wired to a defunct local-JSON store path; never re-pointed to wicked-brain after the v6→v7 brain migration.
>
> Changed: `agents/jam/brainstorm-facilitator.md` and `commands/jam/revisit.md` now query `wicked-brain:memory` directly for past decision recall.

---

### 2C. Relocate `session_fact_extractor.py` (per Q4)

**Load-bearing dependency confirmed.** `hooks/scripts/stop.py` lines 142-145:

```python
# scripts/ is already on sys.path; add the mem/ directory for the
# sibling import of session_fact_extractor.
sys.path.insert(0, str(_PLUGIN_ROOT / "scripts" / "mem"))

from session_fact_extractor import extract_session_facts
```

This is the post-Stop hook pathway that emits `wicked.fact.extracted` events into the bus, which back the brain auto-memorize behavior. If this import breaks, **brain auto-memorize stops working silently** — no exception bubbles up because `stop.py` is async and best-effort by design. This is the same failure shape as the `context7_adapter._lookup_cheatsheet` finding from PR #630.

**Target directory selection.** Existing `scripts/` siblings:

```
scripts/_adapters/         scripts/_brain_port.py    scripts/_bus.py
scripts/_capability_*      scripts/_domain_store.py  scripts/_event_*
scripts/_integration_*     scripts/_logger.py        scripts/_paths.py
scripts/_python.sh         scripts/_run.py           scripts/_session.py
scripts/_wicked_testing_*
```

**Convention observation:** underscore-prefixed names are framework/internal infrastructure; non-underscore names are domain directories (`crew`, `jam`, `data`, `qe`, etc.). `session_fact_extractor.py` is internal infrastructure that bridges Stop hook → brain, not a user-facing domain. It belongs under an underscore-prefixed location.

**Recommended target:** `scripts/_brain_ingest/session_fact_extractor.py`

Rationale:
- Mirrors `_brain_port.py` naming (the brain-facing internal module already in `scripts/`).
- A directory (not a flat sibling file) leaves room for related extractors in the future without re-relocating.
- `_brain_ingest` clearly signals "feeds the brain" which is exactly what this module does.

Implementer should make the final call between `scripts/_brain_ingest/`, `scripts/_brain/`, and `scripts/hooks/`. The tie-breaker is convention: check whether any peer brain-bridge code already lives at one of these paths and prefer co-location. If a peer exists, use that path.

**Move + import update:**

```bash
mkdir -p scripts/_brain_ingest
git mv scripts/mem/session_fact_extractor.py scripts/_brain_ingest/session_fact_extractor.py
# scripts/_brain_ingest/__init__.py — create empty for clean import
```

Update `hooks/scripts/stop.py:142-145` to:

```python
# scripts/ is on sys.path via the hook's bootstrap; add _brain_ingest
# for the sibling import of session_fact_extractor.
sys.path.insert(0, str(_PLUGIN_ROOT / "scripts" / "_brain_ingest"))

from session_fact_extractor import extract_session_facts
```

**`scripts/mem/phase_scoring.py` — NOT a clean orphan.** Trust-but-verify spot-check found it referenced by:

- `scenarios/mem/phase-aware-recall.md` (lines 35, 43, 51, 59, 80, 94, 108, 122) — full test scenario for the script's behavior.
- `scenarios/crew/cross-module-integration.md` (lines 151, 230) — integration test that imports `enrich_memory_with_phase` from it.
- `docs/crew-workflow.md:306` and `docs/cross-phase-intelligence.md` (lines 322, 342, 345, 348, 351) — documentation references.

Implementer must decide between two paths:

- **Path A (cut both):** delete `scripts/mem/phase_scoring.py` AND `scenarios/mem/phase-aware-recall.md` AND the relevant section of `scenarios/crew/cross-module-integration.md`. Update `docs/crew-workflow.md:306` and `docs/cross-phase-intelligence.md` to remove the references. Justification: phase-scoring was a v6-era feature that operated on the local-JSON mem store; brain handles memory ranking via FTS5 + BM25 now, so phase-scoring is genuinely dead.
- **Path B (relocate + keep):** if implementer finds evidence that phase-scoring is still wired into a live recall path (verify by grepping for callers of `enrich_memory_with_phase` and `score_memories_for_phase` in `scripts/` and `hooks/`), relocate alongside `session_fact_extractor.py` under `scripts/_brain_ingest/` and update the scenarios + docs to match.

**Recommended path: A**, contingent on the verification grep returning no live callers. The 2 scenarios reference it; the scenarios should be retired alongside it because they exist to test a layer that brain now subsumes.

**`scripts/mem/` directory cleanup:** after moves, remove `scripts/mem/__pycache__/` and `scripts/mem/` itself.

**Verification:**

```bash
# import path works
cd /Users/michael.parcewski/Projects/wicked-garden && \
  python3 -c "import sys; sys.path.insert(0, 'scripts/_brain_ingest'); from session_fact_extractor import extract_session_facts; print('OK')"

# stop.py runs
sh scripts/_python.sh hooks/scripts/stop.py < /dev/null  # should not crash on import
```

**CHANGELOG entry:**

> Moved: `scripts/mem/session_fact_extractor.py` → `scripts/_brain_ingest/session_fact_extractor.py`. Internal infrastructure relocation; no public API change. Caller `hooks/scripts/stop.py` updated.
>
> Removed: `scripts/mem/phase_scoring.py` and associated scenarios (`scenarios/mem/phase-aware-recall.md`, the phase-scoring section of `scenarios/crew/cross-module-integration.md`) — phase affinity was a v6-era memory ranking step now handled by wicked-brain's FTS5/BM25.

---

### 2D. Cross-reference sweep — 290 occurrences / 117 files

The sweep splits into three categories by handling pattern.

#### 2D.1 — User-visible docs (TOP PRIORITY, surgical edits)

These are the files a new or returning user actually reads. They actively mislead.

| File | Issue | Fix |
|---|---|---|
| `README.md:143` | Advertises `mem:store`, `mem:recall`, `mem:consolidate` as live commands in the domain table. | Either remove the `mem` row entirely (memory is now via the `wicked-brain` plugin, not a wicked-garden domain) **or** rewrite the row to point users at `wicked-brain:memory` with a note "requires wicked-brain plugin." |
| `docs/getting-started.md` | Documents dead `/wicked-garden:mem:store|recall` syntax in the onboarding flow. | Replace with `wicked-brain:memory` invocations. Verify the example actually works end-to-end after rewrite. |
| `docs/advanced.md` | Same. | Same. |
| `docs/crew-workflow.md:306` | Mentions `mem/phase_scoring.py` as part of the crew memory recall path. | Remove the phase_scoring sentence; rewrite the paragraph to describe brain-backed recall. |
| `docs/cross-phase-intelligence.md:322,342,345,348,351` | Documents `phase_scoring.py` CLI. | Remove the entire section if 2C-Path-A is taken. If 2C-Path-B, update the paths. |
| `AGENTS.md` | Contains dead `wicked-garden:mem:*` slash command syntax. | Sweep + replace with `wicked-brain:memory` invocations. |

**Acceptance:** zero hits for `wicked-garden:mem:store|recall|forget|stats|consolidate|retag|review|help|tasks|promote|archive` syntax in `README.md`, `docs/getting-started.md`, `docs/advanced.md`, `AGENTS.md` after the sweep.

#### 2D.2 — Skill/agent integration descriptions (50+ files, pattern replacement)

Many skills and agents have prose like:

> "Skills you may use: ... `/wicked-garden:mem:store` to persist a decision ..."

The mechanical fix: replace every `/wicked-garden:mem:store|recall|forget|consolidate|retag|review|stats|help` syntax with the equivalent `wicked-brain:memory` skill invocation pattern.

**Files identified by spot-grep (not exhaustive):**

- `.claude/CLAUDE.md`
- `.claude/commands/wg-test.md`
- `agents/delivery/delivery-manager.md`
- `agents/delivery/experiment-designer.md`
- `agents/delivery/progress-tracker.md`
- `agents/delivery/risk-monitor.md`
- `agents/delivery/stakeholder-reporter.md`
- `skills/crew/issue-reporting/SKILL.md`
- `skills/delivery/onboarding-guide/SKILL.md`
- `skills/integration-discovery/refs/cli-detection.md`
- `skills/jam/SKILL.md`
- `scripts/ci/gate4-cutover-matrix.md`

Implementer runs:

```bash
grep -rln "wicked-garden:mem:\(store\|recall\|forget\|stats\|consolidate\|retag\|review\|help\|tasks\|promote\|archive\)" \
  --include="*.md" --include="*.py" --include="*.json" .
```

…to enumerate the full file list, then surgically edits each. Bulk find-and-replace is **not safe** because the replacement grammar (`wicked-brain:memory` skill invocation) differs by context — sometimes it's a bullet in a "skills you may use" list, sometimes it's an inline code reference, sometimes it's a Task dispatch.

**Recommended pattern** (validate against canonical wicked-brain usage in the repo first):

| Old | New |
|---|---|
| `/wicked-garden:mem:store decision "..."` | `wicked-brain:memory` (store mode, type=decision) |
| `/wicked-garden:mem:recall <query>` | `wicked-brain:memory` (recall mode) or `wicked-brain:search` |
| `/wicked-garden:mem:forget <id>` | `wicked-brain:forget` |
| `/wicked-garden:mem:stats` | `wicked-brain:status` |
| `/wicked-garden:mem:consolidate` | `wicked-brain:agent` (consolidate) |
| `/wicked-garden:mem:retag` | `wicked-brain:retag` |
| `/wicked-garden:mem:review` | `wicked-brain:review` |

Implementer should consult `docs/v9/audit.md` lines 116-127 — the v9 audit already mapped each cut command to its brain replacement.

#### 2D.3 — Scripts (VERIFICATION REQUIRED before edit)

Six scripts reference `wicked-garden:mem` as a domain identifier. **These may be live wiring, not just doc lint.** Implementer must inspect each, classify (keep / update / delete), and act accordingly. **Do not bulk-rename.**

| File | Reference | Recommended classification |
|---|---|---|
| `scripts/_paths.py:114` | Migration comment for `wicked-garden:mem/memories/` directories from older versions. | **Keep** — it's a historical migration note in a comment. Optionally update wording to add "v8.0.0 removed the surface; storage layout retained for read-only migration support." |
| `scripts/_domain_store.py:15,64,166` | `DomainStore("wicked-garden:mem")` example + integration-discovery routing entry for the mem domain. | **Verify carefully.** If anything still creates a `DomainStore("wicked-garden:mem")` instance for **writes**, that's live wiring to a now-orphaned local store. If it's only **read-side** (for migration / one-time export), document that and keep. If neither, remove the routing entry. |
| `scripts/_integration_resolver.py:40,300` | Integration discovery for `wicked-garden:mem`; emits `"source: wicked-garden:mem"` line. | **Update.** The source name should change to `wicked-brain:memory` (or whatever the canonical brain source-name pattern is — check sibling adapter source-name strings first). |
| `scripts/reset.py:46` | `"mem": "wicked-garden:mem"` in a reset routing table. | **Verify, likely remove.** If `/wicked-garden:reset` exposes a `mem` target, removing this entry breaks the reset CLI for that target. Implementer must check `scripts/reset.py` end-to-end and either route `mem` resets to brain or remove the option. |
| `scripts/smaht/context_package.py:57,132,210` | Injects `/wicked-garden:mem:recall` into a directive string at line 57; queries `wicked-garden:mem` via domain adapter at line 132. | **Update.** Line 57 directive is user-visible advice that points users at a dead command — rewrite to point at `wicked-brain:memory`. Line 132's domain-adapter query should be re-pointed to brain. Line 210 is a docstring — update wording. |
| `scripts/jam/consensus.py:387` | Format consensus result for storage in `wicked-garden:mem` (docstring). | **Update.** Likely just a docstring referring to the old storage path; update to "wicked-brain:memory". Verify the function actually still writes somewhere — if it writes to the dead local-JSON store, the function itself is broken and needs to be re-pointed at brain. |

#### 2D.4 — Hook source-name emissions

| File:Line | Issue | Fix |
|---|---|---|
| `hooks/scripts/prompt_submit.py:94` | Emits `"source: wicked-garden:mem"` in chunk metadata. | Change to `"source: wicked-brain:memory"` (or sibling-canonical pattern — verify by `grep -rn "source: wicked-brain" hooks/ scripts/`). |
| `hooks/scripts/pre_compact.py:81` | Same. | Same. |

These are persisted into brain chunk metadata. Existing chunks in brain will retain the old `wicked-garden:mem` source string — this is fine; no data migration needed, just stop writing the wrong thing going forward.

---

## Section 3 — CHANGELOG amendment

### 3.1 Retroactive entry under v8.0.0

Add a new sub-section under `## [8.0.0] - 2026-04-24` documenting the breaking change in user-visible terms. This corrects the original entry's "Features" framing for consumer-impact transparency.

Recommended insertion (above the existing `### Features` block):

```markdown
### Breaking — already shipped in v8.0.0

- Removed all 8 `commands/mem/` slash commands without a deprecation window:
  `mem:store`, `mem:recall`, `mem:forget`, `mem:stats`, `mem:consolidate`,
  `mem:retag`, `mem:review`, `mem:help`. Replacement: use `wicked-brain:memory`
  (store/recall/forget modes), `wicked-brain:status`, `wicked-brain:retag`,
  `wicked-brain:review`, `wicked-brain:agent` (consolidate) directly. See
  `docs/cluster-a/mem-zombie-postmortem-and-remediation.md` for migration
  details and the postmortem on this rollout.
```

### 3.2 Forward entry under `## [Unreleased]`

Add to the existing `### Removed` block:

```markdown
### Removed
- (existing entries above…)
- Skill `wicked-garden:mem` (SKILL.md + refs/) — orphaned discovery surface
  for the v8.0.0 mem command cuts. Use `wicked-brain:memory` directly.
- Agents `wicked-garden:mem:memory-recaller`, `wicked-garden:mem:memory-learner`,
  `wicked-garden:mem:memory-archivist` — wired to a defunct local-JSON store
  path; never re-pointed to wicked-brain after the v6→v7 brain migration.
- Script `scripts/mem/phase_scoring.py` and its scenarios — phase affinity
  ranking now handled by wicked-brain's FTS5/BM25.

### Changed
- `agents/jam/brainstorm-facilitator.md` and `commands/jam/revisit.md` now
  query `wicked-brain:memory` directly for past decision recall (was:
  `wicked-garden:mem:memory-recaller` agent dispatch).
- `scripts/mem/session_fact_extractor.py` moved to `scripts/_brain_ingest/`
  (internal infrastructure relocation; no public API change).
- Hook chunk metadata now emits `source: wicked-brain:memory` (was:
  `source: wicked-garden:mem`).

### Documentation
- README, getting-started, advanced, crew-workflow, cross-phase-intelligence,
  AGENTS.md, and ~50 skill/agent integration descriptions swept of dead
  `/wicked-garden:mem:*` slash command syntax.
```

---

## Section 4 — Implementer brief

For the next dispatch (recommended `wicked-garden:engineering:senior-engineer`).

### Files to delete (full paths)

```
skills/mem/SKILL.md
skills/mem/refs/effective-recall.md
skills/mem/refs/memory-lifecycle.md
skills/mem/refs/storing-decisions.md
skills/mem/refs/                   # if empty
skills/mem/                        # the directory
agents/mem/memory-recaller.md
agents/mem/memory-learner.md
agents/mem/memory-archivist.md
agents/mem/                        # if empty
scripts/mem/phase_scoring.py       # contingent on Path A verification (2C)
scripts/mem/__pycache__/
scripts/mem/                       # after move + delete above
scenarios/mem/phase-aware-recall.md           # contingent on Path A
scenarios/mem/                                # if all retired (verify)
```

Scenarios under `scenarios/mem/` other than `phase-aware-recall.md` (the audit lists `automatic-learning.md`, `debug-pattern.md`, `decision-recall.md`, `end-to-end-workflow.md`, `memory-lifecycle.md`, `memory-promotion.md`, `returning-user.md`, `tag-based-discovery.md`) all exercise the dead slash commands. Implementer should propose retirement (or rewrite to test `wicked-brain:memory`) — do not silently keep failing scenarios.

### Files to edit (full paths + critical edits)

**`agents/jam/brainstorm-facilitator.md`** — replace the two `Task(subagent_type="wicked-garden:mem:memory-recaller", ...)` blocks at lines 39-43 and 52-55 with `wicked-brain:memory` recall calls. Verify the exact skill invocation grammar against canonical usage elsewhere in the repo.

**`commands/jam/revisit.md`** — replace the `Task(subagent_type="wicked-garden:mem:memory-recaller", ...)` block at lines 16-19 with the same pattern. Preserve the "if no matching decision found, suggest `/wicked-garden:jam:brainstorm`" fallback.

**`hooks/scripts/stop.py`** — line 142-145, update `sys.path.insert` and import to point at the new location of `session_fact_extractor.py`:

```python
# BEFORE
sys.path.insert(0, str(_PLUGIN_ROOT / "scripts" / "mem"))
from session_fact_extractor import extract_session_facts

# AFTER
sys.path.insert(0, str(_PLUGIN_ROOT / "scripts" / "_brain_ingest"))
from session_fact_extractor import extract_session_facts
```

**`hooks/scripts/prompt_submit.py:94`** and **`hooks/scripts/pre_compact.py:81`** — change emitted source from `"wicked-garden:mem"` to `"wicked-brain:memory"`.

**`README.md:143`** — remove or rewrite the `mem` domain row (memory is no longer a wicked-garden domain).

**`docs/getting-started.md`**, **`docs/advanced.md`**, **`docs/crew-workflow.md`**, **`docs/cross-phase-intelligence.md`**, **`AGENTS.md`** — sweep dead slash command syntax per 2D.1.

**~50 skill/agent integration descriptions** — sweep per 2D.2 using the mapping table in that section.

**`CHANGELOG.md`** — apply both amendments per Section 3.

### Files to verify before cutting (the 6 live-wiring candidates)

1. `scripts/_paths.py:114` — historical migration comment, likely keep.
2. `scripts/_domain_store.py:15,64,166` — example + routing table; check if `DomainStore("wicked-garden:mem")` is instantiated anywhere for **writes**.
3. `scripts/_integration_resolver.py:40,300` — update the emitted source-name string.
4. `scripts/reset.py:46` — check whether `/wicked-garden:reset` exposes a `mem` target; route to brain or remove the option.
5. `scripts/smaht/context_package.py:57,132,210` — line 57 is user-visible directive text (rewrite); line 132 is a domain-adapter query (re-point to brain); line 210 is a docstring (update).
6. `scripts/jam/consensus.py:387` — docstring; verify the function's actual write target and re-point if it writes to the dead store.

For each: classify as **keep** / **update** / **delete**, document the decision in the PR description, and only act on the classification.

### Acceptance criteria

- [ ] No broken imports: `python3 -c "from session_fact_extractor import extract_session_facts"` succeeds with the new sys.path.
- [ ] `hooks/scripts/stop.py` runs end-to-end without import error (smoke test: dispatch a Stop event with empty stdin).
- [ ] No broken Task dispatches: `grep -rn "wicked-garden:mem:memory-" --include="*.md" --include="*.py" --include="*.json" .` returns zero hits outside `docs/cluster-a/` and `docs/evidence/`.
- [ ] All 837+ existing tests still pass (`/wg-test --all` or whatever the canonical full-suite invocation is).
- [ ] Full grep clean for `wicked-garden:mem:store|recall|forget|stats|consolidate|retag|review|help|tasks|promote|archive` in user-visible docs (`README.md`, `docs/getting-started.md`, `docs/advanced.md`, `AGENTS.md`).
- [ ] Brain auto-memorize smoke test: end a session, confirm a `wicked.fact.extracted` event reaches the bus, confirm brain receives the chunk.
- [ ] `/wicked-garden:jam:revisit` end-to-end smoke test with a known past decision in brain — confirm the decision is recalled.

### Out of scope

- Do **not** touch the `wicked-brain` plugin (it's a separate distribution).
- Do **not** change the brain memory schema.
- Do **not** attempt data migration of any existing local-JSON `wicked-garden:mem` store entries — those were migrated in v6→v7; the dead local path is a no-write zombie at this point. A separate one-time migration script may be needed if any user reports data loss, but that is out of scope for this cleanup.
- Do **not** add deprecation shims for the already-removed slash commands; that ship sailed in v8.0.0.

### Evidence directory

Capture all evidence under `docs/evidence/cluster-a-mem-zombie-cleanup/`:

- `grep-pre-sweep.txt` — full grep output before edits (baseline).
- `grep-post-sweep.txt` — full grep output after edits (zero hits expected per acceptance).
- `pytest-results.txt` — full test-suite output.
- `import-smoke-test.txt` — output of the import smoke test.
- `stop-hook-smoke-test.txt` — output of the stop.py end-to-end smoke test.
- `verification-classification.md` — for each of the 6 live-wiring candidates, the implementer's keep/update/delete decision and rationale.

### Process gate

Standing merge gate applies:
- PR opened against `main`
- `/wicked-garden:jam:council` review on the PR
- HITL judge sign-off
- Standing merge gate verdict APPROVE before merge

---

## Section 5 — Risks + mitigations

### 5.1 Load-bearing risk: `session_fact_extractor.py` relocation breaks brain auto-memorize silently

**Risk class**: same as the `context7_adapter._lookup_cheatsheet` finding from PR #630 — silent breakage of an async best-effort hook pathway. `hooks/scripts/stop.py` swallows import errors by design (the hook is async and best-effort), so a broken import means brain auto-memorize stops working with **no user-visible error**. Users only notice when they look for a decision in brain weeks later and find it isn't there.

**Mitigation:**
- **Pre-merge**: explicit smoke test as part of acceptance criteria — dispatch a real Stop event in a test session, confirm via bus query that `wicked.fact.extracted` events appear with the expected payload.
- **Pre-merge**: import smoke test (`python3 -c "..."`) in CI or in the PR's evidence bundle.
- **Post-merge**: a watchdog assertion — consider adding a startup check in `hooks/scripts/stop.py` that logs to stderr on import failure (instead of silently passing). This is a small additive change, low risk, high value for catching this exact regression class. (Out of scope for this remediation but flagged as a follow-up candidate.)

### 5.2 Sweep miss risk: residual `wicked-garden:mem:*` slash command syntax in user-visible surface

**Risk**: implementer misses a doc/skill/agent file in the cross-ref sweep, leaves dead syntax in front of users.

**Mitigation:**
- Acceptance criterion includes a full-repo grep that must return zero hits in user-visible docs.
- Evidence bundle includes pre/post grep diffs.
- Council review on the PR will catch high-visibility misses (README, getting-started).

### 5.3 Verification miss risk on the 6 live-wiring candidates

**Risk**: implementer misclassifies one of the 6 scripts (e.g., treats `scripts/jam/consensus.py:387` as docstring-only when the function actually writes to the dead store), shipping a silent broken write path.

**Mitigation:**
- Acceptance criterion: each of the 6 candidates gets a written classification (keep/update/delete) with rationale, captured in `docs/evidence/cluster-a-mem-zombie-cleanup/verification-classification.md`.
- Council review specifically asked to validate the 6 classifications.
- Spot-check by safety-reviewer in the council round.

### 5.4 Scenario debt risk

**Risk**: the `scenarios/mem/` directory contains 8+ scenarios that exercise dead slash commands. If left in place, they pollute the test suite with permanent failures or skipped-with-noise.

**Mitigation:**
- Implementer must propose a disposition for each scenario in `scenarios/mem/` (delete, rewrite, or keep-as-historical-record-with-skip-marker). Default recommendation: delete.
- Same for `scenarios/jam/04-integration-with-wicked-mem.md`.
- Same for the relevant section of `scenarios/crew/cross-module-integration.md`.

### 5.5 Process-debt risk: this happens again

**Risk**: the next ruthless-cuts surface refactor ships zombie state again because the cross-ref sweep is treated as a follow-up rather than part of the cut.

**Mitigation** (out of scope for this remediation, flagged as candidate process change):
- Add a "consumer breakage check" to the standing merge gate that triggers on any deletion under `commands/**/*.md` or `agents/**/*.md` paired with a marketplace version bump.
- Document the deprecation-grace pattern in the release skill (`releasing`).
- Track as a separate follow-up item — do not bundle into this remediation PR.

---

## Appendix — verified spot-checks

For trust-but-verify, the following audit claims were re-confirmed during memo authoring:

| Claim | Verification | Result |
|---|---|---|
| `commands/mem/` is gone | `ls commands/mem/` | Confirmed: directory does not exist. |
| v8.0.0 cut PR is `fd9517d` | `git log --oneline | grep fd9517d` | Confirmed: `feat(v9-PR-2): execute 85 surface cuts (#601) (#603)`. |
| Jam files dispatch the 3 mem agents | `grep -n "wicked-garden:mem:memory-" agents/jam/brainstorm-facilitator.md commands/jam/revisit.md` | Confirmed: 3 hits at the cited lines. |
| No other live callers of the 3 mem agents | full-repo grep excluding evidence/cluster-a/.aider | Confirmed: only the 3 jam dispatches + the 3 agent self-frontmatter. |
| `session_fact_extractor.py` is imported by `stop.py:145` | `grep -n "session_fact_extractor" hooks/scripts/stop.py` | Confirmed: import at line 145, sys.path manipulation at line 142. |
| `phase_scoring.py` has scenario dependencies | `grep -rn "phase_scoring" .` | Confirmed: `scenarios/mem/phase-aware-recall.md` (8 references) + `scenarios/crew/cross-module-integration.md` (2 references) — **NOT** a clean orphan, contradicting the audit's "orphan" framing. Adjusted the remediation plan (Section 2C, Path A vs Path B). |
| 290 occurrences across 117 files of `wicked-garden:mem` strings | `grep -rn "wicked-garden:mem" ... | wc -l` and unique-files count | Confirmed: 290 / 117 (audit had said 268 / 109; numbers grew slightly, likely because the `.md` extension list expanded). |
| 139 occurrences of dead slash command syntax | `grep -rn "wicked-garden:mem:store|recall|..." | wc -l` | Confirmed. |
| README.md:143 advertises mem as live | direct read | Confirmed: `| **mem** | 3-tier persistent memory ... | mem:store, mem:recall, mem:consolidate |` |

**One audit revision:** `phase_scoring.py` was framed as "orphan" in the inlined audit but has live scenario dependencies. Section 2C was adjusted to expose Path A (cut both script + scenarios) vs Path B (relocate + keep both) and recommend Path A pending implementer verification of caller-side wiring.
