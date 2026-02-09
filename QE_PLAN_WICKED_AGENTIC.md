# QE Plan: wicked-agentic Plugin

**Version**: 1.0
**Target**: wicked-agentic v0.1.0
**Generated**: 2026-02-05
**Confidence**: HIGH

## Executive Summary

Complete QE strategy for wicked-agentic, a plugin that validates agentic application architecture. This plan covers detection script testing, fixture design, quality gates for crew phases, integration scenarios, and acceptance criteria.

## 1. Test Scenarios by Component

### 1.1 Detection Scripts

#### detect_framework.py

**Purpose**: Identifies agentic frameworks in codebases

**Happy Path (P1)**
| ID | Scenario | Input | Expected Output | Acceptance |
|----|----------|-------|----------------|------------|
| DF-H1 | Detect ADK project | Repo with `from anthropic_adk import Agent` | Framework=ADK, confidence≥0.85 | Identifies all agent definitions |
| DF-H2 | Detect LangGraph project | Repo with `from langgraph import StateGraph` | Framework=LangGraph, confidence≥0.85 | Identifies graph nodes |
| DF-H3 | Detect CrewAI project | Repo with `from crewai import Crew, Agent` | Framework=CrewAI, confidence≥0.85 | Identifies crew + agents |
| DF-H4 | Detect Mastra (TS) | TS repo with `import { Agent } from '@mastra/core'` | Framework=Mastra, confidence≥0.85 | Works with TypeScript |
| DF-H5 | Detect Vercel AI SDK | TS repo with `import { generateText } from 'ai'` | Framework=Vercel AI, confidence≥0.85 | Works with JS/TS |

**Error Cases (P1)**
| ID | Scenario | Input | Expected Output | Acceptance |
|----|----------|-------|----------------|------------|
| DF-E1 | Non-agentic repo | Standard Flask/Django app | Framework=None, confidence≥0.90 | No false positives |
| DF-E2 | Partial match | Has `agent.py` but no framework imports | Framework=Unknown, confidence≤0.40 | Low confidence warning |
| DF-E3 | Empty/missing files | Directory with no Python/JS files | Framework=None, confidence=1.0 | Graceful handling |
| DF-E4 | Malformed imports | Syntax errors in agent files | Framework=None with warning | No crashes |
| DF-E5 | Mixed signals | Both LangChain and LangGraph imports | Framework=Multiple with list | Reports all detected |

**Edge Cases (P2)**
| ID | Scenario | Input | Expected Output | Acceptance |
|----|----------|-------|----------------|------------|
| DF-D1 | Monorepo with multiple frameworks | `/backend` has ADK, `/frontend` has Vercel AI | Multiple frameworks with paths | Scopes by directory |
| DF-D2 | Deep nested agent files | Agents 6+ levels deep | Framework detected | Works regardless of depth |
| DF-D3 | Custom framework | Proprietary agent framework | Framework=Custom, confidence≤0.60 | Fallback detection |
| DF-D4 | Agents in tests | Agent code only in test files | Framework detected, note=test-only | Flags test-only usage |
| DF-D5 | Version-specific patterns | LangGraph v0.0.x vs v0.2.x | Detects correct version | Version awareness |

**False Positive Prevention (P1)**
| ID | Scenario | Input | Expected Negative | Acceptance |
|----|----------|-------|------------------|------------|
| DF-FP1 | ML training script | agent.py with RL agent (gym) | NOT agentic | No false positive |
| DF-FP2 | Game AI | agent.py with game AI logic | NOT agentic | No false positive |
| DF-FP3 | SSH agent wrapper | ssh_agent.py utility | NOT agentic | No false positive |
| DF-FP4 | User agent strings | HTTP client with user agent | NOT agentic | No false positive |

---

#### analyze_agents.py

**Purpose**: Maps agent topology and relationships

**Happy Path (P1)**
| ID | Scenario | Input | Expected Output | Acceptance |
|----|----------|-------|----------------|------------|
| AA-H1 | Flat agent topology | 3 independent agents | Graph with 3 nodes, 0 edges | Correct isolation |
| AA-H2 | Simple hierarchy | Main agent → 2 sub-agents | Graph with 3 nodes, 2 edges, depth=2 | Parent-child links |
| AA-H3 | Delegation chain | Agent A → B → C (linear) | Chain topology, depth=3 | Correct ordering |
| AA-H4 | Crew topology | Crew with 4 specialized agents | Crew pattern detected | Role identification |
| AA-H5 | Mixed pattern | Crew + standalone agents | Multiple patterns | Pattern coexistence |

**Error Cases (P1-P2)**
| ID | Scenario | Input | Expected Output | Acceptance |
|----|----------|-------|----------------|------------|
| AA-E1 | Circular delegation | Agent A → B → C → A | Cycle detected, warning | Anti-pattern flagged |
| AA-E2 | Orphaned agents | Agent definitions with no usage | Graph with isolated nodes | Reports orphans |
| AA-E3 | Missing agent definition | Agent referenced but not defined | Graph with placeholder | Warns about missing |
| AA-E4 | Ambiguous delegation | Dynamic agent selection | Graph with conditional edges | Notes uncertainty |

**Edge Cases (P2-P3)**
| ID | Scenario | Input | Expected Output | Acceptance |
|----|----------|-------|----------------|------------|
| AA-D1 | Deep hierarchy | 9+ levels of agent nesting | Full graph, anti-pattern P1 | Deep nesting warning |
| AA-D2 | Wide fanout | Agent delegates to 10+ agents | Full graph, anti-pattern P2 | Wide fanout warning |
| AA-D3 | Dynamic agents | Agents created at runtime | Partial graph with note | Best-effort mapping |
| AA-D4 | Cross-file agents | Agent definitions across modules | Complete graph | Module traversal |
| AA-D5 | Conditional agents | Agents loaded by config | Graph with variants | Shows all paths |

---

#### pattern_scorer.py

**Purpose**: Scores against anti-patterns from Mars ODAI review

**Happy Path (P1)**
| ID | Scenario | Input | Expected Output | Acceptance |
|----|----------|-------|----------------|------------|
| PS-H1 | Clean architecture | Well-structured agents | Score≥85, no critical issues | Healthy baseline |
| PS-H2 | Minor issues | 1-2 P3 anti-patterns | Score 70-84, warnings only | Acceptable |
| PS-H3 | Multiple anti-patterns | 3+ anti-patterns (mixed severity) | Score<70, prioritized list | Clear guidance |

**Anti-Pattern Detection (P1)**
| ID | Anti-Pattern | Detection Criteria | Severity | Acceptance |
|----|--------------|-------------------|----------|------------|
| PS-AP1 | Deep nesting (9+ levels) | `depth > 8` | P1 Critical | Exact threshold |
| PS-AP2 | Sync-in-async (blocking calls) | `time.sleep()` or `requests.get()` in async | P1 Critical | Detects both |
| PS-AP3 | Missing guardrails | No timeout/retry config | P1 Critical | Checks config |
| PS-AP4 | Context overflow | Prompt template >8k tokens | P2 Warning | Token counting |
| PS-AP5 | Missing error handling | Agent calls without try/except | P2 Warning | AST analysis |
| PS-AP6 | Hardcoded prompts | No prompt templates/variables | P3 Info | String analysis |
| PS-AP7 | Missing observability | No logging/tracing | P3 Info | Import checks |

**Edge Cases (P2)**
| ID | Scenario | Input | Expected Output | Acceptance |
|----|----------|-------|----------------|------------|
| PS-D1 | Borderline scoring | Score exactly 70 | Clear threshold messaging | Consistent rounding |
| PS-D2 | Conflicting patterns | Good + bad in same file | Mixed score with context | Nuanced analysis |
| PS-D3 | False positive mitigation | Legitimate blocking call | Excludes with comment | Smart filtering |

---

#### issue_taxonomy.py

**Purpose**: Classifies findings by severity

**Happy Path (P1)**
| ID | Scenario | Input | Expected Output | Acceptance |
|----|----------|-------|----------------|------------|
| IT-H1 | Critical issue | Deep nesting detected | Severity=CRITICAL, category=architecture | Correct classification |
| IT-H2 | Warning | Missing retry config | Severity=WARNING, category=reliability | Correct classification |
| IT-H3 | Info | Hardcoded prompt | Severity=INFO, category=maintainability | Correct classification |
| IT-H4 | Multiple issues | Mixed severities | Grouped by severity | Prioritized output |

**Classification Accuracy (P1)**
| ID | Category | Example Finding | Expected Severity | Acceptance |
|----|----------|----------------|------------------|------------|
| IT-C1 | Architecture | Deep nesting (9+ levels) | CRITICAL | P1 anti-pattern |
| IT-C2 | Performance | Sync-in-async blocking | CRITICAL | P1 anti-pattern |
| IT-C3 | Reliability | Missing guardrails | CRITICAL | P1 anti-pattern |
| IT-C4 | Performance | Context overflow (8k+) | WARNING | P2 anti-pattern |
| IT-C5 | Reliability | Missing error handling | WARNING | P2 anti-pattern |
| IT-C6 | Maintainability | Hardcoded prompts | INFO | P3 anti-pattern |
| IT-C7 | Observability | Missing logging | INFO | P3 anti-pattern |

**Edge Cases (P2)**
| ID | Scenario | Input | Expected Output | Acceptance |
|----|----------|-------|----------------|------------|
| IT-D1 | Duplicate findings | Same issue in 2 files | Deduplicated with count | No noise |
| IT-D2 | Severity upgrade | Multiple warnings → critical | Aggregated severity | Smart escalation |
| IT-D3 | Context-dependent | Issue severity varies by context | Contextual severity | Nuanced |

---

### 1.2 Command Testing

#### /wicked-agentic:review

**Happy Path (P1)**
| ID | Scenario | Input | Expected Output | Acceptance |
|----|----------|-------|----------------|------------|
| CMD-R1 | Review ADK project | Path to ADK repo | Markdown report with findings | Complete analysis |
| CMD-R2 | Review with --format json | --format json flag | JSON output schema valid | Schema compliance |
| CMD-R3 | Review specific path | --path backend/agents | Scoped analysis | Correct scope |

**Error Cases (P1)**
| ID | Scenario | Input | Expected Output | Acceptance |
|----|----------|-------|----------------|------------|
| CMD-R-E1 | Invalid path | Nonexistent directory | Error message, exit code 1 | Graceful failure |
| CMD-R-E2 | Permission denied | No read access | Clear error message | User-friendly |
| CMD-R-E3 | No agentic code | Non-agentic repo | "No agentic patterns found" | No false positives |

---

#### /wicked-agentic:design

**Happy Path (P1)**
| ID | Scenario | Input | Expected Output | Acceptance |
|----|----------|-------|----------------|------------|
| CMD-D1 | Validate design doc | Path to architecture.md | Design feedback | Actionable |
| CMD-D2 | Agent topology review | Graph JSON input | Topology analysis | Pattern detection |

---

#### /wicked-agentic:frameworks

**Happy Path (P1)**
| ID | Scenario | Input | Expected Output | Acceptance |
|----|----------|-------|----------------|------------|
| CMD-F1 | List frameworks | No args | Table of supported frameworks | Complete list |
| CMD-F2 | Compare frameworks | --compare ADK LangGraph | Comparison matrix | Feature parity |

---

#### /wicked-agentic:audit

**Happy Path (P1)**
| ID | Scenario | Input | Expected Output | Acceptance |
|----|----------|-------|----------------|------------|
| CMD-A1 | Full audit | Path to repo | Complete audit report | All checks run |
| CMD-A2 | Specific checks | --checks security,performance | Subset of checks | Correct filtering |

---

### 1.3 Agent Testing

**Agents**: architect, safety-reviewer, performance-analyst, framework-researcher, pattern-advisor

**Agent Contract (P1)**
| ID | Requirement | Test | Acceptance |
|----|------------|------|------------|
| AG-C1 | Agent responds to prompt | Send test prompt | Response within 60s |
| AG-C2 | Agent follows role | Prompt for role-specific task | Response aligned with role |
| AG-C3 | Agent outputs valid format | Request structured output | Schema-valid JSON/markdown |
| AG-C4 | Agent handles errors | Prompt with missing context | Graceful error response |

---

### 1.4 Hook Testing

**Hook**: Auto-detection on file reads

**Happy Path (P1)**
| ID | Scenario | Trigger | Expected Behavior | Acceptance |
|----|----------|---------|------------------|------------|
| HK-H1 | First agentic file read | Read `agents/main.py` | Hook fires, detection runs | Triggered once |
| HK-H2 | Cooldown prevents spam | Read 3 agent files in 5s | Hook fires once | Cooldown works |
| HK-H3 | Framework change detection | Edit framework imports | Hook fires on next read | Change detection |

**Edge Cases (P2)**
| ID | Scenario | Trigger | Expected Behavior | Acceptance |
|----|----------|---------|------------------|------------|
| HK-D1 | Hook disabled in settings | User disables hook | No firing | Respects config |
| HK-D2 | Cache invalidation | Framework changes | Cache cleared | Fresh detection |
| HK-D3 | Concurrent reads | 10 file reads at once | Hook fires once | Race condition safe |

---

## 2. Test Fixtures

### 2.1 Fixture Codebases

#### Fixture: minimal-adk
**Purpose**: Happy path ADK detection
**Structure**:
```
minimal-adk/
├── pyproject.toml (anthropic-adk dep)
├── agents/
│   ├── main.py (main agent with 2 tools)
│   ├── researcher.py (sub-agent)
│   └── writer.py (sub-agent)
└── README.md
```
**Characteristics**:
- 3 agents total
- Simple 2-level hierarchy
- Clean architecture (score 90+)
- ADK 0.2.x patterns

**Expected Detection**:
- Framework: ADK (confidence 0.95+)
- Topology: Tree (depth=2, width=2)
- Pattern Score: 90+
- Issues: 0

---

#### Fixture: deep-hierarchy
**Purpose**: Anti-pattern detection (deep nesting)
**Structure**:
```
deep-hierarchy/
└── agents/
    ├── level1.py (main)
    ├── level2.py
    ├── level3.py
    ...
    └── level10.py
```
**Characteristics**:
- 10 levels of nesting
- Linear delegation chain
- Triggers P1 anti-pattern

**Expected Detection**:
- Framework: LangGraph
- Topology: Chain (depth=10)
- Pattern Score: <50
- Issues: 1 CRITICAL (deep nesting)

---

#### Fixture: multi-framework-monorepo
**Purpose**: Multiple framework detection
**Structure**:
```
monorepo/
├── backend/
│   └── agents/ (ADK)
├── ml-pipeline/
│   └── graph.py (LangGraph)
└── frontend/
    └── src/ai/ (Vercel AI SDK)
```
**Characteristics**:
- 3 different frameworks
- Clear separation by directory
- No conflicts

**Expected Detection**:
- Framework: Multiple [ADK, LangGraph, Vercel AI]
- Topology: Per-directory graphs
- Pattern Score: Separate scores per framework

---

#### Fixture: false-positive-ml
**Purpose**: False positive prevention
**Structure**:
```
ml-project/
├── agent.py (RL gym agent)
├── training.py
└── models/
```
**Characteristics**:
- Has `agent.py` but NOT agentic
- Uses reinforcement learning (gym)
- Should NOT trigger detection

**Expected Detection**:
- Framework: None
- Confidence: <0.20
- Warning: "Possible non-agentic agent.py"

---

#### Fixture: typescript-mastra
**Purpose**: TypeScript framework detection
**Structure**:
```
mastra-app/
├── package.json (@mastra/core)
├── src/
│   └── agents/
│       ├── index.ts
│       └── researcher.ts
└── tsconfig.json
```
**Characteristics**:
- TypeScript/JavaScript
- Mastra framework
- Modern ESM imports

**Expected Detection**:
- Framework: Mastra
- Language: TypeScript
- Confidence: 0.85+

---

#### Fixture: mars-odai-anti-patterns
**Purpose**: All anti-patterns from Mars ODAI review
**Structure**:
```
mars-odai/
└── agents/
    ├── deep_nested.py (9 levels)
    ├── blocking_calls.py (sync in async)
    ├── no_guardrails.py (missing config)
    ├── large_context.py (10k token prompt)
    └── no_error_handling.py
```
**Characteristics**:
- Deliberately bad code
- All P1/P2/P3 anti-patterns
- Comprehensive negative test

**Expected Detection**:
- Framework: ADK
- Pattern Score: <30
- Issues: 7+ (3 critical, 2 warning, 2+ info)
- Severity: CRITICAL overall

---

### 2.2 Fixture Data Requirements

**Test Data Assets**:
1. Valid framework examples (6 fixtures above)
2. Golden output files (expected JSON/markdown)
3. Configuration variants (settings.json permutations)
4. Edge case inputs (malformed files, empty repos)
5. Performance test data (large repos for latency testing)

**Maintenance**:
- Fixtures stored in `/plugins/wicked-agentic/tests/fixtures/`
- Each fixture has `README.md` with purpose and expected outputs
- Version-locked dependencies in requirements.txt per fixture
- CI runs full fixture suite on every PR

---

## 3. Quality Gates by Crew Phase

### Phase: Clarify → Design

**Must Pass (Blockers)**:
1. Requirements elicitation complete
   - User goal understood
   - Target codebase identified
   - Scope defined (full audit vs. specific check)

2. Feasibility check
   - Codebase accessible (read permissions)
   - Language/framework supported
   - Size within limits (<1M LOC)

3. Detection pre-flight
   - `detect_framework.py` runs without error
   - Framework identified OR "none found" confirmed
   - Confidence score computed

**Should Pass (Warnings)**:
- Framework version identified
- Test coverage >0% (if applicable)

**Automated Checks**:
```bash
# Gate script: gates/clarify_to_design.sh
python detect_framework.py --path "$TARGET"
if [ $? -ne 0 ]; then
  echo "FAIL: Detection script error"
  exit 1
fi
```

**Human Review Required**: NO
**Approval**: Auto-advance if all pass

---

### Phase: Design → Build

**Must Pass (Blockers)**:
1. Topology analysis complete
   - `analyze_agents.py` ran successfully
   - Agent graph built (or empty if no agents)
   - Cycles detected and flagged

2. Pattern scoring done
   - `pattern_scorer.py` executed
   - Score computed (0-100)
   - Anti-patterns classified

3. Design validated
   - No CRITICAL blocking issues in design
   - Architecture feasible for implementation

**Should Pass (Warnings)**:
- Pattern score >60
- <5 CRITICAL issues

**Automated Checks**:
```bash
# Gate script: gates/design_to_build.sh
python analyze_agents.py --output /tmp/topology.json
python pattern_scorer.py --topology /tmp/topology.json
```

**Human Review Required**: If score <40 or >10 CRITICAL issues
**Approval**: Auto-advance unless human review required

---

### Phase: Build → Review

**Must Pass (Blockers)**:
1. All detection scripts pass
   - detect_framework.py
   - analyze_agents.py
   - pattern_scorer.py
   - issue_taxonomy.py

2. Output schema valid
   - JSON output validates against schema
   - Markdown output well-formed

3. Issue deduplication
   - No duplicate issues
   - Issues grouped by severity

4. Report generated
   - Final report exists
   - Contains all required sections

**Should Pass (Warnings)**:
- Execution time <60s for <10k LOC repos
- Memory usage <500MB

**Automated Checks**:
```bash
# Gate script: gates/build_to_review.sh
pytest tests/test_detection_scripts.py -v
pytest tests/test_schema_validation.py -v
pytest tests/test_performance.py -k "execution_time" -v
```

**Human Review Required**: NO
**Approval**: Auto-advance if all pass

---

### Phase: Review → Done

**Must Pass (Blockers)**:
1. All integration tests pass
   - Standalone mode works
   - Specialist mode works
   - No mode conflicts

2. Acceptance criteria met
   - Detection accuracy ≥90%
   - False positive rate <5%
   - No P1 bugs

3. Documentation complete
   - README.md updated
   - Examples provided
   - Troubleshooting guide

**Should Pass (Warnings)**:
- Performance benchmarks met
- All fixtures pass

**Automated Checks**:
```bash
# Gate script: gates/review_to_done.sh
pytest tests/integration/ -v
pytest tests/acceptance/ -v
python tests/accuracy_validation.py --threshold 0.90
```

**Human Review Required**: YES
**Approval**: Manual sign-off after QE review

---

## 4. Integration Test Scenarios

### 4.1 Standalone + Specialist Conflict Prevention

#### Scenario: Duplicate Run Prevention
**Setup**:
1. User invokes `/wicked-agentic:review` (standalone mode)
2. wicked-crew separately invokes specialist mode during "design" phase

**Expected Behavior**:
- Detection scripts check for lock file: `/tmp/wicked-agentic-{repo_hash}.lock`
- If lock exists and <60s old, skip re-run
- Return cached results from first run
- Log: "Using cached results from [timestamp]"

**Test**:
```bash
# Terminal 1: Standalone
/wicked-agentic:review --path /test/repo

# Terminal 2: Specialist (within 60s)
/wicked-crew:execute  # triggers specialist

# Verify: Only 1 detection run, 2nd uses cache
```

**Acceptance**:
- No duplicate detection runs
- Both modes get same results
- Timestamp shows cache hit

---

#### Scenario: Hook Cooldown Integration
**Setup**:
1. User reads `agents/main.py` (hook fires)
2. User immediately reads `agents/sub.py`
3. User runs `/wicked-agentic:review`

**Expected Behavior**:
- Hook fires on first read, sets cooldown (60s)
- Second read within cooldown: hook skips
- Standalone command respects cooldown, uses cached hook results

**Test**:
```bash
# Read agent file (triggers hook)
cat agents/main.py

# Read another within 60s (should skip)
cat agents/sub.py

# Run standalone (should use cache)
/wicked-agentic:review
```

**Acceptance**:
- Hook fires once
- Cooldown prevents spam
- Standalone command doesn't re-run detection

---

### 4.2 Crew Specialist Mode Integration

#### Scenario: Design Phase Auto-Invocation
**Setup**:
1. wicked-crew starts project
2. Reaches "design" phase
3. Codebase contains agentic code

**Expected Behavior**:
- Crew detects specialist capability match
- Invokes wicked-agentic specialist
- Specialist runs full analysis
- Returns findings to crew
- Crew incorporates into design phase

**Test**:
```bash
# Start crew project with agentic codebase
/wicked-crew:start "Review architecture of ADK agents"

# Advance to design
/wicked-crew:execute

# Verify specialist invoked
grep "wicked-agentic" /tmp/crew-*.log
```

**Acceptance**:
- Specialist invoked during design
- Findings in crew context
- No manual invocation needed

---

#### Scenario: Specialist Results in Crew Report
**Setup**:
1. Crew invokes wicked-agentic specialist
2. Specialist finds 3 CRITICAL issues
3. Crew generates final report

**Expected Behavior**:
- Crew report includes agentic findings section
- Issues prioritized by severity
- Recommendations integrated

**Test**:
```bash
# Complete crew workflow with agentic codebase
/wicked-crew:start "Audit agent architecture"
/wicked-crew:execute
/wicked-crew:evidence

# Verify findings in evidence
```

**Acceptance**:
- Agentic findings in crew evidence
- Severity preserved
- Recommendations actionable

---

### 4.3 Output Schema Validation

#### Scenario: JSON Output Schema
**Setup**:
1. Run detection with `--format json`
2. Parse output

**Expected Schema**:
```json
{
  "version": "1.0",
  "timestamp": "ISO8601",
  "repository": {
    "path": "string",
    "framework": "string|null",
    "confidence": "number"
  },
  "topology": {
    "depth": "number",
    "width": "number",
    "agents": ["Agent[]"],
    "edges": ["Edge[]"],
    "patterns": ["string[]"]
  },
  "score": {
    "overall": "number",
    "architecture": "number",
    "performance": "number",
    "reliability": "number",
    "maintainability": "number"
  },
  "issues": [{
    "severity": "CRITICAL|WARNING|INFO",
    "category": "string",
    "message": "string",
    "file": "string",
    "line": "number|null",
    "recommendation": "string"
  }]
}
```

**Test**:
```bash
/wicked-agentic:review --format json --path /test/repo > output.json
python tests/validate_schema.py output.json
```

**Acceptance**:
- Schema validation passes
- All required fields present
- Data types correct

---

## 5. Acceptance Criteria

### 5.1 Functional Requirements

**F1: Framework Detection (MUST)**
- ✅ Detect ADK, LangGraph, CrewAI, Mastra, Vercel AI
- ✅ Confidence score 0.0-1.0
- ✅ Support Python and TypeScript
- ✅ Handle monorepos
- ✅ False positive rate <5%

**F2: Topology Analysis (MUST)**
- ✅ Build agent graph (nodes + edges)
- ✅ Detect cycles
- ✅ Calculate depth and width
- ✅ Identify patterns (crew, chain, tree, flat)

**F3: Pattern Scoring (MUST)**
- ✅ Score 0-100
- ✅ Detect all Mars ODAI anti-patterns
- ✅ Classify by severity (P1/P2/P3)
- ✅ Provide recommendations

**F4: Issue Classification (MUST)**
- ✅ Group by severity
- ✅ Deduplicate
- ✅ Actionable recommendations

**F5: Multiple Invocation Modes (MUST)**
- ✅ Standalone commands work
- ✅ Crew specialist integration works
- ✅ Hook auto-detection works
- ✅ No conflicts between modes

---

### 5.2 Non-Functional Requirements

**NF1: Performance (MUST)**
- ✅ <10s for repos <10k LOC
- ✅ <60s for repos <100k LOC
- ✅ Memory <500MB

**NF2: Accuracy (MUST)**
- ✅ Detection accuracy ≥90%
- ✅ False positive rate <5%
- ✅ False negative rate <10%

**NF3: Reliability (MUST)**
- ✅ No crashes on malformed input
- ✅ Graceful error messages
- ✅ Retry on transient failures

**NF4: Usability (SHOULD)**
- ✅ Clear error messages
- ✅ Progress indicators for long runs
- ✅ Helpful examples in docs

---

### 5.3 Exit Criteria (Before Release)

**All must pass**:
1. ✅ All P1 test scenarios pass
2. ✅ 6 test fixtures validate
3. ✅ Quality gates automated
4. ✅ Integration tests pass
5. ✅ Schema validation passes
6. ✅ Acceptance criteria met
7. ✅ Documentation complete
8. ✅ /wg-check --full passes

---

## 6. Test Automation Strategy

### 6.1 Unit Tests (pytest)

**Location**: `/plugins/wicked-agentic/tests/unit/`

**Coverage Target**: ≥80% for detection scripts

**Files**:
- `test_detect_framework.py` (40+ tests)
- `test_analyze_agents.py` (30+ tests)
- `test_pattern_scorer.py` (25+ tests)
- `test_issue_taxonomy.py` (15+ tests)

**Run**:
```bash
cd plugins/wicked-agentic
pytest tests/unit/ -v --cov=scripts --cov-report=html
```

---

### 6.2 Integration Tests (pytest)

**Location**: `/plugins/wicked-agentic/tests/integration/`

**Files**:
- `test_standalone_mode.py`
- `test_specialist_mode.py`
- `test_hook_integration.py`
- `test_crew_workflow.py`

**Run**:
```bash
pytest tests/integration/ -v -s
```

---

### 6.3 Fixture Tests (pytest)

**Location**: `/plugins/wicked-agentic/tests/fixtures/`

**Structure**:
```
fixtures/
├── minimal-adk/
│   ├── golden_output.json
│   └── ...
└── test_fixtures.py (runs all fixtures)
```

**Run**:
```bash
pytest tests/test_fixtures.py -v
```

---

### 6.4 Acceptance Tests (behave)

**Location**: `/plugins/wicked-agentic/tests/acceptance/`

**Gherkin Scenarios**:
```gherkin
Feature: Framework Detection
  Scenario: Detect ADK project
    Given a repository with ADK agents
    When I run framework detection
    Then the framework should be "ADK"
    And the confidence should be greater than 0.85
```

**Run**:
```bash
behave tests/acceptance/
```

---

### 6.5 CI/CD Pipeline

**GitHub Actions** (`.github/workflows/wicked-agentic-tests.yml`):
```yaml
name: wicked-agentic Tests

on: [pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      - run: pip install -r requirements.txt
      - run: pytest tests/unit/ -v
      - run: pytest tests/integration/ -v
      - run: pytest tests/fixtures/ -v
      - run: behave tests/acceptance/
      - run: python tests/accuracy_validation.py
```

---

## 7. Risk Assessment

### High Risk
| Risk | Impact | Mitigation |
|------|--------|-----------|
| False positive spam | User annoyance, trust loss | Extensive negative test suite, confidence thresholds |
| Hook firing too often | Performance degradation | 60s cooldown, cache, disable option |
| Deep hierarchy crashes | Script timeout/OOM | Depth limit (50 levels), iterative traversal |

### Medium Risk
| Risk | Impact | Mitigation |
|------|--------|-----------|
| Multi-framework confusion | Incorrect recommendations | Scope detection by directory, clear reporting |
| TypeScript parsing errors | Detection failures | Fallback to regex, graceful degradation |
| Specialist/standalone conflict | Duplicate runs, cache conflicts | Lock files, shared cache, conflict detection |

### Low Risk
| Risk | Impact | Mitigation |
|------|--------|-----------|
| Schema drift | Output parsing breaks | Versioned schema, validation in CI |
| Fixture maintenance | Stale tests | Automated fixture validation, dependency updates |

---

## 8. Testing Timeline

**Week 1: Foundation**
- Day 1-2: Write unit tests for detect_framework.py
- Day 3-4: Write unit tests for analyze_agents.py
- Day 5: Create first 3 fixtures (minimal-adk, deep-hierarchy, false-positive-ml)

**Week 2: Coverage**
- Day 1-2: Write unit tests for pattern_scorer.py and issue_taxonomy.py
- Day 3-4: Create remaining 3 fixtures
- Day 5: Integration tests (standalone + specialist modes)

**Week 3: Integration**
- Day 1-2: Hook integration tests
- Day 3-4: Crew workflow tests
- Day 5: Schema validation and acceptance tests

**Week 4: Validation**
- Day 1-2: Run full test suite, fix failures
- Day 3: Accuracy validation (≥90% detection accuracy)
- Day 4: Performance benchmarking
- Day 5: Documentation and QE sign-off

---

## 9. Success Metrics

**Quantitative**:
- Test coverage ≥80%
- Detection accuracy ≥90%
- False positive rate <5%
- False negative rate <10%
- All fixtures pass
- Performance within SLA (<60s for <100k LOC)

**Qualitative**:
- Clear, actionable recommendations
- No user-reported false positives in first 30 days
- Positive feedback on crew integration
- Zero P1 bugs in production

---

## 10. Appendix: Test Data Generation

### Generating Synthetic Fixtures

**Script**: `tests/generate_fixture.py`

**Usage**:
```bash
# Generate minimal ADK fixture
python tests/generate_fixture.py --type minimal-adk --output tests/fixtures/minimal-adk

# Generate anti-pattern fixture
python tests/generate_fixture.py --type mars-odai --output tests/fixtures/mars-odai
```

**Capabilities**:
- Generate valid agent code
- Inject anti-patterns
- Create golden output files
- Version-lock dependencies

---

## 11. Recommended Next Steps

1. **Immediate (This Week)**:
   - Create fixtures directory structure
   - Write first 3 fixtures (minimal-adk, deep-hierarchy, false-positive-ml)
   - Implement detect_framework.py with tests

2. **Short-term (Next 2 Weeks)**:
   - Complete all 4 detection scripts with unit tests
   - Implement integration tests for standalone + specialist modes
   - Set up CI/CD pipeline

3. **Medium-term (Next Month)**:
   - Complete all fixtures
   - Implement quality gates automation
   - Run accuracy validation
   - QE sign-off

4. **Long-term (Post-Launch)**:
   - Monitor false positive rate in production
   - Collect user feedback
   - Iterate on anti-pattern library
   - Add support for new frameworks

---

## Document Control

**Author**: test-strategist agent
**Reviewers**: QE Lead, Engineering Manager
**Approval**: TBD
**Next Review**: After Phase 2 (Coverage) completion

**Changelog**:
- 2026-02-05: Initial version (v1.0)
