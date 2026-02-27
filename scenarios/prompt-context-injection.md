---
name: prompt-context-injection
title: Smart Context Injection on User Prompts
description: UserPromptSubmit hook injects relevant memories based on query content
type: integration
difficulty: intermediate
estimated_minutes: 6
---

# Smart Context Injection on User Prompts

Test that the UserPromptSubmit hook analyzes user questions and automatically injects relevant memories into the agent's context.

## Setup

Create a knowledge base with memories across different topics.

1. **Store authentication-related memories**
   ```
   /wicked-mem:store "JWT tokens stored in httpOnly cookies, not localStorage. Prevents XSS token theft. Refresh token rotation implemented with 7-day expiry." --type decision --tags auth,jwt,security
   ```

   ```
   /wicked-mem:store "Authentication middleware checks: (1) Token presence, (2) Token validity, (3) User still active, (4) Required permissions for route. Returns 401 for auth failures, 403 for permission issues." --type procedural --tags auth,middleware,security
   ```

2. **Store database-related memories**
   ```
   /wicked-mem:store "Using Prisma ORM. Benefits: Type-safe queries, excellent migration system, good DX. Gotcha: Generated client can be large (100MB+ in node_modules for complex schemas). Not an issue but surprising." --type decision --tags database,prisma,orm
   ```

   ```
   /wicked-mem:store "Database connection pool leak was causing 'too many clients' errors. Root cause: Not properly releasing connections in error paths. Fix: Always use try/finally to release, or use Prisma's built-in connection management. Added monitoring for active connections." --type episodic --tags database,debugging,prisma,connections
   ```

3. **Store deployment-related memories**
   ```
   /wicked-mem:store "Deploy to Railway using GitHub integration. Main branch auto-deploys to production. PR preview environments created automatically. Environment variables managed in Railway dashboard. Database connection string injected as DATABASE_URL." --type procedural --tags deployment,railway,ci-cd
   ```

## Steps

1. **Ask a question about authentication WITHOUT mentioning past context**

   Ask: "How should I implement the logout endpoint?"

2. **Observe agent's response**

   - Does it mention httpOnly cookies?
   - Does it reference the token storage decision?
   - Does it mention the authentication middleware pattern?
   - Check if relevant memories were silently injected into context

3. **Ask a question about database WITHOUT context**

   Ask: "I'm getting 'too many clients' error from Postgres"

4. **Observe agent's response**

   - Does it recognize the symptom from the episodic memory?
   - Does it suggest checking connection pool management?
   - Does it mention Prisma-specific considerations?

5. **Ask a question about deployment**

   Ask: "How do I add a new environment variable?"

6. **Observe agent's response**

   - Does it mention Railway dashboard?
   - Does it reference the existing deployment setup?

7. **Ask a cross-cutting question**

   Ask: "What security considerations should I keep in mind?"

8. **Observe agent's response**

   - Does it pull from multiple memories (JWT cookies, auth middleware)?
   - Does it synthesize across topic areas?

9. **Verify with explicit recall**
   ```
   /wicked-mem:recall "auth"
   /wicked-mem:recall "database"
   /wicked-mem:recall "security"
   ```

   Compare what the agent referenced naturally vs what's in storage.

## Expected Outcome

**Automatic context injection:**
- User asks about logout → Auth memories injected
- User asks about database error → Database memories injected
- User asks about deployment → Deployment memories injected
- User asks about security → Relevant memories from multiple categories injected

**No manual recall needed:**
- Agent has context without running /wicked-mem:recall
- Context is relevant to the question (not all memories dumped)
- Injection happens transparently

**Quality of injection:**
- Relevant memories are included
- Irrelevant memories are excluded
- Agent naturally references the stored knowledge in its response

## Success Criteria

- [ ] UserPromptSubmit hook fires on each user question
- [ ] Auth question triggers injection of auth-related memories
- [ ] Database question triggers injection of database-related memories
- [ ] Agent references stored decisions naturally (e.g., mentions httpOnly cookies)
- [ ] Agent applies stored procedures (e.g., uses the auth middleware pattern)
- [ ] Agent recognizes past problems (e.g., connection pool leak)
- [ ] Cross-cutting questions pull from multiple memory categories
- [ ] Irrelevant memories are NOT injected (deployment memories don't appear for auth questions)
- [ ] No manual /wicked-mem:recall commands were needed
- [ ] Agent's answers are more informed than without the memory system

## Value Demonstrated

This hook creates "contextual intelligence" - the agent knows what it needs to know, when it needs to know it:

**Without UserPromptSubmit hook:**
- User: "How do I implement logout?"
- Agent: Generic logout implementation (not project-specific)
- User must manually recall context or explain the setup

**With UserPromptSubmit hook:**
- User: "How do I implement logout?"
- Agent: "Given your JWT-in-httpOnly-cookies setup, for logout you need to..."
- Context is automatically relevant and specific

**Real-world impact:**
- **Eliminates context explanation overhead** - Don't repeat "we use JWT in cookies" every conversation
- **Answers are project-specific** - Not generic Stack Overflow responses
- **Faster iteration** - Agent gives relevant answers on first try
- **Better decisions** - Past context informs current recommendations

The key insight: The best memory system is one you never think about. It just makes the agent smarter.

## Troubleshooting

If context isn't being injected:
- Check `/Users/michael.parcewski/Projects/wicked-garden/plugins/wicked-mem/hooks/hooks.json` has UserPromptSubmit
- Verify prompt_submit.py script exists and is executable
- Check Claude Code console for hook execution
- Verify memories exist with /wicked-mem:stats
- Check memory tags match query keywords (e.g., "auth" query should match "auth" tag)
