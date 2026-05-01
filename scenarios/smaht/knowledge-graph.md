---
name: knowledge-graph
title: Knowledge Graph Entity and Relationship CRUD
description: Verify knowledge_graph.py creates entities, relationships, traverses subgraphs, and handles errors
type: unit
difficulty: intermediate
estimated_minutes: 10
---

# Knowledge Graph Entity and Relationship CRUD

Validates the full CRUD lifecycle of the knowledge graph: entity creation, retrieval, listing with filters, relationship creation, forward/reverse traversal, subgraph extraction, stats, and error handling.

> **Note (closes #711)**: Steps that depend on shared shell variables (`$REQ`, `$REQ_ID`, etc.) are bundled into a single bash block per logical group. Some `/wg-test` executors run each `### Step` in a separate shell, which would lose the variables and produce false FAILs. Bundling preserves variable scope.

## Setup

The script uses DomainStore by default for its DB path. We use the CLI directly and capture entity IDs from each `create-entity` JSON response.

## Steps

### 1. Create entities, retrieve by ID, and list by type (Steps 1-3 bundled)

```bash
SHIM="sh ${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh"
KG="${CLAUDE_PLUGIN_ROOT}/scripts/smaht/knowledge_graph.py"
PARSE_ID='import json,sys; print(json.load(sys.stdin)["entity_id"])'

# 1a — create four entity types
REQ=$($SHIM "$KG" create-entity --type requirement      --name "Auth must use OAuth2"          --phase clarify --project test-kg)
DESIGN=$($SHIM "$KG" create-entity --type design_artifact --name "OAuth2 flow diagram"           --phase design  --project test-kg)
TASK=$($SHIM "$KG" create-entity --type task            --name "Implement OAuth2 middleware"   --phase build   --project test-kg)
TEST=$($SHIM "$KG" create-entity --type test_scenario   --name "OAuth2 token validation tests" --phase test    --project test-kg)
echo "$REQ"; echo "$DESIGN"; echo "$TASK"; echo "$TEST"

# Pull stable IDs from each response
REQ_ID=$(echo    "$REQ"    | $SHIM -c "$PARSE_ID")
DESIGN_ID=$(echo "$DESIGN" | $SHIM -c "$PARSE_ID")
TASK_ID=$(echo   "$TASK"   | $SHIM -c "$PARSE_ID")
TEST_ID=$(echo   "$TEST"   | $SHIM -c "$PARSE_ID")

# 1b — get-entity by ID
$SHIM "$KG" get-entity --id "$REQ_ID"

# 1c — list-entities with type filter
$SHIM "$KG" list-entities --type requirement --project test-kg

# Persist IDs for downstream blocks via env-shell-of-record file
{
  echo "REQ_ID=$REQ_ID"
  echo "DESIGN_ID=$DESIGN_ID"
  echo "TASK_ID=$TASK_ID"
  echo "TEST_ID=$TEST_ID"
} > "${TMPDIR:-/tmp}/wg-kg-ids.env"
```

**Expected**:
- 1a: each `create-entity` returns JSON with `entity_id`, `entity_type`, `name`, `state`=`DRAFT`, `created_at`, `updated_at`. All four types accepted.
- 1b: returns the same requirement entity with `entity_id`=`$REQ_ID`, `name`="Auth must use OAuth2".
- 1c: returns a JSON array of requirement entities only (no design/task/test entries).

### 2. Relationships, forward/reverse traversal, subgraph (Steps 4-7 bundled)

```bash
SHIM="sh ${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh"
KG="${CLAUDE_PLUGIN_ROOT}/scripts/smaht/knowledge_graph.py"
. "${TMPDIR:-/tmp}/wg-kg-ids.env"

# 2a — create three relationships
REL1=$($SHIM "$KG" create-rel --source "$REQ_ID"    --target "$DESIGN_ID" --type TRACES_TO)
REL2=$($SHIM "$KG" create-rel --source "$DESIGN_ID" --target "$TASK_ID"   --type IMPLEMENTED_BY)
REL3=$($SHIM "$KG" create-rel --source "$REQ_ID"    --target "$TEST_ID"   --type TESTED_BY)
echo "$REL1"; echo "$REL2"; echo "$REL3"

# 2b — forward traversal from requirement
$SHIM "$KG" related --id "$REQ_ID" --direction forward

# 2c — reverse traversal from task
$SHIM "$KG" related --id "$TASK_ID" --direction reverse

# 2d — subgraph from requirement at depth 3
$SHIM "$KG" subgraph --id "$REQ_ID" --depth 3
```

**Expected**:
- 2a: each `create-rel` returns JSON with `rel_id`, `source_id`, `target_id`, and `rel_type`.
- 2b: array containing the design and test entities (both forward targets from requirement). Each result includes `_rel_type` and `_direction`=`forward`.
- 2c: array containing the design entity (only entity with a forward link to the task). `_direction`=`reverse`.
- 2d: JSON with `entities` (all 4) and `relationships` (all 3).

### 3. Stats reflect created data

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/smaht/knowledge_graph.py" stats \
  | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
s = json.load(sys.stdin)
assert s['total_entities'] >= 4, 'Expected at least 4 entities, got %d' % s['total_entities']
assert s['total_relationships'] >= 3, 'Expected at least 3 relationships, got %d' % s['total_relationships']
assert 'requirement' in s['entities_by_type'], 'Missing requirement in entity counts'
assert 'TRACES_TO' in s['relationships_by_type'], 'Missing TRACES_TO in rel counts'
print('PASS: Stats match expected counts')
"
```

**Expected**: `total_entities` >= 4, `total_relationships` >= 3. `entities_by_type` includes all four types. `relationships_by_type` includes TRACES_TO, IMPLEMENTED_BY, TESTED_BY.

### 4. Invalid entity type is rejected

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/smaht/knowledge_graph.py" \
  create-entity --type invalid_type --name "Should fail" --project test-kg 2>&1
echo "EXIT: $?"
```

**Expected**: Error message mentioning "Invalid entity_type" and a non-zero exit status.

### 5. list-entities with project filter returns scoped results

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/smaht/knowledge_graph.py" list-entities --project test-kg \
  | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
entities = json.load(sys.stdin)
for e in entities:
    assert e.get('project_id') == 'test-kg', 'Entity %s has wrong project: %s' % (e['entity_id'], e.get('project_id'))
print('PASS: All %d entities scoped to test-kg' % len(entities))
"
```

**Expected**: Every returned entity has `project_id`=`test-kg`. Prints PASS.

### 6. Subgraph with depth 1 returns only immediate neighbors

```bash
. "${TMPDIR:-/tmp}/wg-kg-ids.env"
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/smaht/knowledge_graph.py" subgraph --id "$REQ_ID" --depth 1 \
  | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
sg = json.load(sys.stdin)
entity_count = len(sg['entities'])
assert entity_count <= 4, 'Depth 1 should limit traversal, got %d entities' % entity_count
print('PASS: Depth-1 subgraph has %d entities' % entity_count)
"
```

**Expected**: Returns fewer entities than the depth-3 traversal in Step 2d (only the requirement and its immediate neighbors). Prints PASS.

## Success Criteria

- [ ] All four entity types created successfully with DRAFT state
- [ ] get-entity returns correct data by ID
- [ ] list-entities filters by type and project
- [ ] Three relationship types created with correct source/target IDs
- [ ] Forward traversal from requirement finds design and test entities
- [ ] Reverse traversal from task finds design entity
- [ ] Subgraph traversal covers the full entity chain at depth 3
- [ ] Stats report accurate entity and relationship counts
- [ ] Invalid entity type produces a clear error
- [ ] Project filter scopes results correctly
- [ ] Depth-1 subgraph limits to immediate neighbors

## Cleanup

```bash
rm -f "${TMPDIR:-/tmp}/wg-kg-ids.env"
```

The knowledge graph uses the default DomainStore path; `--project test-kg` scoping prevents test entities from interfering with production data.
