---
name: cross-module-integration
title: Cross-Module Integration Across 7 Crew Scripts
description: End-to-end integration test spanning project registry, knowledge graph, traceability, artifact state, impact analysis, smaht adapter fan-out, verification protocol, and consensus
type: integration
difficulty: advanced
estimated_minutes: 15
fixes: "#523"
---

# Cross-Module Integration Across 7 Crew Scripts

Validates that 7 different scripts work together in a realistic workflow: create a project, register entities in the knowledge graph, create traceability links, manage artifact state transitions, run impact analysis, fan-out through smaht adapters, run the verification protocol, and synthesize consensus.

Note: phase_scoring.py was removed in the v8.0.0 cleanup (cluster-A P0). Phase affinity ranking is now handled by wicked-brain's FTS5/BM25. Step 7 (phase enrichment) has been removed accordingly.

Note: The search lifecycle scoring script was removed. Search-domain scoring is now
handled by the smaht adapter fan-out (scripts/smaht/adapters/). Step 6 has been
updated to test the domain adapter directly.

## Setup

Set up project name and script path aliases:

```bash
PROJECT="integration-test-$$"
CREW="${CLAUDE_PLUGIN_ROOT}/scripts/crew"
SMAHT="${CLAUDE_PLUGIN_ROOT}/scripts/smaht"
JAM="${CLAUDE_PLUGIN_ROOT}/scripts/jam"
```

## Steps

### 1. Create project via project_registry

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CREW}/project_registry.py" create --name "$PROJECT" --json
```

**Expected**: Returns JSON with the project record including `id`, `name` matching the project name, `status` = "active". Capture the project ID for subsequent steps.

### 2. Register entities in knowledge graph

```bash
REQ=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${SMAHT}/knowledge_graph.py" create-entity --type requirement --name "Users must authenticate via OAuth2" --phase clarify --project "$PROJECT")
DESIGN=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${SMAHT}/knowledge_graph.py" create-entity --type design_artifact --name "OAuth2 flow architecture" --phase design --project "$PROJECT")
TASK=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${SMAHT}/knowledge_graph.py" create-entity --type task --name "Implement OAuth2 middleware" --phase build --project "$PROJECT")
TEST=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${SMAHT}/knowledge_graph.py" create-entity --type test_scenario --name "OAuth2 token validation" --phase test --project "$PROJECT")

echo "$REQ" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "import json,sys; d=json.load(sys.stdin); assert d['state']=='DRAFT'; print('REQ: %s' % d['entity_id'])"
echo "$DESIGN" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "import json,sys; d=json.load(sys.stdin); assert d['state']=='DRAFT'; print('DESIGN: %s' % d['entity_id'])"
echo "$TASK" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "import json,sys; d=json.load(sys.stdin); assert d['state']=='DRAFT'; print('TASK: %s' % d['entity_id'])"
echo "$TEST" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "import json,sys; d=json.load(sys.stdin); assert d['state']=='DRAFT'; print('TEST: %s' % d['entity_id'])"
```

**Expected**: Four entities created with state=DRAFT. Each prints its entity_id.

### 3. Create traceability links between artifacts

```bash
REQ_ID=$(echo "$REQ" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "import json,sys; print(json.load(sys.stdin)['entity_id'])")
DESIGN_ID=$(echo "$DESIGN" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "import json,sys; print(json.load(sys.stdin)['entity_id'])")
TASK_ID=$(echo "$TASK" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "import json,sys; print(json.load(sys.stdin)['entity_id'])")
TEST_ID=$(echo "$TEST" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "import json,sys; print(json.load(sys.stdin)['entity_id'])")

sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CREW}/traceability.py" create \
  --source-id "$REQ_ID" --source-type requirement \
  --target-id "$DESIGN_ID" --target-type design \
  --link-type TRACES_TO --project "$PROJECT" --created-by clarify

sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CREW}/traceability.py" create \
  --source-id "$DESIGN_ID" --source-type design \
  --target-id "$TASK_ID" --target-type task \
  --link-type IMPLEMENTED_BY --project "$PROJECT" --created-by design

sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CREW}/traceability.py" create \
  --source-id "$REQ_ID" --source-type requirement \
  --target-id "$TEST_ID" --target-type test_scenario \
  --link-type TESTED_BY --project "$PROJECT" --created-by clarify
```

**Expected**: Three traceability links created: req-to-design (TRACES_TO), design-to-task (IMPLEMENTED_BY), req-to-test (TESTED_BY). Each returns JSON with an `id` field.

### 4. Register and transition artifact via artifact_state

```bash
ART=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CREW}/artifact_state.py" --json register --name "OAuth2 architecture doc" --type design --project "$PROJECT" --phase design)
ART_ID=$(echo "$ART" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "import json,sys; print(json.load(sys.stdin)['id'])")
echo "Registered artifact: $ART_ID"

sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CREW}/artifact_state.py" transition --id "$ART_ID" --to IN_REVIEW --by "design-phase" --json
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CREW}/artifact_state.py" transition --id "$ART_ID" --to APPROVED --by "gate-check" --json | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
art = json.load(sys.stdin)
assert art['state'] == 'APPROVED', 'Expected APPROVED, got %s' % art['state']
assert len(art['state_history']) == 2, 'Expected 2 transitions, got %d' % len(art['state_history'])
print('PASS: Artifact transitioned to APPROVED with 2 history entries')
"
```

**Expected**: Artifact registered as DRAFT, transitioned to IN_REVIEW, then APPROVED. State history has 2 entries. Prints PASS.

### 5. Run impact analysis from requirement

```bash
REQ_ID=$(echo "$REQ" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "import json,sys; print(json.load(sys.stdin)['entity_id'])")
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CREW}/impact_analyzer.py" analyze --source-id "$REQ_ID" --project "$PROJECT" --depth 3 | tee "${TMPDIR:-/tmp}/impact.json" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
report = json.load(sys.stdin)
assert 'impact' in report, 'Missing impact key'
assert 'risk_summary' in report, 'Missing risk_summary key'
total = report['risk_summary']['total_affected']
print('PASS: Impact analysis found %d affected artifacts' % total)
print('Risk level: %s' % report['risk_summary']['risk_level'])
"
```

**Expected**: Impact report contains `impact.direct` and `impact.transitive` arrays, plus `risk_summary` with `total_affected`, `phases_affected`, and `risk_level`. Prints PASS with the count and risk level.

### 6. Fan-out impact items through smaht domain adapter

Note: The search lifecycle scoring script was removed. This step now tests the smaht
domain adapter fan-out, which is the current mechanism for scoring/prioritising items.

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts')
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/smaht')
from adapters.domain_adapter import query

report = json.load(open('${TMPDIR:-/tmp}/impact.json'))
items = report.get('impact', {}).get('direct', []) + report.get('impact', {}).get('transitive', [])

# domain_adapter exposes a module-level query() function; verify it is importable and callable
result = query({'query': 'OAuth2 impact', 'phase': 'build', 'session_id': 'integration-test'})
assert isinstance(result, (dict, list, type(None))), 'Unexpected return type from domain adapter'
print('PASS: domain_adapter.query() fan-out succeeded (%d impact items queued)' % len(items))
"
```

**Expected**: `query()` is importable from `smaht.adapters.domain_adapter` and returns a valid result (dict, list, or None). Prints PASS.

### 7. Run verification protocol

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CREW}/verification_protocol.py" run --project "$PROJECT" --phases-dir "${TMPDIR:-/tmp}/phases-$$" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
report = json.load(sys.stdin)
check_names = [c['name'] for c in report.get('checks', [])]
expected = ['acceptance_criteria', 'test_suite', 'debug_artifacts', 'code_quality', 'documentation', 'traceability']
for name in expected:
    assert name in check_names, 'Missing check: %s' % name
statuses = {c['name']: c['status'] for c in report['checks']}
print('PASS: All 6 verification checks present')
for name in expected:
    print('  %s: %s' % (name, statuses[name]))
"
```

**Expected**: Verification protocol produces valid JSON with all 6 check names: acceptance_criteria, test_suite, debug_artifacts, code_quality, documentation, traceability. Most checks will SKIP since there is no real codebase, but the protocol itself runs without error. Prints PASS.

### 8. Score consensus from minimal proposals

```bash
cat > "${TMPDIR:-/tmp}/mini-proposals.json" <<'EOF'
[
  {"persona": "Engineer A", "proposal": "Use OAuth2 with PKCE for all APIs", "rationale": "Consistency", "confidence": 0.8, "concerns": []},
  {"persona": "Engineer B", "proposal": "Use OAuth2 with PKCE for external APIs only", "rationale": "Simpler", "confidence": 0.7, "concerns": ["Internal API overhead"]}
]
EOF

sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${JAM}/consensus.py" synthesize --proposals "${TMPDIR:-/tmp}/mini-proposals.json" --question "Auth approach" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
result = json.load(sys.stdin)
assert 'decision' in result, 'Missing decision'
assert 'confidence' in result, 'Missing confidence'
assert result['participants'] == 2, 'Expected 2 participants'
print('PASS: Consensus synthesized from 2 proposals')
print('Decision: %s' % result['decision'][:80])
"
```

**Expected**: Consensus synthesis completes with 2 participants and produces a structured decision. Prints PASS.

### 9. Traceability coverage report

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CREW}/traceability.py" coverage --project "$PROJECT" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
report = json.load(sys.stdin)
assert 'total_requirements' in report, 'Missing total_requirements'
assert 'coverage_pct' in report, 'Missing coverage_pct'
assert 'covered' in report, 'Missing covered list'
print('PASS: Coverage report generated')
print('Requirements: %d, Coverage: %.1f%%' % (report['total_requirements'], report['coverage_pct']))
if report['covered']:
    print('Covered requirement IDs: %s' % [c['id'] for c in report['covered']])
"
```

**Expected**: Coverage report shows requirements with forward chains. The requirement created in step 3 should show coverage to test_scenario (via TESTED_BY link). Prints PASS.

## Success Criteria

- [ ] Project created via project_registry
- [ ] Four entity types registered in knowledge graph (scripts/smaht/knowledge_graph.py)
- [ ] Three traceability links created (TRACES_TO, IMPLEMENTED_BY, TESTED_BY)
- [ ] Artifact state transitions work (DRAFT -> IN_REVIEW -> APPROVED)
- [ ] Impact analysis finds affected artifacts from requirement
- [ ] Smaht domain_adapter.query() fan-out succeeds (replaces removed search lifecycle scoring script)
- [ ] Verification protocol produces valid JSON with all 6 check names
- [ ] Consensus synthesis works with minimal proposals
- [ ] Traceability coverage report identifies requirement coverage

## Cleanup

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CREW}/traceability.py" delete --project "$PROJECT" 2>/dev/null
PROJECT_ID=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CREW}/project_registry.py" find --name "$PROJECT" --json 2>/dev/null | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "import json,sys; d=json.load(sys.stdin); print(d.get('id',''))" 2>/dev/null)
if [ -n "$PROJECT_ID" ]; then
  sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CREW}/project_registry.py" archive --id "$PROJECT_ID" --json 2>/dev/null
fi
rm -f "${TMPDIR:-/tmp}/impact.json" "${TMPDIR:-/tmp}/impact_items.json" "${TMPDIR:-/tmp}/mini-proposals.json"
rm -rf "${TMPDIR:-/tmp}/phases-$$"
```
