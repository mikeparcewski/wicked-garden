# Discovery Sources

Where to look for capabilities and how to check each source.

## Source Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         Capability Sources                                │
├─────────────────┬──────────────┬─────────────────┬────────────────────── ┤
│  MCP Servers    │  CLI Tools   │  Skills         │  Agents               │
│  (external)     │  (PATH)      │  (methodology)  │  (specialized workers)│
├─────────────────┼──────────────┼─────────────────┼───────────────────────┤
│  ListMcpRes...  │ command -v   │  Skill tool     │  Task tool            │
│  Tool           │ {tool}       │  description    │  agent list           │
└─────────────────┴──────────────┴─────────────────┴───────────────────────┘
```

## MCP Servers

**What they provide**: External integrations (Jira, GitHub, Slack, analytics, etc.)

**How to discover**:
```
ListMcpResourcesTool
```

**What to look for**:
- Server names (often match the service: `atlassian`, `github`, `slack`)
- Resource descriptions
- Available tools/operations

**Key insight**: MCP servers are user-configured. Don't assume availability—always check.

### MCP Discovery Pattern

```markdown
## MCP Discovery

Available servers:
- `atlassian` - Jira/Confluence (project management, documentation)
- `context7` - Library documentation retrieval

Matched to needs:
- Project tracking → atlassian (Jira)
- Code docs → context7
- Analytics → NOT AVAILABLE
```

## PATH / CLI Tools

**What they provide**: Installed binaries for browser automation, cloud platforms, databases, CI/CD, package management, and AI models.

**How to discover**:
```bash
command -v {tool}   # returns exit 0 if found, non-zero if not
```

**Key insight**: CLI tools are environment-specific. Don't assume availability — always check with `command -v`.

**Detection categories**:

| Category | Key Tools |
|----------|-----------|
| AI CLIs | claude, codex, gemini, opencode, pi |
| Browser | playwright, puppeteer, cypress |
| Cloud | aws, gcloud, az, heroku, vercel, fly |
| Observability | datadog-agent, newrelic, dynatrace |
| Data | duckdb, psql, mysql, mongosh, redis-cli |
| CI/CD | gh, glab, circleci |
| Package managers | uv, bun, npm, pip, cargo, go |

### CLI Discovery Pattern

```markdown
## CLI Discovery

Task requires browser automation.

Detection (priority order):
- playwright: FOUND (/usr/local/bin/playwright)
- puppeteer: not checked (playwright found first)
- cypress: not checked

Recommendation: Use playwright.
Stake level: medium — informing user of choice.
```

**Decision policy**: Low stakes → auto-decide silently. Medium stakes → auto-decide and inform. High stakes → always ask user. See [cli-detection.md](cli-detection.md) for full policy.

**Preference storage**: After first selection, store in wicked-mem under `cli-preference:{category}`.

---

## Skills

**What they provide**: Methodology, expertise, guidance, processes

**How to discover**: Check the Skill tool's available skills list in system prompt, or invoke skills by name.

**Key skill families** (wicked-garden):

| Family | Purpose | Example Skills |
|--------|---------|----------------|
| **engineering** | Engineering & architecture | senior-engineer, debugger |
| **qe** | Quality engineering | test-strategist, tdd-coach |
| **platform** | Security/compliance | security-engineer, privacy-expert |
| **product** | Product management | requirements-analyst, product-manager |
| **data** | Data engineering | data-engineer, ml-engineer |
| **wicked-crew** | Workflow orchestration | orchestrator, facilitator |

### Skill Discovery Pattern

```markdown
## Skill Discovery

Task involves security review.

Relevant skills:
- platform (security-engineer, privacy-expert)
- qe (test-strategist for security test scenarios)
- engineering (senior-engineer for code quality)

Recommendation: Use wicked-garden:platform:security-engineer as primary reviewer.
```

## Agents

**What they provide**: Specialized subagents that can work autonomously

**How to discover**: Check Task tool's `subagent_type` options in system prompt.

**Agent categories**:

| Category | Agents | Best For |
|----------|--------|----------|
| **Explore** | Codebase exploration | Finding files, understanding structure |
| **Plan** | Implementation planning | Designing approaches |
| **Bash** | Command execution | Git, npm, system commands |
| **wicked-*:*** | Specialized domain agents | Specific expertise |

### Agent Discovery Pattern

```markdown
## Agent Discovery

Task: "Review PR for security issues"

Relevant agents:
- `wicked-garden:platform:security-engineer` - Security expertise
- `wicked-garden:engineering:senior-engineer` - Code quality
- `Explore` - Understand codebase context

Recommendation: Spawn security-engineer for focused review.
```

## Built-in Tools

**What they provide**: Core operations always available

**Always available**:

| Tool | Purpose |
|------|---------|
| Read, Write, Edit | File operations |
| Bash | Command execution |
| Glob, Grep | File/content search |
| WebFetch, WebSearch | Web access |
| Task | Spawn subagents |
| Skill | Invoke skills |

**Don't need to discover these**—they're always present.

## Discovery Checklist

When scouting for a task:

```markdown
## Discovery Checklist

Task: [description]

### 1. MCP Servers
- [ ] Run ListMcpResourcesTool
- [ ] Match servers to task needs
- [ ] Note what's missing

### 2. CLI Tools
- [ ] Check wicked-mem for stored cli-preference:{category}
- [ ] If no preference, run `command -v` on priority-ordered tool list
- [ ] Apply auto-decide vs ask policy based on stake level
- [ ] Store selection in wicked-mem after first decision

### 3. Skills
- [ ] Identify relevant skill families
- [ ] Check if installed/available
- [ ] Note methodology gaps

### 4. Agents
- [ ] Identify specialized agents needed
- [ ] Check availability
- [ ] Plan orchestration

### 5. Built-in Tools
- [ ] Confirm required tools (usually all available)
```

## Discovery vs. Assumption

| Approach | Risk | Better |
|----------|------|--------|
| Assume Jira available | Fails if not configured | Check MCP first |
| Use generic agent | Misses specialized help | Check for domain agents |
| Skip skill check | Miss methodology guidance | Check relevant skills |
| Hardcode tool names | Breaks with different setup | Discover by capability |

## Caching Discovery Results

For long-running tasks, cache discovery at the start:

```markdown
## Session Capabilities (discovered at start)

**MCP**: atlassian, github, context7
**Skills**: wicked-* family installed
**Agents**: Full wicked-garden specialist set

Reference this throughout session instead of re-discovering.
```
