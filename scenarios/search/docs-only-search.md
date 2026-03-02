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

## Expected Outcome

1. `/docs password` returns ONLY documentation results:
   - api-spec.md: password field in request body
   - security-policy.md: Password Requirements section
   - security-policy.md: Password Storage section

2. Code files (users.py) are NOT included in results

3. Results show:
   - Relevant document sections with context
   - Section headers (e.g., "Password Requirements")
   - Snippet of surrounding content

4. `/search password` returns both for comparison

## Success Criteria

- [ ] Only documentation files returned (no .py files)
- [ ] Both api-spec.md and security-policy.md found
- [ ] Multiple sections from security-policy.md shown
- [ ] Section headers included for context
- [ ] users.py excluded from docs-only results
- [ ] Results show surrounding context from documents

## Value Demonstrated

**Problem solved**: When learning about system policies, architecture, or requirements, developers need to read specifications without being distracted by implementation details.

**Why this matters**:
- **Understanding requirements**: "What are the password rules?" → see policy doc, not code
- **Compliance review**: Find security policies without implementation noise
- **Architecture decisions**: Read design docs without code references
- **API design**: Review specs before looking at implementation

Docs-only search is essential for:
- New team members learning system design
- Product managers reviewing requirements
- Security auditors checking policies
- Architects reviewing design documents

Filtering out code lets you focus on the "what and why" before diving into the "how".
