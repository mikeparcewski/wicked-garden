---
name: quick-pattern-scout
title: Quick Pattern Reconnaissance
description: Scout common code patterns without building full index
type: feature
difficulty: basic
estimated_minutes: 5
---

# Quick Pattern Reconnaissance

## Setup

Create a sample codebase with various patterns:

```bash
# Create test directory
mkdir -p /tmp/wicked-scout-test/src
mkdir -p /tmp/wicked-scout-test/tests

# Error handling patterns
cat > /tmp/wicked-scout-test/src/error_handler.py << 'EOF'
def process_data(data):
    try:
        validate(data)
        return transform(data)
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return None
EOF

# Logging patterns
cat > /tmp/wicked-scout-test/src/service.py << 'EOF'
import logging

logger = logging.getLogger(__name__)

class DataService:
    def fetch_data(self, id: int):
        logger.info(f"Fetching data for id: {id}")
        try:
            result = self.query(id)
            logger.debug(f"Found result: {result}")
            return result
        except Exception as e:
            logger.error(f"Failed to fetch data: {e}")
            raise
EOF

# Validation patterns
cat > /tmp/wicked-scout-test/src/validators.py << 'EOF'
from pydantic import BaseModel, validator

class UserInput(BaseModel):
    username: str
    email: str
    age: int

    @validator('age')
    def check_age(cls, v):
        if v < 0 or v > 150:
            raise ValueError('Invalid age')
        return v

def validate_email(email: str) -> bool:
    if '@' not in email:
        raise ValueError('Invalid email')
    return True
EOF

# Test patterns
cat > /tmp/wicked-scout-test/tests/test_service.py << 'EOF'
import unittest
from unittest.mock import Mock, patch

class TestDataService(unittest.TestCase):
    def test_fetch_data(self):
        service = DataService()
        result = service.fetch_data(1)
        self.assertIsNotNone(result)

    @patch('service.query')
    def test_fetch_with_mock(self, mock_query):
        mock_query.return_value = {'id': 1}
        service = DataService()
        result = service.fetch_data(1)
        self.assertEqual(result['id'], 1)
EOF
```

## Steps

1. Scout for error handling patterns (NO INDEX NEEDED):
   ```
   /wicked-search:scout error-handling
   ```

2. Scout for logging patterns:
   ```
   /wicked-search:scout logging
   ```

3. Scout for validation patterns:
   ```
   /wicked-search:scout validation
   ```

4. Scout for test patterns:
   ```
   /wicked-search:scout test-patterns
   ```

5. Compare speed with indexed search (optional):
   ```
   /wicked-search:index /tmp/wicked-scout-test
   /wicked-search:code "error handling"
   ```

## Expected Outcome

### Error Handling Scout:
```
## Scout: error-handling

### try/catch blocks
src/error_handler.py:3 (2 matches)
src/service.py:7 (1 match)

### throw statements
src/error_handler.py:7 (2 matches)
src/service.py:14 (1 match)

### Error types
ValueError: 3 occurrences
Exception: 2 occurrences

Summary: 8 error handling patterns across 2 files
```

### Logging Scout:
```
## Scout: logging

### Logger imports
src/service.py:1 (1 match)

### Logger calls
src/service.py:7 (logger.info)
src/service.py:10 (logger.debug)
src/service.py:13 (logger.error)

Summary: 4 logging patterns across 1 file
```

### Validation Scout:
```
## Scout: validation

### Pydantic models
src/validators.py:3 (1 model)

### Validators/decorators
src/validators.py:9 (@validator)

### Type checks
src/validators.py:11 (age validation)
src/validators.py:17 (email validation)

Summary: 4 validation patterns across 1 file
```

### Test Patterns Scout:
```
## Scout: test-patterns

### Test classes/functions
tests/test_service.py:5 (TestDataService)

### Test methods
tests/test_service.py:6 (test_fetch_data)
tests/test_service.py:11 (test_fetch_with_mock)

### Assertions
tests/test_service.py:9 (assertIsNotNone)
tests/test_service.py:16 (assertEqual)

### Mocks
tests/test_service.py:11 (@patch decorator)
tests/test_service.py:12 (mock_query)

Summary: 7 test patterns across 1 file
```

## Success Criteria

- [ ] Scout runs WITHOUT requiring index
- [ ] Scout completes in <2 seconds
- [ ] All pattern types detected correctly
- [ ] File locations included with counts
- [ ] Summary shows aggregate statistics
- [ ] Works on fresh, un-indexed codebases
- [ ] Faster than building full index + searching

## Value Demonstrated

**Problem solved**: Full indexing takes time. Developers need quick answers before deciding if deep analysis is worth it.

**Why this matters**:

**Quick reconnaissance**:
- New codebase: "What's the error handling like here?"
- Run: `/scout error-handling`
- See: Try/catch usage, error types, patterns
- Time: 2 seconds vs 30+ seconds for full indexing

**Decision making**:
- Question: "Does this project have tests?"
- Run: `/scout test-patterns`
- Answer: Instant overview of test coverage
- Decision: Proceed with confidence or add tests

**Code review prep**:
- Before review: `/scout logging`
- See: Where logging is used (or missing)
- Review: Check if critical paths have logging

**Pattern consistency**:
- Run: `/scout validation`
- Discover: Mix of pydantic, manual checks, type guards
- Action: Standardize validation approach

**Real-world scenarios**:

1. **Evaluating a project**:
   - Fork unknown repo
   - Run 6 scout commands in 12 seconds
   - Get: Instant overview of code patterns
   - vs Full index: 2+ minutes on large codebases

2. **Debugging without context**:
   - Bug report mentions error handling
   - Run: `/scout error-handling`
   - Find: All error handling patterns instantly
   - Focus: Review relevant error handlers

3. **Architecture assessment**:
   - Scout multiple patterns quickly
   - See: How team structures code
   - Learn: Project conventions in seconds

4. **Pair with full search**:
   - Scout first: Get quick counts
   - If interesting: Build full index
   - Decision: Scout = filter, Index = deep dive

Scout is the "quick grep" to wicked-search's "full database" - use it for reconnaissance before committing to full analysis.
