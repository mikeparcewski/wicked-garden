---
name: docs-only-search
title: Search Documentation Only
description: Filter search to only documentation, excluding code
type: feature
difficulty: basic
estimated_minutes: 5
---

# Search Documentation Only

## Setup

Create documentation and code that both mention "password":

```bash
# Create test directory
mkdir -p /tmp/wicked-docsonly-test/docs
mkdir -p /tmp/wicked-docsonly-test/src

# Create multiple doc files
cat > /tmp/wicked-docsonly-test/docs/api-spec.md << 'EOF'
# API Specification

## Endpoints

### POST /api/users
Create a new user account.

Request body:
- username (required)
- email (required)
- password (required)

Response: 201 Created
EOF

cat > /tmp/wicked-docsonly-test/docs/security-policy.md << 'EOF'
# Security Policy

## Password Requirements

- Minimum 8 characters
- Must include uppercase and lowercase
- Must include at least one number
- No common dictionary words

## Password Storage

Passwords are hashed using bcrypt with cost factor 12.
Never store plaintext passwords.

## Session Management

Sessions expire after 24 hours of inactivity.
EOF

# Create code that shouldn't appear in docs search
cat > /tmp/wicked-docsonly-test/src/users.py << 'EOF'
def create_user(username: str, email: str, password: str):
    """Create user - password must meet requirements."""
    pass

def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    pass
EOF
```

## Steps

1. Index the project:
   ```
   /wicked-garden:search:index /tmp/wicked-docsonly-test
   ```

2. Search docs only for "password":
   ```
   /wicked-garden:search:docs password
   ```

3. Compare with unified search:
   ```
   /wicked-garden:search:search password
   ```

## Expected Outcomes

- Docs-only search returns results exclusively from documentation files (.md), not code (.py)
- Both api-spec.md and security-policy.md are found
- Multiple relevant sections from security-policy.md appear (Password Requirements, Password Storage)
- Section headers included for navigational context
- Unified search returns both code and doc results, confirming the filter works

## Success Criteria

- [ ] Docs-only search excludes code files (users.py not in results)
- [ ] Both api-spec.md and security-policy.md found
- [ ] Multiple sections from security-policy.md returned (requirements and storage)
- [ ] Section headers visible in results for context
- [ ] Unified search returns both code and doc results for comparison

## Value Demonstrated

**Problem solved**: When learning about system policies, architecture, or requirements, developers need to read specifications without being distracted by implementation details.

**Why this matters**:
- **Understanding requirements**: "What are the password rules?" returns policy docs, not code
- **Compliance review**: Find security policies without implementation noise
- **Architecture decisions**: Read design docs without code references
- **API design**: Review specs before looking at implementation
