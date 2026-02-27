---
name: debug-pattern
title: The Debug Pattern
description: Agent remembers how a similar bug was fixed before
type: workflow
difficulty: intermediate
estimated_minutes: 5
---

# The Debug Pattern

Test that learnings from debugging sessions persist and prevent repeating the same debugging journey.

## Setup

Simulate having solved a tricky bug previously.

1. **Store an episodic memory from a past debug session**
   ```
   /wicked-mem:store "Fixed 'Connection refused on port 5432' error in Docker. Root cause: The postgres container and app container weren't on the same network - they were on different default bridge networks created at different times. Symptoms: (1) psql from host worked, (2) psql from app container failed, (3) docker logs showed postgres was healthy. Diagnostic: 'docker network inspect bridge' and 'docker ps --format \"{{.Names}}\t{{.Networks}}\"' showed the network mismatch. Fix: Added explicit network in docker-compose.yml and recreated containers. Key learning: Always use explicit networks in docker-compose, never rely on default bridge. Prevention: Add network check to CI startup script." --type episodic --tags debugging,docker,postgres,networking
   ```

2. **Store a related procedural memory**
   ```
   /wicked-mem:store "Docker connection debugging checklist: (1) Verify containers are running: docker ps, (2) Check logs: docker logs <container>, (3) Test from host: can you connect from outside Docker?, (4) Check networks: docker ps --format \"{{.Names}}\t{{.Networks}}\", (5) Verify same network: containers must share a network to communicate, (6) Test DNS: docker exec <app> ping <db-service-name>, (7) Check ports: docker port <container>. Most connection issues are network isolation or DNS." --type procedural --tags docker,debugging,checklist
   ```

## Steps

1. **Simulate encountering a similar error**
   - Imagine seeing: "Error: connect ECONNREFUSED 127.0.0.1:5432"
   - Or: "Error: getaddrinfo ENOTFOUND postgres"

2. **Ask the agent for help**
   - "I'm getting 'connection refused' when connecting to Postgres from my app"
   - "Docker containers can't talk to each other"

3. **Check if agent recalls the pattern**
   ```
   /wicked-mem:recall "connection refused postgres"
   /wicked-mem:recall "docker network"
   /wicked-mem:recall --tags debugging,docker
   ```

4. **Verify agent suggests the known fix**
   - Does it mention checking docker networks?
   - Does it suggest the procedural checklist?
   - Does it skip the dead ends you already tried?

## Expected Outcome

- Agent finds the relevant past debugging session automatically
- Agent suggests checking docker networks early (not after trying other approaches)
- Agent references the procedural checklist
- Agent saves time by not repeating failed debugging approaches
- If UserPromptSubmit hook is working, relevant memories inject into the response context

## Success Criteria

- [ ] Episodic memory captures the problem, diagnostic steps, root cause, and fix
- [ ] Procedural memory provides reusable checklist
- [ ] Search by symptoms ("connection refused") finds the memory
- [ ] Search by context ("docker network") finds the memory
- [ ] Agent suggests the docker network check proactively (demonstrates learning)
- [ ] Agent explains the diagnostic commands from the checklist
- [ ] /wicked-mem:stats shows 2 memories (1 episodic, 1 procedural)

## Value Demonstrated

Agent learns from experience and builds a debugging knowledge base. Prevents:
- **Repeating the same debugging path** - You tried psql from host last time, it worked, it's not the issue
- **Forgetting diagnostic commands** - What was that docker network inspect command again?
- **Losing tribal knowledge** - "Oh yeah, we had this issue before" but can't remember the fix
- **Time waste** - What took 2 hours to debug the first time takes 10 minutes the second time

Real-world impact: This scenario mirrors how senior engineers build intuition. They've seen "connection refused" + Docker before and immediately think "network isolation." The memory system lets the agent build the same intuition.
