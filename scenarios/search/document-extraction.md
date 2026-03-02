---
name: document-extraction
title: Extract and Search Office Documents
description: Extract content from PDF, Word, Excel, PowerPoint and link to implementing code
type: feature
difficulty: intermediate
estimated_minutes: 10
---

# Extract and Search Office Documents

## Setup

Create a project with Office-style documents (simulated as text) and implementing code:

```bash
# Create test directory
mkdir -p /tmp/wicked-docs-test/docs
mkdir -p /tmp/wicked-docs-test/src

# Create a text file simulating requirements document
# (In real use, this would be a .docx or .pdf)
cat > /tmp/wicked-docs-test/docs/requirements.txt << 'EOF'
Product Requirements Document

1. Authentication System
   - Users must authenticate via AuthService
   - Session tokens expire after 24 hours
   - Support for OAuth2 providers (GoogleAuth, GitHubAuth)

2. Data Processing Pipeline
   - All data processed through DataPipeline
   - Batch processing via process_batch() method
   - Real-time updates via StreamHandler class
   - Error handling with RetryPolicy

3. Notification System
   - Email notifications via EmailService
   - Push notifications via PushService
   - SMS via TwilioAdapter
EOF

# Create matching implementation
cat > /tmp/wicked-docs-test/src/auth.py << 'EOF'
class AuthService:
    """Main authentication service."""

    def authenticate(self, credentials):
        pass

class GoogleAuth:
    """Google OAuth provider."""
    pass

class GitHubAuth:
    """GitHub OAuth provider."""
    pass
EOF

cat > /tmp/wicked-docs-test/src/pipeline.py << 'EOF'
class DataPipeline:
    """Main data processing pipeline."""

    def process_batch(self, items: list):
        """Process items in batch mode."""
        pass

class StreamHandler:
    """Handle real-time data streams."""
    pass

class RetryPolicy:
    """Retry configuration for failed operations."""
    pass
EOF

cat > /tmp/wicked-docs-test/src/notifications.py << 'EOF'
class EmailService:
    """Send email notifications."""
    pass

class PushService:
    """Send push notifications."""
    pass

class TwilioAdapter:
    """Twilio SMS integration."""
    pass
EOF
```

## Steps

1. Index the project:
   ```
   /wicked-garden:search:index /tmp/wicked-docs-test
   ```

2. Find code that implements "Authentication System":
   ```
   /wicked-garden:search:impl "Authentication System"
   ```

3. Find code for "Data Processing Pipeline":
   ```
   /wicked-garden:search:impl "Data Processing"
   ```

4. Search for what documents mention DataPipeline:
   ```
   /wicked-garden:search:refs DataPipeline
   ```

## Expected Outcome

1. Document parsed into searchable sections:
   - Section 1: Authentication System
   - Section 2: Data Processing Pipeline
   - Section 3: Notification System

2. Cross-references automatically detected:
   - AuthService, GoogleAuth, GitHubAuth → auth.py
   - DataPipeline, StreamHandler, RetryPolicy → pipeline.py
   - EmailService, PushService, TwilioAdapter → notifications.py

3. Bidirectional traceability:
   - From requirement section → implementing classes
   - From code class → which requirements mention it

## Success Criteria

- [ ] Document parsed and indexed successfully
- [ ] All code symbols mentioned in document detected
- [ ] `/impl "Authentication System"` returns auth.py classes
- [ ] `/impl "Data Processing"` returns pipeline.py classes
- [ ] `/refs DataPipeline` returns requirements.txt with context
- [ ] Can trace any requirement section to its implementation

## Value Demonstrated

**Problem solved**: Requirements live in Word/PDF documents disconnected from code. Developers can't easily:
- Find which code implements a requirement
- Verify that all requirements are implemented
- Update docs when code changes

**Why this matters**: Real-world scenarios:
- **Onboarding**: New dev reads "Feature X spec" → instantly sees implementing code
- **Compliance**: Auditor asks "Show me the code for requirement 2.3" → instant answer
- **Refactoring**: Changing EmailService? See which requirements mention it
- **Gap analysis**: Which requirements have no implementing code?

The plugin extracts Office docs (PDF, Word, Excel, PowerPoint) and builds the knowledge graph automatically - no manual linking required.
