---
name: integration-discovery
description: |
  Capability router that decides which tools, skills, and agents to use for a task.
  Reduces cognitive load on the main agent by making tool selection decisions.

  Use this skill (or spawn as subagent) when:
  - Starting a complex task that might benefit from available integrations
  - Unsure what tools/skills could help with current work
  - Want to discover capabilities before executing
  - Building a task plan that should leverage available resources
---

# Capability Router

**Purpose**: Scout available capabilities and decide what to use for a task. Return actionable recommendations so the main agent can execute without discovery overhead.

## Why This Matters

Most agents execute with whatever tools are obvious. They don't:
- Check what else is available
- Consider skills that could help
- Look for specialized agents
- Adapt to the user's configured integrations

**This skill changes that.** It scouts, evaluates, and recommends—so the main agent can focus on execution.

## Quick Usage

### As Inline Check

```markdown
Before executing this task, let me check what capabilities could help.

**Task**: Review PR #123 for security issues

**Discovery**:
- MCP: github (PR context), atlassian (link to Jira)
- Skills: wicked-qe (test scenarios), wicked-platform (security checks)
- Agents: wicked-garden:platform/security-engineer

**Recommendation**: Use security-engineer agent for review, github MCP for PR data.
```

### As Subagent

For complex tasks, spawn integration-discovery as a subagent:

```
Task tool:
  subagent_type: "Explore"
  prompt: "Scout available capabilities for: [task description].
           Return specific recommendations on which MCP servers,
           skills, and agents to use."
```

## The Discovery Process

### Step 1: Understand the Task

What does this task need?
- **Information sources**: Where does data come from?
- **Actions**: What operations are required?
- **Quality concerns**: Security, testing, compliance?
- **Output**: Where do results go?

### Step 2: Scout Available Capabilities

Check these sources (see refs/discovery-sources.md for details):

| Source | How to Check | What You Get |
|--------|--------------|--------------|
| **MCP Servers** | `ListMcpResourcesTool` | External integrations |
| **Skills** | Check Skill tool description | Methodology/expertise |
| **Agents** | Check Task tool agent list | Specialized workers |
| **Built-in Tools** | Known set | File ops, search, web |

### Step 3: Match Capabilities to Needs

For each task need, find matching capabilities:

```markdown
Task: "Implement user authentication"

| Need | Capability | Recommendation |
|------|------------|----------------|
| Security review | wicked-garden:platform/security-engineer | Use for auth review |
| Test strategy | wicked-garden:qe/test-strategist | Use for test planning |
| Store decisions | wicked-mem | Store auth decisions |
| Track work | MCP:atlassian or wicked-kanban | Track implementation |
```

### Step 4: Return Recommendations

Output a clear recommendation the main agent can act on:

```markdown
## Capability Recommendations for: [Task]

**Use these**:
1. **wicked-garden:platform/security-engineer** - Review for security issues
2. **MCP:atlassian** - Link work to Jira ticket AUTH-123

**Available but optional**:
- wicked-garden:qe/test-strategist - If test planning needed
- wicked-mem - Store decisions for future reference

**Not available** (consider installing):
- No analytics MCP found - can't check auth failure metrics
```

## Common Task Patterns

Quick mappings for common tasks (see refs/task-patterns.md for full list):

| Task Type | Likely Capabilities |
|-----------|---------------------|
| Code review | wicked-engineering agents, github MCP |
| Security audit | wicked-platform agents, wicked-qe |
| Architecture design | wicked-engineering agents, wicked-mem |
| Bug investigation | wicked-engineering agents, error tracking MCP |
| Feature planning | wicked-product agents, project management MCP |
| Documentation | wicked-engineering agents, confluence MCP |

## Decision Principles

When multiple options exist:

1. **Prefer specialized over general** - Use security-engineer for security, not generic reviewer
2. **Prefer available integrations** - Use configured MCP over manual alternatives
3. **Consider task scope** - Simple task? Skip the heavy machinery
4. **Check dependencies** - Some agents work better together

## Output Format

Always return structured recommendations:

```markdown
## Capability Recommendations

**Task**: [one-line task description]

### Recommended
| Capability | Type | Use For |
|------------|------|---------|
| name | MCP/Skill/Agent | specific purpose |

### Optional
| Capability | Type | Use If |
|------------|------|--------|
| name | type | condition |

### Not Available
| Need | Suggestion |
|------|------------|
| what's missing | how to get it |
```

## References

- [Discovery Sources](refs/discovery-sources.md) - Where to look and how
- [Task Patterns](refs/task-patterns.md) - Common task-to-capability mappings
- [MCP Capabilities](refs/capabilities.md) - MCP server categories and patterns
