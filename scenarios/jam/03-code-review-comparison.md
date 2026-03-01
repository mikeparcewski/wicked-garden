---
name: code-review-comparison
title: Multi-Model Code Review Comparison
description: Tests using different AI models to review the same code and compare their findings
type: feature
difficulty: intermediate
estimated_minutes: 15
---

# Multi-Model Code Review Comparison

Tests the ability to get code reviews from multiple AI models (Claude, Gemini, Codex, OpenCode) and compare their findings for quality assurance.

## Setup

Create a realistic code sample with intentional issues:

```bash
mkdir -p /tmp/code-review-test
cd /tmp/code-review-test

cat > user_service.py <<'EOF'
import requests
import json

class UserService:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.example.com"

    def get_user(self, user_id):
        # Fetch user data from API
        url = f"{self.base_url}/users/{user_id}"
        headers = {"Authorization": f"Bearer {self.api_key}"}

        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            return json.loads(response.text)
        else:
            return None

    def update_user(self, user_id, data):
        url = f"{self.base_url}/users/{user_id}"
        headers = {"Authorization": f"Bearer {self.api_key}"}

        response = requests.put(url, headers=headers, data=json.dumps(data))

        if response.status_code == 200:
            return True
        return False

    def delete_user(self, user_id):
        # Delete user - no confirmation needed
        url = f"{self.base_url}/users/{user_id}"
        headers = {"Authorization": f"Bearer {self.api_key}"}

        requests.delete(url, headers=headers)
        return True

    def batch_update(self, user_ids, data):
        results = []
        for uid in user_ids:
            results.append(self.update_user(uid, data))
        return results
EOF
```

## Steps

1. **Get Claude's code review**

   In Claude Code conversation:
   ```
   Review user_service.py for:
   1. Error handling issues
   2. Security concerns
   3. Performance problems
   4. API best practices

   Be specific about line numbers and provide actionable fixes.
   ```

   Expected: Claude identifies issues like:
   - Missing timeout in requests
   - No retry logic
   - Silent failure in delete_user
   - Missing Content-Type headers
   - Synchronous batch operations

2. **Get Gemini's code review (if available)**

   ```bash
   cat user_service.py | gemini "Review this code for:
   1. Error handling issues
   2. Security concerns
   3. Performance problems
   4. API best practices

   Be specific about line numbers and provide actionable fixes."
   ```

   Expected: Gemini provides analysis, may identify different or overlapping issues.

3. **Get Codex's code review (if available)**

   ```bash
   cat user_service.py | codex exec "Review this code for:
   1. Error handling issues
   2. Security concerns
   3. Performance problems
   4. API best practices

   Be specific about line numbers and provide actionable fixes."
   ```

   Expected: Codex provides code-focused analysis.

4. **Get OpenCode's code review (if available)**

   ```bash
   opencode run "Review this code for:
   1. Error handling issues
   2. Security concerns
   3. Performance problems
   4. API best practices

   Be specific about line numbers and provide actionable fixes." -f user_service.py -m anthropic/claude-3-5-sonnet
   ```

   Expected: OpenCode provides analysis.

5. **Create comparison matrix**

   In Claude Code conversation:
   ```
   Create a comparison matrix of all AI reviews showing:
   1. Issues identified by all models (consensus)
   2. Issues unique to each model
   3. Severity assessment (critical, high, medium, low)
   4. Recommended fix priority
   ```

6. **Identify consensus issues**

   Expected consensus issues (flagged by multiple models):
   - Missing timeout in HTTP requests (security/availability)
   - No error handling for network failures
   - Missing Content-Type headers
   - API key exposed in memory without rotation
   - No rate limiting for batch operations

7. **Identify unique insights**

   Expected unique insights (model-specific):
   - One model might flag JSON parsing without error handling
   - Another might suggest async batch operations
   - One might recommend connection pooling
   - Another might suggest request retries with exponential backoff

8. **Create action plan**

   In Claude Code conversation:
   ```
   Based on the multi-model review, create a prioritized action plan with:
   1. Critical fixes (do immediately)
   2. High priority (do before production)
   3. Medium priority (technical debt)
   4. Low priority (nice to have)
   ```

## Expected Outcome

- All available AI models provide code reviews
- Each review includes specific line numbers and issues
- Consensus issues identified (flagged by 2+ models)
- Unique insights from individual models captured
- Comparison matrix shows complementary perspectives
- Action plan prioritizes fixes based on multi-model agreement
- Critical issues have high confidence due to consensus

## Success Criteria

- [ ] Claude provides detailed code review with specific line numbers
- [ ] If Gemini available: Gemini review captured
- [ ] If Codex available: Codex review captured
- [ ] If OpenCode available: OpenCode review captured
- [ ] At least 3 consensus issues identified across models
- [ ] At least 1 unique insight per model captured
- [ ] Comparison matrix created showing all findings
- [ ] Action plan prioritizes consensus issues as critical
- [ ] Action plan includes severity assessment
- [ ] All AI reviews complete within reasonable time (< 2 min each)

## Value Demonstrated

This scenario proves wicked-garden enables **high-confidence code quality assurance** through multi-model consensus. Instead of relying on a single AI's perspective:

- **Consensus issues** (flagged by multiple models) are high-confidence and should be prioritized
- **Unique insights** from individual models catch edge cases and blind spots
- **Diverse perspectives** provide more comprehensive coverage than single-model review
- **Actionable prioritization** based on agreement reduces subjective decision-making

This workflow transforms code review from "helpful suggestion" to **validated quality gate** with measurable confidence levels.
