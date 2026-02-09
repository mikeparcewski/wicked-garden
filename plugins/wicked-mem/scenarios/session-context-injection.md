---
name: session-context-injection
title: Automatic Context Injection on SessionStart
description: SessionStart hook loads relevant memories without manual recall
type: integration
difficulty: basic
estimated_minutes: 7
---

# Automatic Context Injection on SessionStart

Test that the SessionStart hook loads relevant project memories automatically when Claude Code starts.

## Setup

Create a project with stored memories that should be loaded on session start.

1. **Create or navigate to a project**
   ```bash
   mkdir -p ~/test-projects/e-commerce-api
   cd ~/test-projects/e-commerce-api
   ```

2. **Store project-specific memories**

   Decision memory:
   ```
   /wicked-mem:store "Using Fastify instead of Express. Reasons: (1) Built-in schema validation with JSON Schema, (2) 2-3x faster request throughput for our read-heavy API, (3) Async/await as first-class - no callback hell. Trade-off: smaller ecosystem than Express." --type decision --tags fastify,framework,performance
   ```

   Procedural memory:
   ```
   /wicked-mem:store "Rate limiting pattern: Use fastify-rate-limit with Redis store. Config: max 100 requests per 15 min per IP for general endpoints, max 10 per minute for auth endpoints. Store in Redis so limits work across multiple instances." --type procedural --tags rate-limiting,fastify,redis,security
   ```

   Episodic memory:
   ```
   /wicked-mem:store "Product search was timing out on large catalogs. Root cause: Full-text search with LIKE on unindexed columns. Fix: Added GIN index on products(name, description) and switched to PostgreSQL full-text search (to_tsvector). Search went from 8s to 40ms. Key learning: Always index text search columns." --type episodic --tags postgres,performance,search
   ```

3. **Check current session stats**
   ```
   /wicked-mem:stats
   ```

## Steps

1. **End the current session**
   - Close Claude Code completely, OR
   - Start a new conversation thread

2. **Start a new session in the same project**
   - Navigate to the project directory (~/test-projects/e-commerce-api)
   - Open Claude Code

3. **Immediately ask a project question WITHOUT mentioning details**
   - "What framework are we using?"
   - "How should I implement rate limiting?"
   - "Any gotchas with the product search?"

4. **Observe the agent's knowledge**
   - Does it know about Fastify without being told?
   - Does it reference the rate limiting pattern?
   - Does it mention the search performance learning?

5. **Check what was loaded**
   ```
   /wicked-mem:stats
   ```

   The stats should show the project memories.

6. **Verify no manual recall was needed**
   - Agent should have context immediately
   - No need to run /wicked-mem:recall

## Expected Outcome

- SessionStart hook fires when Claude Code opens
- Hook loads project-specific memories (based on current directory)
- Agent has immediate awareness of project context
- No manual /wicked-mem:recall commands needed
- Questions are answered with project-specific knowledge

## Success Criteria

- [ ] SessionStart hook executes (check Claude Code console if available)
- [ ] Agent demonstrates knowledge of the framework decision (Fastify)
- [ ] Agent references project-specific patterns (rate limiting)
- [ ] Agent recalls past learnings (search performance)
- [ ] All knowledge is available WITHOUT running /wicked-mem:recall manually
- [ ] /wicked-mem:stats shows the 3 project memories
- [ ] Agent scopes memories to the correct project (e-commerce-api)

## Value Demonstrated

Context is automatically loaded without user action. This creates the experience of:
- **No onboarding friction** - Open project, start working, agent already knows the context
- **Eliminates repetition** - No "hey remember we use Fastify" every session
- **Feels collaborative** - Like working with a teammate who read the project docs before joining the call
- **Project isolation** - Memories from other projects don't pollute this context

Real-world impact: This is the killer feature for multi-project work. Context switching between projects doesn't require re-explaining each project's setup. The agent adapts its recommendations based on what it knows about THIS project.

Compare to without hooks:
- Without: "What framework are we using?" → Agent: "I don't have that context"
- With hooks: "What framework are we using?" → Agent: "You're using Fastify for its performance and schema validation"

## Troubleshooting

If memories aren't loaded automatically:
- Verify SessionStart hook is in hooks.json
- Check the session_start.py script exists and is executable
- Verify memories are project-scoped (not global)
- Check Claude Code console for hook errors
