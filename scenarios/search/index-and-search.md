---
name: index-and-search
title: Index and Search Across Code and Documentation
description: Index a project with mixed code and docs, then search across everything
type: workflow
difficulty: basic
estimated_minutes: 5
---

# Index and Search Across Code and Documentation

## Setup

Create a test project with Python code and Markdown documentation:

```bash
# Create test directory with mixed content
mkdir -p /tmp/wicked-search-test/src
mkdir -p /tmp/wicked-search-test/docs

# Create a Python file
cat > /tmp/wicked-search-test/src/auth.py << 'EOF'
"""Authentication module."""

class AuthService:
    """Handles user authentication."""

    def authenticate_user(self, username: str, password: str) -> bool:
        """Authenticate a user with credentials."""
        # Implementation
        return True

    def create_session(self, user_id: int) -> str:
        """Create a new session token."""
        return f"session_{user_id}"
EOF

# Create a markdown doc that references the code
cat > /tmp/wicked-search-test/docs/security.md << 'EOF'
# Security Documentation

## Authentication

The `AuthService` class handles all authentication logic.

Users are authenticated via the `authenticate_user` method which validates
credentials against the database.

After successful authentication, `create_session` generates a session token.
EOF
```

## Steps

1. Index the test project:
   ```
   /wicked-garden:search:index /tmp/wicked-search-test
   ```

2. Search for "authentication" across everything:
   ```
   /wicked-garden:search:search "authentication"
   ```

3. Check index statistics:
   ```
   /wicked-garden:search:stats
   ```

## Expected Outcomes

- Indexing completes without errors for both code and documentation files
- Search results include matches from both auth.py and security.md
- Cross-references detected between documentation mentions and code definitions (AuthService, authenticate_user, create_session)
- Results show file locations, symbol types, and surrounding context
- Stats reflect correct counts for indexed files and discovered symbols

## Success Criteria

- [ ] Index completes without errors
- [ ] Both auth.py and security.md appear in the index
- [ ] Search returns results from code (AuthService class, authenticate_user method) and docs (security.md)
- [ ] Cross-references link documentation mentions to code symbol definitions
- [ ] Stats report accurate file and symbol counts

## Value Demonstrated

**Problem solved**: Developers waste time manually searching through code files and documentation separately, often missing connections between implementation and specification.

**Why this matters**: In real codebases, understanding a feature requires reading both code and docs. Unified search with automatic cross-references means:
- No context switching between tools
- Discover what code implements which requirements
- Find documentation for unfamiliar code quickly
- Onboard to new codebases faster by seeing code-doc relationships
