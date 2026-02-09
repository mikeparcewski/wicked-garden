# Task Patterns

Common task types and their typical capability mappings. Use as starting points—always verify availability.

## Code Review

**Task signals**: "review", "PR", "code quality", "check this code"

| Need | Capability Type | Options |
|------|-----------------|---------|
| PR context | MCP | github, gitlab |
| Code quality | Agent | wicked-engineering:senior-engineer |
| Security check | Agent | wicked-platform:security-engineer |
| Test coverage | Agent | wicked-qe:code-analyzer |
| Link to ticket | MCP | atlassian, linear |

**Recommended flow**:
1. Get PR diff via MCP
2. Spawn senior-engineer for quality review
3. Spawn security-engineer if auth/data handling involved
4. Store findings in ticket via MCP

---

## Security Audit

**Task signals**: "security", "audit", "vulnerabilities", "penetration", "compliance"

| Need | Capability Type | Options |
|------|-----------------|---------|
| Security expertise | Agent | wicked-platform:security-engineer |
| Compliance check | Agent | wicked-platform:compliance-officer |
| Privacy review | Agent | wicked-platform:privacy-expert |
| Test scenarios | Agent | wicked-qe:test-strategist |
| Store findings | Skill | wicked-mem |

**Recommended flow**:
1. Spawn security-engineer for primary audit
2. Add compliance-officer if regulatory concerns
3. Generate test scenarios for findings
4. Store critical findings in wicked-mem

---

## Architecture Design

**Task signals**: "design", "architecture", "system design", "how should we build"

| Need | Capability Type | Options |
|------|-----------------|---------|
| Solution design | Agent | wicked-engineering:solution-architect |
| Data modeling | Agent | wicked-data:data-architect |
| Store decisions | Skill | wicked-mem |
| Document design | Agent | wicked-engineering:technical-writer |

**Recommended flow**:
1. Spawn solution-architect for high-level design
2. Add data-architect if persistence involved
3. Store decisions in wicked-mem
4. Document via technical-writer

---

## Bug Investigation

**Task signals**: "bug", "error", "broken", "not working", "investigate"

| Need | Capability Type | Options |
|------|-----------------|---------|
| Debugging | Agent | wicked-engineering:debugger |
| Error tracking | MCP | sentry, datadog, rollbar |
| Logs/traces | Agent | wicked-platform:incident-responder |
| Codebase exploration | Agent | Explore |
| Track fix | MCP | atlassian, github issues |

**Recommended flow**:
1. Check error tracking MCP for context
2. Spawn debugger for systematic investigation
3. Use Explore agent to understand code paths
4. Track fix in issue tracker

---

## Feature Implementation

**Task signals**: "implement", "build", "add feature", "create"

| Need | Capability Type | Options |
|------|-----------------|---------|
| Requirements clarity | Agent | wicked-product:requirements-analyst |
| Design guidance | Agent | wicked-engineering:solution-architect |
| Implementation | Agent | wicked-engineering:senior-engineer |
| Test strategy | Agent | wicked-qe:test-strategist |
| Track progress | MCP/Skill | atlassian, wicked-kanban |

**Recommended flow**:
1. Clarify requirements with requirements-analyst if vague
2. Get design guidance from solution-architect
3. Plan tests with test-strategist
4. Track in kanban/issue tracker

---

## Documentation

**Task signals**: "document", "write docs", "README", "API docs"

| Need | Capability Type | Options |
|------|-----------------|---------|
| Technical writing | Agent | wicked-engineering:technical-writer |
| API documentation | Agent | wicked-engineering:api-documentarian |
| Publish docs | MCP | confluence, notion |
| Code understanding | Agent | Explore |

**Recommended flow**:
1. Use Explore to understand what needs documenting
2. Spawn appropriate docs agent
3. Publish via documentation MCP if available

---

## Data Analysis

**Task signals**: "analyze data", "query", "metrics", "report"

| Need | Capability Type | Options |
|------|-----------------|---------|
| Data exploration | Agent | wicked-data:data-analyst |
| Query execution | MCP | snowflake, bigquery, databricks |
| Local file analysis | Skill | wicked-data |
| Visualization guidance | Agent | wicked-data:data-analyst |

**Recommended flow**:
1. Check for data warehouse MCP
2. If available, use for queries
3. If not, use wicked-data for local files
4. Spawn data-analyst for interpretation

---

## Incident Response

**Task signals**: "incident", "outage", "production issue", "pages"

| Need | Capability Type | Options |
|------|-----------------|---------|
| Incident triage | Agent | wicked-platform:incident-responder |
| Error context | MCP | sentry, datadog |
| Log analysis | Agent | wicked-platform:sre |
| Communication | MCP | slack, teams |
| Post-mortem | Skill | wicked-mem |

**Recommended flow**:
1. Spawn incident-responder immediately
2. Pull context from observability MCP
3. Communicate status via chat MCP
4. Store learnings in wicked-mem

---

## Test Planning

**Task signals**: "test", "QA", "test strategy", "what to test"

| Need | Capability Type | Options |
|------|-----------------|---------|
| Test strategy | Agent | wicked-qe:test-strategist |
| Test generation | Agent | wicked-qe:test-automation-engineer |
| TDD guidance | Agent | wicked-qe:tdd-coach |
| Risk assessment | Agent | wicked-qe:risk-assessor |

**Recommended flow**:
1. Spawn test-strategist to identify what to test
2. Use risk-assessor for priority
3. Generate tests with test-automation-engineer

---

## Quick Reference Matrix

| Task Type | Primary Agent | Supporting | MCP Needs |
|-----------|---------------|------------|-----------|
| Code review | senior-engineer | security-engineer | github/gitlab |
| Security audit | security-engineer | compliance-officer | - |
| Architecture | solution-architect | data-architect | - |
| Bug fix | debugger | incident-responder | error tracking |
| Feature | requirements-analyst | solution-architect | project mgmt |
| Docs | technical-writer | api-documentarian | confluence |
| Data | data-analyst | - | warehouse |
| Incident | incident-responder | sre | observability |
| Testing | test-strategist | tdd-coach | - |

## When Capabilities Aren't Available

If recommended capability isn't available:

| Missing | Fallback |
|---------|----------|
| Domain agent | Use Explore + manual analysis |
| MCP integration | Use built-in tools + manual steps |
| Specific skill | Check for similar skill or use general approach |

Always note gaps in recommendations so user knows what's missing.
