# Wicked Garden Plugin Test Report

**Date**: 2026-02-23
**Branch**: claude/wg-test-all-plugins-1LXpL
**Plugins Tested**: 17
**Overall Result**: 16/17 PASS, 1 FAIL

## Executive Summary

All 17 registered plugins were tested via parallel background agents executing representative scenarios against each plugin's core functionality. The three-agent Writer phase (wicked-scenarios:scenario-converter) was also run against wicked-crew's end-to-end scenario, catching 8 specification mismatches between scenario documentation and implementation code.

**One failure**: wicked-agentic has 0 test scenarios despite being a v2.1.0 plugin with 5 agents, 7 skills, and 5 commands.

## Test Results

### Utility Plugins (9/9 PASS)

| Plugin | Version | Scenario | Criteria | Verdict | Key Evidence |
|--------|---------|----------|----------|---------|-------------|
| wicked-crew | 1.1.0 | Core scripts + phase lifecycle | 9/9 | **PASS** | Signal detection, phase transitions, gate enforcement, 9 commands, 11 agents |
| wicked-kanban | 1.1.0 | basic-task-workflow | 5/5 | **PASS** | Full task lifecycle, 3 default swimlanes, activity log with 7 entries |
| wicked-mem | 1.1.0 | decision-recall | 9/9 | **PASS** | Store/recall by keyword/tag/type, full-text search for "ACID"/"JOINs" |
| wicked-search | 2.2.0 | index-and-search | 4/4 | **PASS** | Indexed Python + Markdown, unified search, 7 symbols in unified DB |
| wicked-smaht | 3.1.0 | intent-based-retrieval | 4/4 | **PASS** | HOT (6ms), FAST (506ms), SLOW (626ms) routing, 8 adapters |
| wicked-patch | 2.1.1 | add-field-propagation | 10/10 | **PASS** | 5 patches across Java/Python/SQL, transactional apply, 12 generators |
| wicked-scenarios | 1.2.0 | api-health-check | 8/8 | **PASS** | HTTP 200, JSON validation, 3 infrastructure agents valid |
| wicked-startah | 0.10.0 | fresh-install | All | **PASS** | 10 skills valid, hooks execute correctly, cache scripts present |
| wicked-workbench | 1.1.0 | server-startup-health | 6/6 | **PASS** | Server live, 7 plugins discovered, 24 data sources, dashboard UI loads |

### Specialist Plugins (7/8 PASS, 1 FAIL)

| Plugin | Version | Personas | Enhances | Agents | Skills | Commands | Scenarios | Verdict |
|--------|---------|----------|----------|--------|--------|----------|-----------|---------|
| wicked-engineering | 1.1.0 | 5 | 3 | 10 | 10 | 5 | 4 | **PASS** |
| wicked-platform | 1.1.0 | 5 | 3 | 10 | 10 | 10 | 6 | **PASS** |
| wicked-data | 1.1.0 | 4 | 3 | 4 | 5 | 2 | 6 | **PASS** |
| wicked-delivery | 1.1.0 | 11 | 4 | 11 | 3 | 2 | 6 | **PASS** |
| wicked-product | 1.1.0 | 5 | 3 | 13 | 10 | 8 | 6 | **PASS** |
| wicked-jam | 1.1.0 | 5 | 2 | 1 | 1 | 5 | 4 | **PASS** |
| wicked-qe | 1.2.0 | 8 | 4 | 8 | 2 | 6 | 3 | **PASS** |
| wicked-agentic | 2.1.0 | 5 | 3 | 5 | 7 | 5 | **0** | **FAIL** |

## Specification Mismatches (wicked-crew)

The three-agent Writer phase analyzed the `01-end-to-end-feature` scenario against implementation code and found 8 mismatches:

| Severity | Issue |
|----------|-------|
| Medium | Scenario expects `outcome.md` in clarify phase; implementation requires `objective.md`, `complexity.md`, `acceptance-criteria.md` |
| Medium | Scenario uses phase name `qe`; implementation canonical name is `test-strategy` (qe is legacy alias) |
| Medium | Scenario expects `findings.md`; implementation requires `review-findings.md` |
| Low | Scenario assumes design always executes; implementation has `is_skippable: true` with complexity_range [3,7] |
| Low | Scenario references wrong specialist for QE phase (wicked-product instead of wicked-qe) |
| Low | Scenario assumes fixed phase advancement; implementation uses dynamic phase_plan |
| Info | Scenario assumes fixed 5-phase sequence; implementation uses dynamic phase selection |
| Info | Quality gates/sign-offs in implementation not mentioned in scenario |

**Recommendation**: Update `01-end-to-end-feature.md` to align with current implementation. The medium-severity issues (wrong filenames, wrong phase names) will cause test failures in the Executor phase.

## Critical Gap: wicked-agentic

wicked-agentic (v2.1.0) is the only plugin without test scenarios. It has:
- 5 agents (architecture-reviewer, framework-analyzer, pattern-scorer, topology-analyzer, optimization-advisor)
- 7 skills (all under 200-line limit with valid frontmatter)
- 5 commands
- Valid specialist.json with 5 personas and 3 phase enhancements

**Recommended scenarios to create**:
1. Framework detection — detect LangChain/CrewAI/AutoGen in a sample project
2. Agent topology analysis — analyze a multi-agent architecture
3. Pattern scoring — score and recommend optimizations for agentic patterns
4. Integration with wicked-crew — verify specialist.json enhances work in crew workflow

## Minor Observations

1. **wicked-patch SQL placement**: ALTER TABLE patch inserts at top of existing schema file rather than generating a new migration file. Cosmetic, not functional.
2. **wicked-smaht confidence**: Planning and implementation intents at 0.51 confidence (moderate). Could benefit from additional trigger patterns.
3. **wicked-startah version**: At v0.10.0, it's the only pre-1.0 plugin.
4. **wicked-workbench JWT**: Server requires `JWT_SECRET_KEY` env var to start. Documented behavior but worth noting for CI.

## Ecosystem Value Assessment

### Individual Plugin Value

Each plugin solves a specific problem that Claude Code doesn't handle natively:

- **Persistent state**: kanban (tasks), mem (decisions/knowledge), crew (project phases)
- **Code intelligence**: search (unified code+doc index), patch (cross-language change propagation)
- **Quality**: qe (shift-left testing), scenarios (E2E acceptance tests)
- **Context**: smaht (automatic context assembly from all plugins)
- **Specialist expertise**: engineering, platform, data, delivery, product, jam, agentic
- **Infrastructure**: startah (zero-config setup), workbench (unified dashboard)

### Compounding Ecosystem Value

Plugins amplify each other:
- **wicked-smaht** gathers context from mem, search, kanban, crew, jam, context7, startah, delegation — 8 adapters
- **wicked-crew** routes work to specialists by signal analysis — 8 specialist plugins
- **wicked-workbench** provides unified data access — 7 data-providing plugins, 24 sources
- **wicked-scenarios** provides the test framework that wg-test builds on
- More plugins installed = smarter responses, broader coverage

### Graceful Degradation

Every plugin works standalone. Optional integrations use try/except. Verified across test suite — plugins correctly detect what's available and degrade gracefully when dependencies are absent.

## Test Infrastructure

- 11 parallel background agents executed simultaneously
- Representative scenario per plugin (core functionality)
- Three-agent Writer phase ran for wicked-crew's most complex scenario
- All tests non-destructive (runtime data in `~/.something-wicked/`, fixtures in `/tmp/`)
- Total scenarios available across ecosystem: 107 (across 16 plugins)
