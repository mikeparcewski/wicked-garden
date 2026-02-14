# Test Strategy: Ecosystem Improvements (Tier 1)

**Project**: ecosystem-improvements-brainstorm
**Date**: 2026-02-14
**Confidence**: HIGH

## Executive Summary

This strategy covers **3 Tier 1 fixes** to the wicked-garden plugin ecosystem. All fixes are configuration/guidance changes — no algorithmic changes requiring unit tests. Testing approach is **manual verification** with clear pass/fail criteria.

**Test Approach**: Manual verification + integration spot-checks
**Risk Level**: LOW (all fixes are non-breaking configuration corrections)
**Estimated Effort**: 15-20 minutes total

---

## Fix I1: smart_decisioning.py CLI Invocation

### What Changed
Removed stale `analyze --project-dir .` flags from 3 cached command files in wicked-crew v0.11.0. The script never supported `analyze` as a subcommand — correct invocation passes description as positional arg with `--json` flag.

### Test Scenarios

| ID | Category | Scenario | Priority |
|----|----------|----------|----------|
| I1-S1 | Error | Verify cached files no longer contain stale flags | P1 |
| I1-S2 | Happy | Verify smart_decisioning.py accepts positional arg + --json | P1 |
| I1-S3 | Happy | Verify returned JSON has expected structure | P1 |
| I1-S4 | Integration | Run /wicked-crew:start with a project description | P2 |

#### I1-S1: Cached Files Clean
**Objective**: Confirm `analyze --project-dir .` pattern is gone
**Steps**:
1. Check `~/.claude/plugins/cache/wicked-garden/wicked-crew/0.11.0/commands/*.md`
2. Run: `grep -n "analyze --project-dir" start.md execute.md just-finish.md`

**Pass Criteria**: No matches found (exit code 1 from grep)
**Fail Criteria**: Any matches found

**Current State**: FAIL — 3 matches still present (lines verified above)

---

#### I1-S2: CLI Accepts Correct Syntax
**Objective**: Verify script runs with positional arg + --json
**Steps**:
1. `cd /Users/michael.parcewski/Projects/wicked-garden/plugins/wicked-crew`
2. Run: `python3 scripts/smart_decisioning.py --json "Build a REST API with auth"`

**Pass Criteria**:
- Exit code 0
- JSON output on stdout
- No errors on stderr

**Fail Criteria**:
- Non-zero exit code
- Error messages about missing arguments
- No JSON output

---

#### I1-S3: JSON Structure Valid
**Objective**: Returned JSON matches expected schema
**Steps**:
1. Run: `python3 scripts/smart_decisioning.py --json "Build REST API with JWT auth" | jq .`
2. Verify keys present: `signals`, `signal_confidences`, `complexity_score`, `risk_dimensions`, `recommended_specialists`

**Pass Criteria**: All expected keys present with correct types:
- `signals`: array of strings
- `signal_confidences`: object with numeric values
- `complexity_score`: integer 0-7
- `risk_dimensions`: object with impact/reversibility/novelty (0-3 each)
- `recommended_specialists`: array of strings
- `specialist_routing`: object with tier/reason/signals per specialist

**Fail Criteria**: Missing keys, wrong types, or values out of range

---

#### I1-S4: Integration - /wicked-crew:start
**Objective**: End-to-end test via command invocation
**Steps**:
1. Start fresh Claude Code session
2. Run: `/wicked-crew:start "Build a login API with OAuth2"`
3. Observe output for signal analysis

**Pass Criteria**:
- Command completes without errors
- Signal analysis runs (security, architecture detected)
- Phase plan generated
- No "unknown flag" errors

**Fail Criteria**:
- Error: "unknown flag: --project-dir"
- Script crashes
- No phase plan generated

---

## Fix I2: wicked-smaht prompt_submit.py Hook

### What Changed
3 fixes in `/Users/michael.parcewski/Projects/wicked-garden/plugins/wicked-smaht/hooks/scripts/prompt_submit.py`:
1. **Slash command skip removed** (line 69-70): Commands now get context injection
2. **Empty briefing handling** (line 121-138): Logs error to stderr, injects partial context instead of silent drop
3. **Min prompt length lowered** (line 66): From 5 chars to 3 chars ("yes", "no" now pass)

### Test Scenarios

| ID | Category | Scenario | Priority |
|----|----------|----------|----------|
| I2-S1 | Happy | Slash commands should NOT be skipped | P1 |
| I2-S2 | Edge | Prompts of 3+ chars should pass through | P1 |
| I2-S3 | Edge | Prompts <3 chars should be skipped | P1 |
| I2-S4 | Error | Empty briefing produces partial context + stderr error | P1 |
| I2-S5 | Happy | Context warnings appear at turn 30 and 50 | P2 |

#### I2-S1: Slash Commands Get Context
**Objective**: Verify slash commands are no longer skipped by should_gather_context()
**Steps**:
1. Read `prompt_submit.py` lines 63-72
2. Verify no check for `prompt.startswith("/")`
3. Spot-check: inject test prompt `/wicked-mem:recall "test pattern"`

**Pass Criteria**:
- No slash command skip logic in should_gather_context()
- Comment on line 69-70 says "Don't skip slash commands"

**Fail Criteria**:
- Code still contains: `if prompt.startswith("/"):`

---

#### I2-S2: Short Prompts (3+ chars) Pass
**Objective**: Prompts like "yes", "no", "run" should NOT be skipped
**Steps**:
1. Check line 66: `if len(prompt.strip()) < 3:`
2. Mock test: `should_gather_context("yes")` should return True
3. Mock test: `should_gather_context("ok!")` should return True

**Pass Criteria**:
- Threshold is `< 3` (not `< 5`)
- 3-char prompts return True from should_gather_context()

**Fail Criteria**:
- Threshold still `< 5`
- "yes"/"no" get skipped

---

#### I2-S3: Very Short Prompts (<3 chars) Skipped
**Objective**: Single-char confirmations like "y", "k" should skip context gathering
**Steps**:
1. Mock test: `should_gather_context("y")` should return False
2. Mock test: `should_gather_context("k")` should return False
3. Mock test: `should_gather_context("..")` should return False

**Pass Criteria**:
- Prompts with <3 chars return False from should_gather_context()

**Fail Criteria**:
- Single chars trigger context gathering

---

#### I2-S4: Empty Briefing Produces Partial Context
**Objective**: Failed context assembly doesn't silently drop — logs error, injects what's available
**Steps**:
1. Read lines 121-138 (error handling block)
2. Verify: `if not result["success"] or not result.get("briefing"):`
3. Verify: Error logged to stderr: `print(f"smaht: context assembly failed: {result['error']}", file=sys.stderr)`
4. Verify: Partial context injection with fallback_parts

**Pass Criteria**:
- Empty briefing doesn't cause silent drop
- Error logged to stderr (not injected into prompt)
- Fallback context includes: context_warning (if present), sources queried (if any)
- Returns `{"continue": True, "message": "..."}` or `{"continue": True}` (never blocks)

**Fail Criteria**:
- Empty briefing causes prompt to proceed with no context AND no log
- Error message injected into user-visible prompt
- Hook returns `{"continue": False}` on error

---

#### I2-S5: Context Warnings at Turn Thresholds
**Objective**: Turn 30 and 50 should trigger context budget warnings
**Steps**:
1. Read lines 28-29: `CONTEXT_WARNING_TURN = 30`, `CONTEXT_CRITICAL_TURN = 50`
2. Read lines 38-60: increment_and_check_turns() logic
3. Read line 150: Warning appended to briefing

**Pass Criteria**:
- Turn 30-49: Warning about long session, suggest /wicked-mem:store
- Turn 50+: Critical warning about context window filling
- Warning text appended to briefing (line 150)

**Fail Criteria**:
- No warnings at any turn count
- Warnings at wrong thresholds

---

## Fix I3: CLAUDE.md Guidance Additions

### What Changed
Added two new sections to `.claude/CLAUDE.md`:
1. **"Delegation-First Execution"** (lines 237-263): When to delegate to specialists vs execute inline, specialist routing table
2. **"Code Search"** (lines 255-262): Prefer wicked-search over native Grep/Glob when installed

### Test Scenarios

| ID | Category | Scenario | Priority |
|----|----------|----------|----------|
| I3-S1 | Happy | CLAUDE.md contains "Delegation-First Execution" section | P1 |
| I3-S2 | Happy | CLAUDE.md contains "Code Search" section | P1 |
| I3-S3 | Happy | Specialist routing table covers all 8 specialists | P1 |
| I3-S4 | Happy | Fallback conditions documented | P2 |
| I3-S5 | Integration | Claude prefers /wicked-search when available | P2 |

#### I3-S1: Delegation-First Section Exists
**Objective**: Verify section is present with correct content
**Steps**:
1. Read `/Users/michael.parcewski/Projects/wicked-garden/.claude/CLAUDE.md` lines 237-254
2. Search for header: `## Delegation-First Execution`
3. Verify subsections: "Always Delegate", "Execute Inline"

**Pass Criteria**:
- Header found at line 237
- Subsection "Always Delegate (via Task tool)" present
- Subsection "Execute Inline" present
- Core principle documented: "Delegate complex work to specialist subagents"

**Fail Criteria**:
- Section missing
- Subsections incomplete

---

#### I3-S2: Code Search Section Exists
**Objective**: Verify wicked-search preference guidance
**Steps**:
1. Read CLAUDE.md lines 255-262
2. Search for subsection: `### Code Search`
3. Verify guidance: "Always prefer wicked-search over native tools"

**Pass Criteria**:
- Subsection found
- Guidance covers: symbol search, docs, blast-radius, lineage
- Fallback conditions documented (when wicked-search not installed)

**Fail Criteria**:
- Section missing
- No fallback guidance

---

#### I3-S3: Specialist Routing Table
**Objective**: All 8 specialists have routing guidance
**Steps**:
1. Read CLAUDE.md lines 242-243
2. Extract specialist mappings from "Domain-specific work" bullets
3. Verify coverage: engineering, platform, qe, product, delivery, data, jam, agentic

**Pass Criteria**: All 8 specialists mentioned with domain mappings:
- wicked-engineering: architecture, multi-step engineering
- wicked-platform: security review, infrastructure, compliance
- wicked-qe: test strategy, quality gates, risk assessment
- wicked-product: requirements, UX, product decisions
- wicked-delivery: project management, coordination
- wicked-data: data analysis, analytics, pipelines
- wicked-jam: brainstorming, ambiguity resolution
- wicked-agentic: agent architecture, agentic systems

**Fail Criteria**: Missing specialists or unclear domain boundaries

---

#### I3-S4: Fallback Conditions Documented
**Objective**: Inline execution conditions are clear
**Steps**:
1. Read CLAUDE.md lines 249-252 ("Execute Inline" subsection)
2. Verify conditions: single-step ops, continuations, no matching specialist

**Pass Criteria**:
- Explicit list of when NOT to delegate
- "Check Task tool agent list first" guidance present

**Fail Criteria**:
- Fallback conditions vague or missing

---

#### I3-S5: Integration - Search Preference
**Objective**: Claude actually prefers wicked-search when available
**Steps**:
1. Ask Claude Code: "Find all function definitions in wicked-crew"
2. Observe if it uses `/wicked-search:code` or `Grep` tool

**Pass Criteria** (if wicked-search installed):
- Uses `/wicked-search:code` first
- If search fails, falls back to Grep with explanation

**Pass Criteria** (if wicked-search NOT installed):
- Uses Grep directly
- No errors about missing tools

**Fail Criteria**:
- Uses Grep when wicked-search available
- No explanation for tool choice

---

## Test Data Requirements

### Fix I1
- **Sample project descriptions** (for smart_decisioning.py):
  - "Build a REST API with OAuth2 authentication" (expect: security, architecture signals)
  - "Add caching to product catalog query" (expect: performance signal)
  - "Migrate user table to new schema" (expect: reversibility, data signals)
  - "POC: evaluate GraphQL vs REST" (expect: ambiguity, novelty signals)

### Fix I2
- **Sample prompts** (for prompt_submit.py):
  - Slash command: `/wicked-mem:recall "test patterns"`
  - Short prompts: "yes", "no", "run", "ok!"
  - Very short: "y", "k", ".."
  - Mock empty briefing response: `{"success": False, "error": "timeout", "briefing": ""}`

### Fix I3
- **Sample questions** (for CLAUDE.md guidance):
  - "Review the security of auth.py" (expect: delegate to wicked-platform)
  - "Read config.json" (expect: inline Read tool)
  - "Find all API endpoints" (expect: wicked-search preferred)

---

## E2E Scenario Coverage

Checking wicked-scenarios for E2E test coverage of affected areas:

```bash
python3 /Users/michael.parcewski/Projects/wicked-garden/plugins/wicked-qe/scripts/discover_scenarios.py --check-tools
```

### Expected Coverage Gaps

| Risk Area | E2E Scenarios | Status |
|-----------|---------------|--------|
| CLI argument parsing | — | Gap: No wicked-scenarios coverage for smart_decisioning.py CLI |
| Hook lifecycle (UserPromptSubmit) | — | Gap: No hook integration scenarios |
| CLAUDE.md instruction adherence | — | Gap: No synthetic prompt tests for delegation rules |

**Recommendation**: All 3 fixes are **configuration/guidance changes** with no E2E scenario coverage. This is acceptable — manual verification is appropriate for instruction changes.

---

## Priority Ordering

### P1 Scenarios (Must Pass Before Release)
1. **I1-S1**: Cached files clean (blocking bug if not fixed)
2. **I1-S2**: CLI accepts correct syntax (core functionality)
3. **I1-S3**: JSON structure valid (contract correctness)
4. **I2-S1**: Slash commands get context (behavior change intentional)
5. **I2-S2**: Short prompts pass (UX improvement)
6. **I2-S4**: Empty briefing handled gracefully (error handling)
7. **I3-S1**: Delegation section exists (core guidance)
8. **I3-S2**: Code Search section exists (core guidance)
9. **I3-S3**: Specialist routing table complete (discovery contract)

### P2 Scenarios (Should Pass, Not Blocking)
10. **I1-S4**: Integration via /wicked-crew:start (end-to-end check)
11. **I2-S3**: Very short prompts skipped (optimization, not critical)
12. **I2-S5**: Context warnings at turns 30/50 (nice-to-have UX)
13. **I3-S4**: Fallback conditions documented (completeness)
14. **I3-S5**: Claude prefers wicked-search (behavioral integration)

---

## Test Execution Plan

### Phase 1: Quick Wins (5 min)
1. Run I1-S1 (grep cached files)
2. Run I1-S2 (CLI syntax)
3. Read prompt_submit.py for I2-S1, I2-S2 visual inspection
4. Read CLAUDE.md for I3-S1, I3-S2, I3-S3 visual inspection

### Phase 2: Functional Validation (7 min)
5. Run I1-S3 (JSON structure with jq)
6. Create mock test for I2-S4 (empty briefing error handling)
7. Run I1-S4 (integration test via /wicked-crew:start)

### Phase 3: Edge Cases (5 min)
8. Mock test I2-S3 (very short prompts)
9. Read I3-S4 (fallback docs)
10. Optional: I3-S5 (search preference integration)

---

## Success Criteria

**READY FOR RELEASE** if:
- ✅ All P1 scenarios pass
- ✅ I1-S1 PASSES (cached files fixed — currently FAILING)
- ✅ No regressions in existing functionality

**NEEDS WORK** if:
- ❌ I1-S1 still has stale flags in cached files
- ❌ smart_decisioning.py CLI broken
- ❌ prompt_submit.py errors instead of graceful degradation
- ❌ CLAUDE.md missing documented sections

---

## Risk Assessment

| Fix | Risk Level | Justification |
|-----|------------|---------------|
| I1 | MEDIUM | Cached files still have stale flags — commands will fail until cache refreshed |
| I2 | LOW | Hook changes are additive (more context, better errors) — no breaking changes |
| I3 | LOW | Guidance additions don't change code behavior — only affect Claude's decisions |

**Overall Risk**: MEDIUM (due to I1 cache state)

**Mitigation**:
- For I1: Users need to reinstall wicked-crew v0.11.0+ OR manually edit cached files
- For I2: No mitigation needed (backward compatible)
- For I3: No mitigation needed (additive guidance)

---

## Recommendations

1. **Fix I1-S1 FIRST**: The cached files still contain stale flags. Either:
   - Bump wicked-crew to v0.11.1 and force cache refresh
   - Manually edit cached files (not recommended — fragile)
   - Document workaround in release notes

2. **Automate I1-S3**: Add JSON schema validation to wicked-crew tests:
   ```python
   # tests/test_smart_decisioning.py
   def test_analyze_input_schema():
       result = analyze_input("Build REST API with auth")
       assert "signals" in result
       assert isinstance(result["complexity_score"], int)
       assert 0 <= result["complexity_score"] <= 7
   ```

3. **Add E2E Scenarios** (future work):
   - `wicked-crew/scenarios/signal-detection.md` (test smart_decisioning end-to-end)
   - `wicked-smaht/scenarios/context-injection.md` (test hook lifecycle)

4. **Document Behavioral Changes**:
   - CHANGELOG entry for I2-S1 (slash commands now get context)
   - CHANGELOG entry for I2-S2 (short prompts now pass)

---

## Appendix: File Locations

- **I1 Source**: `/Users/michael.parcewski/Projects/wicked-garden/plugins/wicked-crew/scripts/smart_decisioning.py`
- **I1 Cached**: `~/.claude/plugins/cache/wicked-garden/wicked-crew/0.11.0/commands/*.md`
- **I2 Source**: `/Users/michael.parcewski/Projects/wicked-garden/plugins/wicked-smaht/hooks/scripts/prompt_submit.py`
- **I3 Source**: `/Users/michael.parcewski/Projects/wicked-garden/.claude/CLAUDE.md`
- **E2E Discovery**: `/Users/michael.parcewski/Projects/wicked-garden/plugins/wicked-qe/scripts/discover_scenarios.py`
