---
name: end-to-end-workflow
title: End-to-End Memory Workflow
description: Complete workflow from learning through problem to retrieval and reuse
type: workflow
difficulty: advanced
estimated_minutes: 15
---

# End-to-End Memory Workflow

Test the complete memory lifecycle in a realistic development workflow: learn from solving a problem, store the learning, retrieve it later when facing a similar problem.

## Setup

Simulate a realistic multi-day development workflow.

## Steps

### Day 1: Solve a Problem and Store the Learning

1. **Start working on a feature**

   Ask: "I need to add file uploads to my Node.js API. What's the best approach?"

2. **Get a solution**

   Agent suggests approach (e.g., multer, validation, S3 storage).

3. **Encounter a problem**

   Say: "The file upload is working locally but fails in production with 'Request Entity Too Large'"

4. **Debug and solve**

   Agent helps identify: nginx default limit of 1MB, need to configure client_max_body_size.

5. **Complete the task**

   Say: "That fixed it! Files up to 10MB are uploading successfully now."

6. **Stop hook triggers**

   Agent should offer to store the learning about nginx limits.

7. **Accept and store**

   Either accept the suggestion or explicitly store:
   ```
   /wicked-mem:store "File upload 'Request Entity Too Large' error in production. Root cause: nginx has 1MB default client_max_body_size limit. Fix: Add 'client_max_body_size 10M;' to nginx.conf in http or server block. Don't forget to reload nginx: 'sudo systemctl reload nginx'. Also needed: (1) Express/multer limit config, (2) Application-level validation to reject >10MB. Key learning: nginx limits are separate from application limits - configure both." --type episodic --tags nginx,file-upload,production,debugging
   ```

8. **Also store the pattern**
   ```
   /wicked-mem:store "File upload implementation checklist: (1) Backend: multer or formidable for parsing, (2) Storage: S3/GCS for production or local for dev, (3) Validation: file type, size, virus scan if public, (4) Limits: nginx/Apache AND application level, (5) Error handling: clear messages for limit exceeded, (6) Security: sanitize filenames, check MIME types, store outside webroot. Common issues: nginx 1MB default, CORS for direct S3 upload." --type procedural --tags file-upload,backend,checklist,security
   ```

9. **Verify storage**
   ```
   /wicked-mem:stats
   /wicked-mem:recall --tags file-upload
   ```

### Day 2: New Session, Similar Problem

10. **Start new session** (close and reopen Claude Code or new conversation)

11. **Different project, similar problem**

    Say: "I'm getting 'Request Entity Too Large' when uploading images in my Django project."

12. **Check if context is automatically injected**

    Does the agent immediately suggest checking nginx config?
    Or does it require manual recall?

13. **Manual recall if needed**
    ```
    /wicked-mem:recall "Request Entity Too Large"
    /wicked-mem:recall --tags file-upload,production
    ```

14. **Verify agent applies the learning**

    Agent should:
    - Recognize similar symptoms
    - Suggest checking nginx configuration
    - Mention the client_max_body_size setting
    - Reference the checklist (Django specifics + nginx limits)
    - Skip debugging steps that won't help (e.g., checking application code first)

15. **Apply the fix faster**

    What took hours on Day 1 should take minutes on Day 2.

### Day 3: Enhance the Memory

16. **Start new session**

17. **Encounter a variation**

    Say: "File uploads work on AWS EC2 but fail on AWS ECS (Fargate)"

18. **Solve the new variation**

    Agent helps identify: ALB (Application Load Balancer) also has size limits.

19. **Update existing memory**

    Add to the memory:
    ```
    /wicked-mem:store "Update: AWS ALB also has max request size. Default varies by region but generally 1MB for requests. Need to check ALB target group settings. For large uploads, consider: (1) Direct S3 upload with presigned URLs, (2) Chunked uploads, (3) ALB request size limits in target group." --type episodic --tags nginx,file-upload,aws,alb
    ```

## Expected Outcome

**Day 1 - Learning:**
- Problem is solved through debugging
- Stop hook recognizes valuable learning
- Learning is stored with appropriate type and tags
- Pattern is captured as procedural memory

**Day 2 - Retrieval:**
- New session doesn't have context loss
- Similar symptoms trigger memory recall (automatic via UserPromptSubmit hook, or manual)
- Agent suggests known solution early
- Debugging is much faster (minutes vs hours)

**Day 3 - Enhancement:**
- Memory gets enriched with variations
- Knowledge base grows organically
- Related problems build on previous learnings

## Success Criteria

- [ ] Day 1: Stop hook offers to store the learning after solving the problem
- [ ] Day 1: Episodic and procedural memories are stored with relevant tags
- [ ] Day 1: /wicked-mem:stats shows the new memories
- [ ] Day 2: Similar problem triggers memory recall (automatic or manual)
- [ ] Day 2: Agent references past solution early in the debugging process
- [ ] Day 2: Time to solution is significantly reduced
- [ ] Day 2: Agent skips approaches that didn't work (demonstrates learning)
- [ ] Day 3: New variation can be added to the knowledge base
- [ ] End-to-end: Memory system proves value in realistic workflow
- [ ] End-to-end: No manual documentation burden - it happens naturally

## Value Demonstrated

This scenario proves the complete value proposition:

**Before wicked-mem:**
- Day 1: Spend 2 hours debugging nginx limits
- Day 2: Forget the details, spend 1.5 hours debugging again
- Day 3: Realize there was a similar problem before, can't find notes

**After wicked-mem:**
- Day 1: Spend 2 hours debugging, system captures the learning automatically
- Day 2: Agent recalls the solution, 15 minutes to apply fix
- Day 3: Knowledge base grows, new variations enhance existing knowledge

**Real-world impact over time:**
- **Month 1:** 10 problems solved and stored
- **Month 2:** 3 similar problems solved in minutes using past learnings
- **Month 3:** New team member asks about file uploads, agent explains the pattern
- **Month 6:** 50+ memories create a comprehensive project knowledge base

The compounding effect is the key value:
- Each solved problem becomes an asset
- Knowledge base grows automatically
- Time savings accelerate over time
- Team scales better (knowledge doesn't live in one person's head)

This is institutional memory for your codebase, built passively as you work.
