# PR-605 Sweep Summary — Cut-Surface Ref Migration

Generated: 2026-04-23
Branch: v9/pr-3-sharpen-merge
Issues: #601 #605

## Total refs migrated/removed/renamed

| Migration rule | Count | Action |
|---|---|---|
| `wicked-garden:mem:store` → `wicked-brain:memory` | 25 | Migrated |
| `wicked-garden:crew:migrate-gates` → removed | 1 | Removed (replaced with prose) |
| `wicked-garden:crew:cutover` | 0 | Already absent in scope files |
| `wicked-garden:crew:yolo` | 0 | Already absent in scope files |
| `wicked-garden:agentic:ask` | 0 | Already absent in scope files |
| `data:numbers` | 0 | Already absent in scope files |
| **Total** | **26** | |

Note: `scripts/ci/gate4-cutover-matrix.md` line 40 retains `/wicked-garden:mem:store` in
the v5 "OLD behavior" column of a historical comparison table — the v9 column already
reads `wicked-brain:memory`. Updating would distort the historical record; left unchanged
per task instructions.

## Per-file changes

### scripts/crew/dispatch_log.py
- Line 249: Removed `Run /wicked-garden:crew:migrate-gates to backfill.` → replaced with
  `See adopt-legacy skill for backfill guidance.`

### scripts/smaht/context_package.py
- Line 58: `PLUGIN_SKILL_MAP["mem"]` entry — `/wicked-garden:mem:store` → `wicked-brain:memory (store mode)`

### agents/crew/qe-orchestrator.md
- Line 105: `/wicked-garden:mem:store "QE {gate}..."` → `Skill(skill="wicked-brain:memory", args="store ...")`

### agents/delivery/risk-monitor.md
- Line 244: `/wicked-garden:mem:store "risk pattern:..."` → `Skill(skill="wicked-brain:memory", ...)`

### agents/delivery/stakeholder-reporter.md
- Line 194: `/wicked-garden:mem:store "Sprint {name}..."` → `Skill(skill="wicked-brain:memory", ...)`

### agents/jam/council.md
- Line 270: `/wicked-garden:mem:store "Council:..."` → `Skill(skill="wicked-brain:memory", ...)`

### agents/jam/brainstorm-facilitator.md
- Lines 255-260: `/wicked-garden:mem:store` with availability check → `Skill(skill="wicked-brain:memory", ...)` with graceful degradation note

### skills/mem/SKILL.md
- Decision: KEPT as wicked-brain:memory pointer (per audit.md: "The skill itself stays as a discovery handle")
- Quick Reference table: all 4 commands updated to wicked-brain:memory equivalents
- On-Demand Recall: updated to Skill() form

### skills/mem/refs/storing-decisions.md
- 3 bash code blocks (decision, procedural, episodic examples): all updated to Skill() form

### skills/mem/refs/memory-lifecycle.md
- Line 100: `/wicked-garden:mem:recall` + `/wicked-garden:mem:store` → wicked-brain:memory prose

### skills/multi-model/SKILL.md
- Line 119: `/wicked-garden:mem:store "Auth: JWT..."` → `Skill(skill="wicked-brain:memory", ...)`
- Section heading "via wicked-garden:mem" → "via wicked-brain:memory"

### skills/multi-model/refs/examples.md
- Lines 216, 223: 2 × `/wicked-garden:mem:store` → Skill() form
- Section heading updated

### skills/multi-model/refs/orchestration.md
- Line 153: `/wicked-garden:mem:store "Auth: JWT..."` → Skill() form
- Section heading updated

### skills/multi-model/refs/auditability.md
- Lines 143, 152, 158: 3 storage examples → Skill() form
- Line 227: SOX example → Skill() form

### skills/jam/SKILL.md
- Line 137: `# via /wicked-garden:mem:store` comment → `# via wicked-brain:memory (store mode)`

### skills/integration-discovery/refs/cli-detection.md
- Lines 246-250: bash Store Pattern block → Skill() form

### skills/product/product-management/refs/user-story-template.md
- Line 248: inline `/wicked-garden:mem:store` → Skill() form

### skills/product/requirements-analysis/refs/requirements-example-export-integration.md
- Line 77: bash block + section heading updated

### skills/product/strategy/SKILL.md
- Lines 136, 141: store + recall updated to Skill() form; section heading updated

### skills/workflow/refs/integration.md
- Lines 64, 70, 97: store/recall/conditional phrasing updated; section heading updated

## skills/mem decision

KEPT as wicked-brain:memory pointer. Audit verdict: "The `mem` domain in v9 collapses into
a single skill (`wicked-garden:mem`) that delegates to brain... The skill itself stays as a
discovery handle (mem ≠ wicked-brain in user mental model)."

The SKILL.md now documents `wicked-brain:memory` Skill() calls rather than the cut
`/wicked-garden:mem:store` command.

## Coupling discoveries

None. All 635 crew tests passed after edits. No reverts required.
