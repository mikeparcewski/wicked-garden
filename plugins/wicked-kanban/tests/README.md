# Wicked Kanban Tests

Pytest test suite for the wicked-kanban plugin.

## Test Organization

```
tests/
├── README.md
└── test_task_blocking_status.py    # Task dependency blocking tests
```

## Running Tests

### Install dependencies

```bash
cd /Users/michael.parcewski/Projects/wicked-garden/plugins/wicked-kanban
uv sync
```

### Run all tests

```bash
pytest
```

### Run with coverage

```bash
pytest --cov=scripts --cov-report=term-missing --cov-report=html
```

### Run specific test file

```bash
pytest tests/test_task_blocking_status.py
```

### Run specific test class

```bash
pytest tests/test_task_blocking_status.py::TestTaskBlockingStatus
```

### Run specific test

```bash
pytest tests/test_task_blocking_status.py::TestTaskBlockingStatus::test_dep_001_task_blocked_by_incomplete_dependency -v
```

### Run tests by marker

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run dependency tests
pytest -m dependency
```

## Test Coverage

Current test coverage for task dependency blocking:

- **DEP-001**: Task blocking status detects incomplete dependencies
- **DEP-002**: Task blocking status ignores completed dependencies
- **DEP-003**: Task blocking status returns empty for no dependencies
- **DEP-004**: Task blocked by multiple incomplete dependencies
- **DEP-005**: Task blocking handles missing dependency tasks (known bug)
- **DEP-006**: Task partially blocked by mixed dependencies
- **DEP-007**: get_task_with_status includes blocking details
- **DEP-008**: Empty depends_on list not blocked
- **DEP-009**: Nonexistent task returns not blocked
- **DEP-010**: Custom complete swimlane unblocks tasks

## Test Structure

All tests follow Arrange-Act-Assert pattern:

```python
def test_example(self, store, project):
    """Test description."""
    # Arrange: Set up test data
    task = store.create_task(...)

    # Act: Execute the operation being tested
    result = store.get_task_blocking_status(...)

    # Assert: Verify the expected behavior
    assert result["is_blocked"] is True
```

## Fixtures

- **temp_data_dir**: Creates isolated temporary directory for test data
- **store**: Fresh KanbanStore instance for each test
- **project**: Test project with default swimlanes

## Coverage Goals

| Type | Target | Current |
|------|--------|---------|
| Unit | 80%+ | TBD |
| Integration | 70%+ | TBD |
| E2E | Critical paths | TBD |
