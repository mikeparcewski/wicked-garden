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
   /wicked-search:index /tmp/wicked-search-test
   ```

2. Search for "authentication":
   ```
   /wicked-search:search "authentication"
   ```

3. Check index statistics:
   ```
   /wicked-search:stats
   ```

## Expected Outcome

1. Indexer processes both `.py` and `.md` files
2. Cross-references automatically detected:
   - `AuthService` mention in docs → code class
   - `authenticate_user` mention in docs → code method
   - `create_session` mention in docs → code method
3. Search returns unified results from both sources
4. Results show file paths, symbol types, and context

## Success Criteria

- [ ] Index completes without errors
- [ ] Both auth.py and security.md are indexed
- [ ] Cross-references link docs mentions to code definitions
- [ ] Search returns results from both code (AuthService, authenticate_user) and docs (security.md)
- [ ] Stats show correct file counts and symbol counts

## Value Demonstrated

**Problem solved**: Developers waste time manually searching through code files and documentation separately, often missing connections between implementation and specification.

**Why this matters**: In real codebases, understanding a feature requires reading both code and docs. Unified search with automatic cross-references means:
- No context switching between tools
- Discover what code implements which requirements
- Find documentation for unfamiliar code quickly
- Onboard to new codebases faster by seeing code-doc relationships
