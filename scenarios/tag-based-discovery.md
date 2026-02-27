---
name: tag-based-discovery
title: Multi-Faceted Tag-Based Discovery
description: Use tags to discover memories across multiple dimensions
type: feature
difficulty: basic
estimated_minutes: 5
---

# Multi-Faceted Tag-Based Discovery

Test that tags enable flexible discovery of memories from multiple perspectives.

## Setup

Create a realistic set of memories with overlapping tags representing different facets (technology, domain, type of work, team member).

1. **Store memories with multi-faceted tags**

   Memory 1 - Backend API bug:
   ```
   /wicked-mem:store "API returning 500 on POST /orders with large payloads. Root cause: Express body-parser default limit of 100kb. Fix: Increased limit to 10mb for order endpoint. Added validation to reject >10mb. Key learning: Always set explicit size limits and handle them gracefully." --type episodic --tags api,express,bug,orders,security
   ```

   Memory 2 - Database decision:
   ```
   /wicked-mem:store "Using PostgreSQL connection pooling with pg-pool. Max 20 connections, idle timeout 10s. Reasoning: Prevent connection exhaustion during traffic spikes. Heroku Postgres has 20 connection limit on standard tier." --type decision --tags postgres,performance,infrastructure,devops
   ```

   Memory 3 - Frontend pattern:
   ```
   /wicked-mem:store "React form validation pattern: Use react-hook-form with zod schema. Benefits: Type-safe validation, minimal re-renders, good DX. Example: checkout form, profile edit form." --type procedural --tags react,forms,typescript,frontend,dx
   ```

   Memory 4 - Testing approach:
   ```
   /wicked-mem:store "E2E test flakiness was caused by not waiting for API responses. Fix: Use cy.intercept() to explicitly wait for network requests. Always alias intercepts and cy.wait() on them. Added to CI to catch flakes early." --type episodic --tags testing,cypress,ci,bug,frontend
   ```

   Memory 5 - Security decision:
   ```
   /wicked-mem:store "Storing API keys in AWS Secrets Manager instead of environment variables. Reasons: (1) Automatic rotation, (2) Audit logging, (3) Fine-grained IAM permissions. Trade-off: 50ms latency on cold start. Acceptable for our use case." --type decision --tags security,aws,api-keys,infrastructure
   ```

## Steps

1. **Discover by technology stack**
   ```
   /wicked-mem:recall --tags postgres
   /wicked-mem:recall --tags react
   /wicked-mem:recall --tags express
   ```

2. **Discover by problem domain**
   ```
   /wicked-mem:recall --tags security
   /wicked-mem:recall --tags performance
   /wicked-mem:recall --tags bug
   ```

3. **Discover by layer/responsibility**
   ```
   /wicked-mem:recall --tags frontend
   /wicked-mem:recall --tags infrastructure
   /wicked-mem:recall --tags api
   ```

4. **Discover by feature area**
   ```
   /wicked-mem:recall --tags orders
   /wicked-mem:recall --tags testing
   ```

5. **Combine tags for precise discovery**
   ```
   /wicked-mem:recall --tags bug,frontend
   /wicked-mem:recall --tags security,aws
   ```

6. **Search by content, then filter by tag**
   ```
   /wicked-mem:recall "connection" --tags postgres
   /wicked-mem:recall "validation" --tags react
   ```

## Expected Outcome

- Each tag query returns relevant memories
- Same memory appears in multiple tag searches (e.g., "API returning 500" appears in both "api" and "express")
- Combined tags narrow results (bug+frontend returns only cypress, not express)
- Tag-based discovery complements text search
- All memories remain organized and findable from multiple angles

## Success Criteria

- [ ] Single tag queries return all relevant memories
- [ ] Multi-tag queries (comma-separated) return intersection (memories with ALL tags)
- [ ] Same memory discoverable via different facets (technology, domain, layer)
- [ ] Tags shown in /wicked-mem:stats by frequency or category
- [ ] Text search + tag filter works correctly
- [ ] /wicked-mem:recall without arguments shows recent memories regardless of tags

## Value Demonstrated

Tags create a flexible organizational system that mirrors how people actually think:
- **Technology perspective** - "Show me all Postgres issues"
- **Problem perspective** - "Show me all security decisions"
- **Layer perspective** - "Show me all frontend learnings"
- **Feature perspective** - "Show me everything related to orders"

This prevents the rigid hierarchy problem of folders:
- Is the "API 500 error" memory filed under Express? Or Orders? Or Bugs?
- With tags: it's ALL of those simultaneously

Real-world impact:
- **Onboarding** - New frontend dev sees all frontend memories with one command
- **Debugging** - Bug in orders? See all past order-related issues
- **Architecture** - Planning security improvements? See all past security decisions and learnings
- **Refactoring** - Replacing Express? Find all Express-specific knowledge to update

Compare to alternatives:
- **Folders**: Rigid, single classification, hard to reorganize
- **Full-text search**: Good for known terms, bad for browsing
- **Tags**: Flexible, multi-faceted, browseable, combinable
