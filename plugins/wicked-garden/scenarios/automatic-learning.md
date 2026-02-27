---
name: automatic-learning
title: Automatic Learning After Completion
description: Stop hook prompts to store learnings after completing work
type: integration
difficulty: intermediate
estimated_minutes: 8
---

# Automatic Learning After Completion

Test that the Stop hook recognizes valuable learnings and prompts to store them automatically.

## Setup

No explicit setup needed - this tests the natural flow of completing work and extracting learnings.

## Steps

1. **Simulate completing a meaningful task with learnings**

   Ask the agent to help with something that involves a decision or problem-solving:

   Example 1: "Help me set up JWT authentication for my API"

   Example 2: "I'm getting CORS errors. The API is on localhost:3000 and frontend on localhost:5173"

   Example 3: "Should I use React Context or Redux for managing user session state?"

2. **Complete the task**
   - Let the agent provide a solution
   - Implement or acknowledge the fix works

3. **Observe the Stop hook**
   - After the agent's response, the Stop hook should fire
   - Agent should either:
     - Offer to store a memory (if something valuable was learned/decided)
     - Respond with "Success" (if nothing worth storing)

4. **Accept the memory storage offer**
   - If offered, say "yes" or use the suggested /wicked-mem:store command
   - The agent should store with appropriate type and tags

5. **Verify the stored memory**
   ```
   /wicked-mem:stats
   /wicked-mem:recall --type decision
   /wicked-mem:recall --type episodic
   ```

## Expected Outcome

**When there's valuable content:**
- Agent recognizes key decision ("Context is better than Redux for simple session state")
- Agent recognizes problem solved ("CORS fixed by configuring express cors middleware")
- Agent recognizes useful pattern ("JWT verification middleware pattern")
- Agent offers to store with suggested content, type, and tags

**When there's nothing valuable:**
- Agent responds with "Success" without offering storage
- No noise for routine tasks or simple Q&A

## Success Criteria

- [ ] Stop hook fires after agent response (check console or behavior)
- [ ] Agent offers memory storage for decisions (why X over Y)
- [ ] Agent offers memory storage for problems solved (root cause + fix)
- [ ] Agent offers memory storage for useful patterns
- [ ] Agent does NOT offer storage for routine tasks (e.g., "show me the file")
- [ ] Suggested memory includes: content, type, and relevant tags
- [ ] Stored memory appears in /wicked-mem:stats
- [ ] Memory is retrievable and well-formatted

## Value Demonstrated

Eliminates the manual burden of deciding "should I remember this?" The system:
- **Captures learnings automatically** - You don't have to remember to remember
- **Reduces cognitive load** - Focus on solving problems, not documenting them
- **Builds knowledge base passively** - Every solved problem becomes future reference
- **Prevents valuable loss** - That clever fix you found at 11pm gets captured, not forgotten

Real-world impact: This is the difference between having a personal documentation system you never maintain and one that maintains itself. After a month, you have a rich history of what you've learned without explicitly creating it.

## Troubleshooting

If the Stop hook doesn't fire:
- Check `/Users/michael.parcewski/Projects/wicked-garden/plugins/wicked-mem/hooks/hooks.json` is valid
- Verify the plugin is properly installed
- Check Claude Code console for hook execution errors
