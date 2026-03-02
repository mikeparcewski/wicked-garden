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

1. Scout for API endpoint patterns (no index needed):
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

## Expected Outcomes

- All scout commands run without requiring a pre-built index
- API scout finds route definitions in routes.py (GET, POST, DELETE endpoints)
- Test scout finds test classes and methods in test_auth.py, including mock usage
- Auth scout finds authentication-related code in service.py (authenticate, token generation/verification)
- DB scout finds SQLAlchemy models and repository methods in user.py
- Config scout finds settings.yml with database and auth configuration
- Each scout reports file locations alongside discovered patterns
- `--path` argument correctly scopes searches to the specified directory

## Success Criteria

- [ ] Scout runs without requiring an index
- [ ] All 5 pattern types (api, test, auth, db, config) produce results
- [ ] API scout finds the 3 route definitions in routes.py
- [ ] Test scout finds test classes and test methods
- [ ] Auth scout finds authentication code (JWT usage, login/logout)
- [ ] DB scout finds ORM models and repository patterns
- [ ] Config scout finds configuration files
- [ ] File locations included with each result
- [ ] `--path` argument correctly scopes the search directory

## Value Demonstrated

**Problem solved**: Full indexing takes time. Developers need quick answers before deciding if deep analysis is worth it.

**Why this matters**:
- **Quick reconnaissance**: "Does this project have API endpoints?" answered in seconds
- **Decision making**: "Does this project have tests?" gives instant coverage overview
- **Security assessment**: Find where authentication is handled before a full review
- **Data layer overview**: Discover ORM models and query patterns before making changes
