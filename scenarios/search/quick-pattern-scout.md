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
mkdir -p /tmp/wicked-scout-test/src/api
mkdir -p /tmp/wicked-scout-test/src/auth
mkdir -p /tmp/wicked-scout-test/src/models
mkdir -p /tmp/wicked-scout-test/tests
mkdir -p /tmp/wicked-scout-test/config

# API endpoint patterns
cat > /tmp/wicked-scout-test/src/api/routes.py << 'EOF'
from flask import Blueprint, request, jsonify

api = Blueprint('api', __name__)

@api.route('/users', methods=['GET'])
def list_users():
    return jsonify(users=[])

@api.route('/users', methods=['POST'])
def create_user():
    data = request.get_json()
    return jsonify(user=data), 201

@api.route('/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    return '', 204
EOF

# Auth patterns
cat > /tmp/wicked-scout-test/src/auth/service.py << 'EOF'
import jwt

class AuthService:
    def authenticate(self, username: str, password: str):
        user = self.find_user(username)
        if not user or not self.verify_password(password, user.hash):
            raise ValueError("Invalid credentials")
        return self.generate_token(user)

    def generate_token(self, user) -> str:
        return jwt.encode({"user_id": user.id}, "secret")

    def verify_token(self, token: str):
        return jwt.decode(token, "secret")

    def logout(self, session_id: str):
        self.invalidate_session(session_id)
EOF

# Database model patterns
cat > /tmp/wicked-scout-test/src/models/user.py << 'EOF'
from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True)
    email = Column(String(120))

class UserRepository:
    def find_by_id(self, user_id: int):
        return self.session.query(User).filter(User.id == user_id).first()

    def save(self, user: User):
        self.session.add(user)
        self.session.commit()
EOF

# Config file
cat > /tmp/wicked-scout-test/config/settings.yml << 'EOF'
database:
  host: localhost
  port: 5432
  name: myapp
auth:
  secret_key: change-me
  token_expiry: 3600
EOF

# Test patterns
cat > /tmp/wicked-scout-test/tests/test_auth.py << 'EOF'
import unittest
from unittest.mock import Mock, patch

class TestAuthService(unittest.TestCase):
    def test_authenticate_success(self):
        service = AuthService()
        token = service.authenticate("admin", "password")
        self.assertIsNotNone(token)

    @patch('auth.service.jwt.encode')
    def test_generate_token(self, mock_encode):
        mock_encode.return_value = "test-token"
        service = AuthService()
        result = service.generate_token(Mock(id=1))
        self.assertEqual(result, "test-token")
EOF
```

## Steps

1. Scout for API endpoint patterns (NO INDEX NEEDED):
   ```
   /wicked-garden:search:scout api --path /tmp/wicked-scout-test
   ```

2. Scout for test patterns:
   ```
   /wicked-garden:search:scout test --path /tmp/wicked-scout-test
   ```

3. Scout for authentication patterns:
   ```
   /wicked-garden:search:scout auth --path /tmp/wicked-scout-test
   ```

4. Scout for database patterns:
   ```
   /wicked-garden:search:scout db --path /tmp/wicked-scout-test
   ```

5. Scout for configuration files:
   ```
   /wicked-garden:search:scout config --path /tmp/wicked-scout-test
   ```

## Expected Outcome

### API Scout:
```
## Scout: api

### Route definitions
src/api/routes.py: 3 routes found
  - GET /users (list_users)
  - POST /users (create_user)
  - DELETE /users/<user_id> (delete_user)

### API directories
src/api/: 1 file

Summary: 3 API patterns across 1 file
```

### Test Scout:
```
## Scout: test

### Test files
tests/test_auth.py: 2 test methods

### Test classes/functions
TestAuthService: 2 tests
  - test_authenticate_success
  - test_generate_token

### Mocks
tests/test_auth.py: @patch decorator, Mock usage

Summary: 2 test patterns across 1 file
```

### Auth Scout:
```
## Scout: auth

### Authentication code
src/auth/service.py: authenticate, generate_token, verify_token, logout
  - jwt usage (encode/decode)
  - session invalidation

### Auth directories
src/auth/: 1 file

Summary: 4 auth patterns across 1 file
```

### DB Scout:
```
## Scout: db

### Models
src/models/user.py: User (SQLAlchemy model)
  - __tablename__ = 'users'
  - 3 columns

### Repository methods
src/models/user.py: find_by_id, save
  - session.query usage
  - session.commit usage

Summary: 5 database patterns across 1 file
```

### Config Scout:
```
## Scout: config

### Configuration files
config/settings.yml: database + auth settings

Summary: 1 config file found
```

## Success Criteria

- [ ] Scout runs WITHOUT requiring index
- [ ] Scout completes in <2 seconds per pattern type
- [ ] All 5 pattern types (api, test, auth, db, config) work correctly
- [ ] File locations included with match details
- [ ] Summary shows aggregate statistics
- [ ] Works on fresh, un-indexed codebases
- [ ] `--path` argument correctly scopes the search directory

## Value Demonstrated

**Problem solved**: Full indexing takes time. Developers need quick answers before deciding if deep analysis is worth it.

**Why this matters**:

**Quick reconnaissance**:
- New codebase: "Does this project have API endpoints?"
- Run: `/wicked-garden:search:scout api`
- See: Route definitions, endpoint patterns
- Time: 2 seconds vs 30+ seconds for full indexing

**Decision making**:
- Question: "Does this project have tests?"
- Run: `/wicked-garden:search:scout test`
- Answer: Instant overview of test coverage
- Decision: Proceed with confidence or add tests

**Security assessment**:
- Before review: `/wicked-garden:search:scout auth`
- See: Where authentication is used, JWT patterns
- Review: Check auth coverage across the codebase

**Data layer overview**:
- Run: `/wicked-garden:search:scout db`
- Discover: ORM models, raw queries, migration patterns
- Action: Understand data layer before making changes

Scout is the "quick grep" to wicked-search's "full database" - use it for reconnaissance before committing to full analysis.
