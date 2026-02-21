# Test Strategy: Unified SQLite Query Layer Migration

**Project**: wicked-search unified data store migration
**Date**: 2026-02-16
**Confidence**: HIGH

## Executive Summary

This strategy addresses the migration from dual data stores (Graph SQLite + JSONL index) to a unified SQLite database with FTS5 search. The migration involves 348,450 JSONL entries and 53,961 graph symbols, with 8 acceptance criteria covering migration integrity, query parity, performance, and rollback safety.

**Highest Risk Areas**:
1. **Data integrity** during JSONL → SQLite migration (all fields preserved)
2. **Query result parity** (unified search must match current output)
3. **Performance regression** under production load (348K entries)
4. **Incremental re-indexing** correctness (UPSERT logic)

---

## Test Environment

### Test Data Sets

| Dataset | Purpose | Size | Location |
|---------|---------|------|----------|
| **Ohio codebase** | Production scale | 348K JSONL + 44K graph | Real deployment data |
| **wicked-garden** | Small validation | 906 JSONL + minimal graph | This repository |
| **Synthetic test project** | Edge cases | 50-100 files | Create as needed |

### Test Database States

1. **Clean slate**: Empty SQLite, no JSONL
2. **JSONL-only**: Legacy state (current production)
3. **SQLite-only**: Post-migration state
4. **Hybrid**: Both stores present (transition state)
5. **Corrupted**: Incomplete migration (rollback testing)

---

## Test Scenarios

### Category 1: Migration Data Integrity (AC-3)

**Priority: P0** — Data loss is catastrophic

#### S1.1: Full JSONL Migration with Field Preservation
- **Input**: 348K JSONL entries with all fields populated
- **Expected**: Every entry in SQLite with id, name, type, file, line_start, line_end, domain, calls, imports, bases, imported_names, dependents, metadata, content preserved
- **Validation**:
  - Row count match: `SELECT COUNT(*) FROM symbols` = 348,450
  - Sample 1000 random entries, compare JSONL vs SQLite field-by-field
  - Check JSON fields (calls, imports, metadata) parse correctly after round-trip
- **Test Data**: Full Ohio JSONL index
- **Automation**: Python script comparing JSONL → SQLite → verify checksums
- **Exit Criteria**: 100% field preservation, zero data loss

#### S1.2: Relationship Preservation (calls, imports, bases)
- **Input**: JSONL entries with complex relationship arrays (e.g., 50+ calls, 20+ imports)
- **Expected**: All relationships migrated to normalized tables (symbol_calls, symbol_imports, symbol_bases)
- **Validation**:
  - For 100 symbols with most calls: verify call count matches
  - For 100 symbols with most imports: verify import count matches
  - Join queries: `SELECT * FROM symbols JOIN symbol_calls` returns expected rows
- **Test Data**: Identify high-fan-out nodes in Ohio codebase
- **Automation**: SQL query validation script
- **Exit Criteria**: Relationship counts match, no orphaned entries

#### S1.3: Metadata and Content Field Integrity
- **Input**: JSONL entries with large content fields (docstrings, doc sections)
- **Expected**: TEXT blobs preserved, no truncation or encoding issues
- **Validation**:
  - Sample 100 largest content fields, compare byte-for-byte
  - Check UTF-8 encoding survives round-trip
  - Verify metadata JSON nesting (3+ levels deep)
- **Test Data**: Doc section nodes, entities with complex annotations
- **Automation**: Binary comparison script
- **Exit Criteria**: Zero content corruption, metadata structure intact

#### S1.4: Atomic Migration with Rollback
- **Input**: Simulate crash at 50% migration progress
- **Expected**: Temp DB discarded, original JSONL unchanged
- **Validation**:
  - Kill migration script mid-process
  - Check for `.jsonl` (original) and `.db.tmp` (temp)
  - Verify no `.db` (final) present, no partial data
- **Test Data**: Ohio codebase (30s+ migration time)
- **Automation**: Manual kill + filesystem check
- **Exit Criteria**: Original JSONL intact, no corrupt SQLite artifacts

---

### Category 2: Query Result Parity (AC-2, AC-5)

**Priority: P0** — Regression breaks user workflows

#### S2.1: Unified Code Search — Exact Match
- **Input**: Query "CustomerEntity" (known class in Ohio)
- **Expected**:
  - JSONL mode: Returns CustomerEntity class + method results
  - SQLite mode: Same results, same order (after dedup + rank)
- **Validation**: JSON diff of result arrays (id, name, type, file, line_start)
- **Test Data**: 10 queries with known exact matches
- **Automation**: Pytest with result comparison
- **Exit Criteria**: 100% match on exact queries

#### S2.2: Unified Code Search — Fuzzy Match
- **Input**: Query "custmr" (typo for "customer")
- **Expected**:
  - JSONL mode: rapidfuzz returns top 10 closest matches
  - SQLite mode: FTS5 rank with typo tolerance returns similar set
- **Validation**:
  - Top 5 results overlap ≥80%
  - Known correct result appears in both top 10
- **Test Data**: 20 typo queries, 20 partial word queries
- **Automation**: Pytest with fuzzy match scoring
- **Exit Criteria**: ≥80% top-5 overlap, no major result omissions

#### S2.3: Cross-Reference Fan-Out with Deduplication
- **Input**: Query symbol present in both JSONL (as function) and Graph (as entity field)
- **Expected**: Single result with `provenance: ["jsonl", "graph"]`, not duplicate entries
- **Validation**:
  - Check `provenance` field exists and correct
  - Verify result count = 1 for known duplicates
- **Test Data**: Manually identified duplicate symbols across stores
- **Automation**: Pytest checking dedup logic
- **Exit Criteria**: Zero duplicate results in unified query

#### S2.4: Category Filtering Integration (AC-1)
- **Input**: `api.py categories --category backend`
- **Expected**: Returns only backend symbols (entities, services, controllers)
- **Validation**:
  - All returned symbols have `layer = 'backend'`
  - Known frontend symbols (JSP pages, components) excluded
- **Test Data**: Ohio codebase with mixed layers
- **Automation**: SQL query with DISTINCT layer check
- **Exit Criteria**: 100% correct category filtering, no misclassified symbols

---

### Category 3: Performance & Scalability (AC-7)

**Priority: P1** — Performance regression impacts UX

#### S3.1: Single Query Performance — Cold Cache
- **Input**: FTS5 search query on 348K entries, fresh DB (no OS cache)
- **Expected**: Query completes in <500ms
- **Validation**:
  - Run on SSD, clear OS cache: `sync && echo 3 > /proc/sys/vm/drop_caches` (Linux) or `purge` (macOS)
  - Measure 10 queries, report p50, p95, p99
- **Test Data**: 50 representative queries (exact, fuzzy, filtered)
- **Automation**: Python perf harness with timer
- **Exit Criteria**: p95 <500ms on SSD, p99 <750ms

#### S3.2: Cross-Reference Query Performance
- **Input**: Traverse references from high-fan-out symbol (e.g., base entity with 100+ dependents)
- **Expected**: Query completes in <2s (cold cache)
- **Validation**:
  - Measure join queries: `symbols → refs → symbols`
  - Check index usage: `EXPLAIN QUERY PLAN`
- **Test Data**: Top 20 highest fan-out symbols in Ohio
- **Automation**: SQL EXPLAIN + timer
- **Exit Criteria**: p95 <2s, all queries use indexes

#### S3.3: Bulk Query Performance — Category Listing
- **Input**: `api.py list symbols --limit 10000` (10K results)
- **Expected**: Returns in <1s
- **Validation**:
  - Test with offset pagination (offset=0, 5000, 10000)
  - Verify no full table scan
- **Test Data**: Full Ohio dataset
- **Automation**: Bash script with `time` command
- **Exit Criteria**: Pagination performs consistently, no linear degradation

#### S3.4: Migration Performance — Indexing Speed
- **Input**: Index Ohio codebase from scratch
- **Expected**: Complete in <5 minutes on modern hardware (SSD, 4 CPU cores)
- **Validation**:
  - Time full index build: `time python unified_search.py index`
  - Parallel indexer saturates CPU
- **Test Data**: Ohio 348K entries
- **Automation**: Bash script with time measurement
- **Exit Criteria**: <5min total, CPU utilization >70%

---

### Category 4: Incremental Re-Indexing (AC-6)

**Priority: P1** — Stale data breaks accuracy

#### S4.1: UPSERT Changed Files Only
- **Input**: Modify 5 files in wicked-garden, re-index
- **Expected**: Only 5 files re-parsed, SQLite updated via UPSERT
- **Validation**:
  - Check updater.py logs: "Updated 5 files"
  - Verify unchanged files not re-parsed (no tree-sitter calls)
  - Confirm mtime-based staleness detection
- **Test Data**: wicked-garden (906 entries)
- **Automation**: Integration test with file touch + re-index
- **Exit Criteria**: Only changed files processed, <1s re-index for 5 files

#### S4.2: Deleted File Cleanup
- **Input**: Delete 3 files, re-index
- **Expected**: Symbols from deleted files removed from SQLite
- **Validation**:
  - Before delete: 3 files present in `SELECT DISTINCT file FROM symbols`
  - After re-index: 3 files absent, symbol count reduced
- **Test Data**: Synthetic test project with known files
- **Automation**: Python test with temp directory
- **Exit Criteria**: Orphaned symbols cleaned up, no stale entries

#### S4.3: Renamed File Tracking
- **Input**: Rename file from `old.py` to `new.py`, update imports, re-index
- **Expected**: Symbols migrated to new file path, references updated
- **Validation**:
  - Old file symbols deleted
  - New file symbols created with same IDs (if qualified name unchanged)
  - Cross-references still resolve
- **Test Data**: Synthetic test project
- **Automation**: Python test with git mv simulation
- **Exit Criteria**: Renamed symbols tracked correctly, no broken references

---

### Category 5: Filtering & Indexes (AC-4)

**Priority: P1** — Poor filtering breaks advanced queries

#### S5.1: File Path Filtering with LIKE
- **Input**: `SELECT * FROM symbols WHERE file LIKE '%entity%'`
- **Expected**: Returns only entity files, uses index
- **Validation**:
  - EXPLAIN QUERY PLAN shows index usage
  - Result count matches glob `**/*entity*`
- **Test Data**: Ohio codebase with varied directory structure
- **Automation**: SQL query + EXPLAIN check
- **Exit Criteria**: Index used, no full scan, <100ms query time

#### S5.2: Type Filtering Performance
- **Input**: `SELECT * FROM symbols WHERE type = 'entity_field' LIMIT 1000`
- **Expected**: Uses idx_symbols_type, returns <50ms
- **Validation**: EXPLAIN shows index scan, timer confirms speed
- **Test Data**: Ohio codebase (1000+ entity fields)
- **Automation**: SQL query + timer
- **Exit Criteria**: Index used, <50ms for 1000 results

#### S5.3: Layer-Based Filtering (Materialized Column)
- **Input**: `SELECT * FROM symbols WHERE layer = 'frontend'`
- **Expected**: Returns JSP pages, HTML components only
- **Validation**:
  - Verify layer computed correctly during migration
  - All results match layer definition
- **Test Data**: Ohio codebase with JSP + HTML
- **Automation**: SQL query validation
- **Exit Criteria**: Layer column accurate, filtering works correctly

---

### Category 6: Backward Compatibility (AC-5)

**Priority: P1** — Breaking CLI breaks users

#### S6.1: Command Output Shape Unchanged
- **Input**: `python api.py search symbols --query "Customer" --limit 5`
- **Expected**: JSON output has same fields (meta, results, provenance if unified)
- **Validation**:
  - Compare JSONL-mode output vs SQLite-mode output
  - Check keys: `id`, `name`, `type`, `file`, `line_start`, etc.
- **Test Data**: 20 representative queries
- **Automation**: Pytest with JSON schema validation
- **Exit Criteria**: CLI output schema unchanged, only internal implementation differs

#### S6.2: API Error Handling Compatibility
- **Input**: Query non-existent symbol ID
- **Expected**: Returns `{"error": "Symbol not found", "code": "NOT_FOUND"}`
- **Validation**: Same error format for JSONL and SQLite modes
- **Test Data**: Edge cases (empty DB, invalid ID, malformed query)
- **Automation**: Pytest with error code checks
- **Exit Criteria**: Error contracts unchanged

---

### Category 7: Rollback & Config-Driven Behavior (AC-8)

**Priority: P2** — Safety net for production issues

#### S7.1: Config Flag Rollback to JSONL-Only
- **Input**: Set `USE_JSONL_ONLY=true` env var or config flag
- **Expected**: All queries route to JSONL searcher, SQLite ignored
- **Validation**:
  - Queries succeed even if SQLite DB corrupted
  - Performance matches JSONL-only baseline
- **Test Data**: Ohio codebase in both states
- **Automation**: Integration test toggling config flag
- **Exit Criteria**: Rollback successful, zero downtime

#### S7.2: Partial Migration Recovery
- **Input**: Migration fails at 70%, temp DB present
- **Expected**: Next migration attempt resumes or restarts cleanly
- **Validation**:
  - Delete temp DB, restart migration → completes
  - OR: Resume from checkpoint (if implemented)
- **Test Data**: Synthetic crash scenario
- **Automation**: Manual test with kill signal
- **Exit Criteria**: Migration can recover or restart safely

---

### Category 8: Edge Cases & Stress Tests

**Priority: P2-P3** — Uncommon but important scenarios

#### S8.1: Empty Database Initialization
- **Input**: Run queries on empty SQLite (no symbols)
- **Expected**: Returns `{"meta": {"total": 0}, "results": []}`
- **Validation**: No crashes, proper empty state handling
- **Test Data**: Fresh DB
- **Automation**: Pytest
- **Exit Criteria**: Graceful empty state handling

#### S8.2: UTF-8 and Unicode Symbol Names
- **Input**: Symbols with emoji, Chinese characters, special chars
- **Expected**: All characters preserved in SQLite, searchable
- **Validation**: Round-trip test: insert → query → compare
- **Test Data**: Synthetic test file with unicode
- **Automation**: Python test with unicode strings
- **Exit Criteria**: Full unicode support, no encoding errors

#### S8.3: Large Relationship Arrays (100+ calls)
- **Input**: Symbol with 150 outgoing calls (e.g., dispatcher method)
- **Expected**: All calls stored in symbol_calls table, joinable
- **Validation**:
  - `SELECT COUNT(*) FROM symbol_calls WHERE source_id = ?` returns 150
  - Query performance <100ms
- **Test Data**: Synthetic or Ohio dispatcher method
- **Automation**: SQL query test
- **Exit Criteria**: Large arrays handled correctly

#### S8.4: Concurrent Query Load
- **Input**: 50 simultaneous search queries (simulated users)
- **Expected**: All queries succeed, no locking issues, p95 <1s
- **Validation**:
  - Use SQLite WAL mode for concurrency
  - Run `pytest-xdist` with 50 workers
- **Test Data**: Ohio codebase
- **Automation**: Load test script
- **Exit Criteria**: No query failures, acceptable latency under load

---

## Test Data Requirements

### Required Test Datasets

1. **Ohio Production Snapshot**
   - Full JSONL index (348,450 entries)
   - Full graph SQLite (44,290 symbols + 9,671 refs)
   - Representative file types: Java entities, JSP, HTML, configs
   - High-fan-out symbols (100+ dependents)

2. **wicked-garden Codebase**
   - Small validation set (906 entries)
   - Real-world Python codebase
   - Existing test scenarios in `scenarios/`

3. **Synthetic Edge Case Project**
   - Unicode symbol names (emoji, CJK)
   - Deeply nested directories (10+ levels)
   - Large files (10K+ lines)
   - High relationship fan-out (150+ calls per symbol)
   - Empty files, binary files (should be skipped)

4. **Corrupted State Fixtures**
   - Partial JSONL (truncated mid-line)
   - Incomplete SQLite migration (temp DB)
   - Missing indexes (test fallback behavior)

---

## Automation Strategy

### Automated Tests (P0-P1 scenarios)

**Framework**: pytest with custom fixtures

```python
# tests/test_migration.py
@pytest.fixture
def ohio_jsonl():
    """Load Ohio JSONL fixture."""
    return load_jsonl("fixtures/ohio-348k.jsonl")

@pytest.fixture
def migrated_db(ohio_jsonl, tmp_path):
    """Run migration and return SQLite path."""
    db_path = tmp_path / "test.db"
    migrate_jsonl_to_sqlite(ohio_jsonl, db_path)
    return db_path

def test_field_preservation(ohio_jsonl, migrated_db):
    """S1.1: Full JSONL migration field preservation."""
    conn = sqlite3.connect(migrated_db)
    cursor = conn.cursor()

    # Sample 1000 random entries
    sample = random.sample(ohio_jsonl, 1000)

    for entry in sample:
        row = cursor.execute(
            "SELECT * FROM symbols WHERE id = ?",
            (entry['id'],)
        ).fetchone()

        assert row is not None, f"Missing entry: {entry['id']}"
        assert row['name'] == entry['name']
        assert row['type'] == entry['type']
        # ... all fields
```

**Test Suites**:
- `test_migration.py` — S1.* scenarios
- `test_query_parity.py` — S2.* scenarios
- `test_performance.py` — S3.* scenarios (marked `@pytest.mark.slow`)
- `test_incremental.py` — S4.* scenarios
- `test_filtering.py` — S5.* scenarios
- `test_compatibility.py` — S6.* scenarios
- `test_rollback.py` — S7.* scenarios
- `test_edge_cases.py` — S8.* scenarios

### Manual Tests (P2-P3 scenarios)

- **S1.4**: Atomic migration rollback (kill script mid-process)
- **S7.2**: Partial migration recovery (filesystem inspection)
- **S8.4**: Concurrent load test (visual inspection, monitoring)

### CI/CD Integration

```yaml
# .github/workflows/wicked-search-tests.yml
name: wicked-search SQLite Migration Tests

on: [pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          cd plugins/wicked-search/scripts
          pip install pytest pytest-xdist
      - name: Run fast tests
        run: pytest tests/ -m "not slow"
      - name: Run performance tests (on main only)
        if: github.ref == 'refs/heads/main'
        run: pytest tests/ -m slow --durations=10
```

---

## Success Metrics

### Acceptance Gates

| Metric | Target | Critical? |
|--------|--------|-----------|
| Data integrity | 100% field preservation | ✅ BLOCKER |
| Query parity (exact) | 100% match | ✅ BLOCKER |
| Query parity (fuzzy) | ≥80% top-5 overlap | ✅ BLOCKER |
| Single query perf | p95 <500ms | ⚠️ MAJOR |
| Cross-ref query perf | p95 <2s | ⚠️ MAJOR |
| Incremental re-index | Only changed files | ⚠️ MAJOR |
| Rollback success | Zero downtime | ⚠️ MAJOR |
| CLI compatibility | Output schema unchanged | ✅ BLOCKER |

### Test Coverage Requirements

- **Unit tests**: 80%+ coverage of new modules (query_builder.py, migration.py)
- **Integration tests**: All 8 acceptance criteria covered
- **Performance tests**: Baseline established, regression detection
- **Edge case tests**: At least 15 scenarios (S8.*)

---

## Risk Mitigation

### High-Risk Areas

1. **JSONL → SQLite Migration**
   - **Risk**: Data loss or corruption
   - **Mitigation**: Atomic writes (temp DB), checksums, rollback flag
   - **Tests**: S1.1, S1.2, S1.3, S1.4

2. **FTS5 Search Accuracy**
   - **Risk**: FTS5 ranking differs from rapidfuzz, user confusion
   - **Mitigation**: Parallel testing, tunable ranking weights, fallback to JSONL
   - **Tests**: S2.2, S6.1

3. **Performance Regression**
   - **Risk**: 348K entries cause query slowdown
   - **Mitigation**: Proper indexes, EXPLAIN analysis, benchmarking
   - **Tests**: S3.1, S3.2, S3.3

4. **Incremental Update Bugs**
   - **Risk**: Stale data persists after file changes
   - **Mitigation**: mtime tracking, comprehensive integration tests
   - **Tests**: S4.1, S4.2, S4.3

### Rollback Plan

If migration fails in production:
1. Set `USE_JSONL_ONLY=true` config flag (S7.1)
2. All queries route to legacy JSONL searcher
3. Investigate SQLite issues offline
4. Re-attempt migration with fixes

---

## Test Execution Plan

### Phase 1: Pre-Implementation (Week 1)
- [ ] Set up test fixtures (Ohio JSONL, synthetic datasets)
- [ ] Write pytest scaffolding (fixtures, helpers)
- [ ] Baseline performance measurements (current JSONL-only)

### Phase 2: Migration Testing (Week 2)
- [ ] Implement S1.* tests (migration integrity)
- [ ] Run full Ohio migration, validate checksums
- [ ] Test rollback scenarios (S1.4, S7.*)

### Phase 3: Query Parity Testing (Week 3)
- [ ] Implement S2.* tests (exact/fuzzy/cross-ref)
- [ ] Compare 1000 queries: JSONL vs SQLite
- [ ] Fix ranking discrepancies

### Phase 4: Performance & Scale (Week 4)
- [ ] Implement S3.* tests (perf benchmarks)
- [ ] Profile slow queries with EXPLAIN
- [ ] Add missing indexes, optimize

### Phase 5: Integration & Edge Cases (Week 5)
- [ ] Implement S4.*, S5.*, S6.*, S8.* tests
- [ ] Manual testing (concurrent load, unicode)
- [ ] CI/CD integration

### Phase 6: Production Validation (Week 6)
- [ ] Deploy with rollback flag enabled
- [ ] Canary testing (10% traffic to SQLite)
- [ ] Monitor error rates, latency
- [ ] Full cutover if metrics green

---

## E2E Scenario Coverage

### Existing wicked-search Scenarios

The following scenarios in `plugins/wicked-search/scenarios/` provide E2E coverage:

| Scenario | Relevance to Migration | Risk Coverage |
|----------|------------------------|---------------|
| **index-and-search.md** | Tests full index → query flow | AC-1, AC-2, AC-5 |
| **incremental-indexing.md** | Tests UPSERT logic | AC-6 |
| **code-only-search.md** | Tests domain filtering | AC-2, AC-4 |
| **docs-only-search.md** | Tests domain filtering | AC-2, AC-4 |
| **cross-reference-detection.md** | Tests relationship joins | AC-2, AC-4 |
| **blast-radius-analysis.md** | Tests transitive refs | AC-4, AC-7 |
| **find-implementations.md** | Tests cross-domain refs | AC-2, AC-4 |

**Coverage Gaps**:
- No scenario for migration rollback (AC-8)
- No scenario for performance benchmarking (AC-7)
- No scenario for JSONL → SQLite migration validation (AC-3)

**Recommendation**: Add 3 new scenarios:
1. `unified-query-migration.md` — Full migration + validation (AC-3, AC-8)
2. `query-performance-benchmark.md` — Perf testing (AC-7)
3. `incremental-upsert-validation.md` — UPSERT correctness (AC-6)

---

## Recommendation

**Prioritize in this order**:

1. **P0: Data Integrity (S1.*)** — Implement migration with atomic writes, checksums, field validation. This is the foundation.

2. **P0: Query Parity (S2.*)** — Prove SQLite results match JSONL. Without this, users lose trust.

3. **P1: Incremental Re-Index (S4.*)** — Stale data breaks accuracy. Must work correctly.

4. **P1: Performance (S3.*)** — Acceptable speed is non-negotiable for 348K entries.

5. **P2: Rollback Safety (S7.*)** — Insurance policy for production issues.

6. **P3: Edge Cases (S8.*)** — Handle uncommon scenarios gracefully.

**Test-First Approach**: Write tests S1.1, S2.1, S4.1, S3.1 BEFORE implementing migration.py and query_builder.py. This ensures correctness from the start.

**Performance Baseline**: Before any code changes, run S3.* tests on current JSONL-only system to establish baseline. This quantifies any regression.

**Continuous Validation**: On every PR, run P0 tests (S1.*, S2.*). Weekly, run full suite including performance tests.
