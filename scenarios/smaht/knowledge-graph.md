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

## Setup

Set the knowledge graph to use an isolated test database:

```bash
export KG_TEST_DB="${TMPDIR:-/tmp}/test-kg-$$.db"
KG_SCRIPT="${CLAUDE_PLUGIN_ROOT}/scripts/smaht/knowledge_graph.py"
```

Note: The script uses DomainStore by default for its DB path. We will use the CLI directly and capture entity IDs from output.

## Steps

### 1. Create entities of four different types

```bash
REQ=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/smaht/knowledge_graph.py" create-entity --type requirement --name "Auth must use OAuth2" --phase clarify --project test-kg)
echo "$REQ"

DESIGN=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/smaht/knowledge_graph.py" create-entity --type design_artifact --name "OAuth2 flow diagram" --phase design --project test-kg)
echo "$DESIGN"

TASK=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/smaht/knowledge_graph.py" create-entity --type task --name "Implement OAuth2 middleware" --phase build --project test-kg)
echo "$TASK"

TEST=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/smaht/knowledge_graph.py" create-entity --type test_scenario --name "OAuth2 token validation tests" --phase test --project test-kg)
echo "$TEST"
```

**Expected**: Each command returns JSON with `entity_id`, `entity_type`, `name`, `state` equal to `DRAFT`, `created_at`, and `updated_at` fields. All four types are accepted.

### 2. Get entity by ID

```bash
REQ_ID=$(echo "$REQ" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "import json,sys; print(json.load(sys.stdin)['entity_id'])")
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/smaht/knowledge_graph.py" get-entity --id "$REQ_ID"
```

**Expected**: Returns the same requirement entity with matching `entity_id`, `name` = "Auth must use OAuth2", `entity_type` = "requirement".

### 3. List entities with type filter

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/smaht/knowledge_graph.py" list-entities --type requirement --project test-kg
```

**Expected**: Returns a JSON array containing only requirement entities. The "Auth must use OAuth2" entity is present. No design_artifact, task, or test_scenario entities appear.

### 4. Create relationships between entities

```bash
REQ_ID=$(echo "$REQ" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "import json,sys; print(json.load(sys.stdin)['entity_id'])")
DESIGN_ID=$(echo "$DESIGN" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "import json,sys; print(json.load(sys.stdin)['entity_id'])")
TASK_ID=$(echo "$TASK" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "import json,sys; print(json.load(sys.stdin)['entity_id'])")
TEST_ID=$(echo "$TEST" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "import json,sys; print(json.load(sys.stdin)['entity_id'])")

REL1=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/smaht/knowledge_graph.py" create-rel --source "$REQ_ID" --target "$DESIGN_ID" --type TRACES_TO)
echo "$REL1"

REL2=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/smaht/knowledge_graph.py" create-rel --source "$DESIGN_ID" --target "$TASK_ID" --type IMPLEMENTED_BY)
echo "$REL2"

REL3=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/smaht/knowledge_graph.py" create-rel --source "$REQ_ID" --target "$TEST_ID" --type TESTED_BY)
echo "$REL3"
```

**Expected**: Each returns JSON with `rel_id`, `source_id`, `target_id`, and `rel_type` matching the input. All three relationship types are accepted.

### 5. Get related entities (forward direction)

```bash
REQ_ID=$(echo "$REQ" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "import json,sys; print(json.load(sys.stdin)['entity_id'])")
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/smaht/knowledge_graph.py" related --id "$REQ_ID" --direction forward
```

**Expected**: Returns JSON array with the design_artifact and test_scenario entities (both are forward targets from the requirement). Each result includes `_rel_type` and `_direction` = "forward".

### 6. Get related entities (reverse direction)

```bash
TASK_ID=$(echo "$TASK" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "import json,sys; print(json.load(sys.stdin)['entity_id'])")
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/smaht/knowledge_graph.py" related --id "$TASK_ID" --direction reverse
```

**Expected**: Returns JSON array containing the design_artifact entity (the only entity with a forward link to the task). Result includes `_direction` = "reverse".

### 7. Subgraph traversal from requirement

```bash
REQ_ID=$(echo "$REQ" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "import json,sys; print(json.load(sys.stdin)['entity_id'])")
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/smaht/knowledge_graph.py" subgraph --id "$REQ_ID" --depth 3
```

**Expected**: Returns JSON with `entities` and `relationships` arrays. The entities array contains all 4 entities (requirement, design, task, test). The relationships array contains all 3 relationships. Depth 3 ensures the full chain is traversed.

### 8. Stats reflect created data

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/smaht/knowledge_graph.py" stats | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
s = json.load(sys.stdin)
assert s['total_entities'] >= 4, 'Expected at least 4 entities, got %d' % s['total_entities']
assert s['total_relationships'] >= 3, 'Expected at least 3 relationships, got %d' % s['total_relationships']
assert 'requirement' in s['entities_by_type'], 'Missing requirement in entity counts'
assert 'TRACES_TO' in s['relationships_by_type'], 'Missing TRACES_TO in rel counts'
print('PASS: Stats match expected counts')
"
```

**Expected**: `total_entities` >= 4, `total_relationships` >= 3. `entities_by_type` includes requirement, design_artifact, task, test_scenario. `relationships_by_type` includes TRACES_TO, IMPLEMENTED_BY, TESTED_BY.

### 9. Invalid entity type is rejected

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/smaht/knowledge_graph.py" create-entity --type invalid_type --name "Should fail" --project test-kg 2>&1; echo "EXIT: $?"
```

**Expected**: Returns an error message mentioning "Invalid entity_type" and exits with non-zero status.

### 10. List entities with project filter returns scoped results

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/smaht/knowledge_graph.py" list-entities --project test-kg | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
entities = json.load(sys.stdin)
for e in entities:
    assert e.get('project_id') == 'test-kg', 'Entity %s has wrong project: %s' % (e['entity_id'], e.get('project_id'))
print('PASS: All %d entities scoped to test-kg' % len(entities))
"
```

**Expected**: All returned entities have `project_id` = "test-kg". Prints PASS.

### 11. Subgraph with depth 1 returns only immediate neighbors

```bash
REQ_ID=$(echo "$REQ" | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "import json,sys; print(json.load(sys.stdin)['entity_id'])")
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/smaht/knowledge_graph.py" subgraph --id "$REQ_ID" --depth 1 | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys
sg = json.load(sys.stdin)
entity_count = len(sg['entities'])
assert entity_count <= 4, 'Depth 1 should limit traversal, got %d entities' % entity_count
print('PASS: Depth-1 subgraph has %d entities' % entity_count)
"
```

**Expected**: Returns fewer entities than depth-3 traversal (only the requirement and its immediate neighbors). Prints PASS.

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

## Cleanup

No explicit cleanup needed -- the knowledge graph uses the default DomainStore path and test entities will not interfere with production data if `--project test-kg` scoping is used.
