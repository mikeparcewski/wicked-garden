---
phase_relevance: ["bootstrap"]
archetype_relevance: ["*"]
---
# Task Patterns

Common task types and their typical capability mappings. Use as starting points—always verify availability.

## Code Review

**Task signals**: "review", "PR", "code quality", "check this code"

| Need | Capability Type | Options |
|------|-----------------|---------|
| PR context | MCP | github, gitlab |
| Code quality | Agent / inline | wicked-garden:crew:reviewer (or engineering review skill inline) |
| Security check | Agent | wicked-garden:platform:security-engineer |
| Test coverage | Agent / inline | wicked-garden:crew:reviewer (or engineering review skill inline) |
| Link to ticket | MCP | atlassian, linear |

**Recommended flow**:
1. Get PR diff via MCP
2. Run the engineering review skill inline (or dispatch crew:reviewer) for quality
3. Spawn security-engineer if auth/data handling involved
4. Store findings in ticket via MCP

---

## Security Audit

**Task signals**: "security", "audit", "vulnerabilities", "penetration", "compliance"

| Need | Capability Type | Options |
|------|-----------------|---------|
| Security expertise | Agent | wicked-garden:platform:security-engineer |
| Compliance check | Agent | wicked-garden:platform:compliance-officer |
| Privacy review | Agent | wicked-garden:platform:privacy-expert |
| Test scenarios | Agent | wicked-garden:crew:gate-adjudicator |
| Store findings | Skill | wicked-brain:memory |

**Recommended flow**:
1. Spawn security-engineer for primary audit
2. Add compliance-officer if regulatory concerns
3. Generate test scenarios for findings
4. Store critical findings in wicked-brain:memory

---

## Architecture Design

**Task signals**: "design", "architecture", "system design", "how should we build"

| Need | Capability Type | Options |
|------|-----------------|---------|
| Solution design | Agent | wicked-garden:engineering:solution-architect |
| Data modeling | Agent / Skill | wicked-garden:data:data-engineer (or data skill inline) |
| Store decisions | Skill | wicked-brain:memory |
| Document design | Agent | wicked-garden:engineering:api-documentarian (or docs skill inline) |

**Recommended flow**:
1. Spawn solution-architect for high-level design (it covers persistence/data shape too)
2. Store decisions in wicked-brain:memory
3. Document via api-documentarian or the engineering docs skill inline

---

## Bug Investigation

**Task signals**: "bug", "error", "broken", "not working", "investigate"

| Need | Capability Type | Options |
|------|-----------------|---------|
| Debugging | Skill | engineering debugging skill (inline root-cause analysis) |
| Error tracking | MCP | sentry, datadog, rollbar |
| Logs/traces | Skill | platform errors skill (inline) |
| Codebase exploration | Agent | Explore |
| Track fix | MCP | atlassian, github issues |

**Recommended flow**:
1. Check error tracking MCP for context
2. Run the engineering debugging skill inline for systematic investigation
3. Use Explore agent to understand code paths
4. Track fix in issue tracker

---

## Feature Implementation

**Task signals**: "implement", "build", "add feature", "create"

| Need | Capability Type | Options |
|------|-----------------|---------|
| Requirements clarity | Agent | wicked-garden:product:requirements-analyst |
| Design guidance | Agent | wicked-garden:engineering:solution-architect |
| Implementation | Agent | wicked-garden:crew:implementer |
| Test strategy | Agent | wicked-testing:test-strategist |
| Track progress | MCP/Native | atlassian, TaskCreate/TaskUpdate |

**Recommended flow**:
1. Clarify requirements with requirements-analyst if vague
2. Get design guidance from solution-architect
3. Implement with crew:implementer; plan tests with wicked-testing:test-strategist
4. Track via native TaskCreate or issue tracker

---

## Documentation

**Task signals**: "document", "write docs", "README", "API docs"

| Need | Capability Type | Options |
|------|-----------------|---------|
| Technical writing | Skill | engineering docs skill (inline narrative docs) |
| API documentation | Agent | wicked-garden:engineering:api-documentarian |
| Publish docs | MCP | confluence, notion |
| Code understanding | Agent | Explore |

**Recommended flow**:
1. Use Explore to understand what needs documenting
2. Dispatch api-documentarian for API/reference docs; run the docs skill inline for narrative docs
3. Publish via documentation MCP if available

---

## Data Analysis

**Task signals**: "analyze data", "query", "metrics", "report"

| Need | Capability Type | Options |
|------|-----------------|---------|
| Data exploration | Agent / Skill | wicked-garden:data:data-engineer (or data skill inline) |
| Query execution | MCP | snowflake, bigquery, databricks |
| Local file analysis | Skill | data |
| Visualization guidance | Skill | data analysis skill (inline) |

**Recommended flow**:
1. Check for data warehouse MCP
2. If available, use for queries
3. If not, use the data skill for local files
4. Dispatch data-engineer (or run the data analysis skill inline) for interpretation

---

## Incident Response

**Task signals**: "incident", "outage", "production issue", "pages"

| Need | Capability Type | Options |
|------|-----------------|---------|
| Incident triage | Command/Skill | /wicked-garden:platform:incident (incident archetype, inline) |
| Error context | MCP | sentry, datadog |
| Log analysis | Skill | platform errors / observability skills (inline) |
| Communication | MCP | slack, teams |
| Post-mortem | Skill | wicked-brain:memory |

**Recommended flow**:
1. Run /wicked-garden:platform:incident (or the incident archetype) immediately
2. Pull context from observability MCP
3. Communicate status via chat MCP
4. Store learnings in wicked-brain:memory

---

## Test Planning

**Task signals**: "test", "QA", "test strategy", "what to test"

| Need | Capability Type | Options |
|------|-----------------|---------|
| Test strategy | Agent | wicked-garden:crew:gate-adjudicator |
| Test generation | Agent | wicked-garden:crew:implementer |
| TDD guidance | Agent | wicked-testing:test-strategist |
| Risk assessment | Agent | wicked-garden:platform:security-engineer |

**Recommended flow**:
1. Spawn gate-adjudicator to identify what to test
2. Use security-engineer for risk priority
3. Generate tests with implementer

---

## Quick Reference Matrix

| Task Type | Primary Agent | Supporting | MCP Needs |
|-----------|---------------|------------|-----------|
| Code review | crew:reviewer | security-engineer | github/gitlab |
| Security audit | security-engineer | compliance-officer | - |
| Architecture | solution-architect | data-engineer | - |
| Bug fix | engineering debugging skill (inline) | platform errors skill | error tracking |
| Feature | requirements-analyst | solution-architect | project mgmt |
| Docs | api-documentarian | engineering docs skill (inline) | confluence |
| Data | data-engineer | data skill (inline) | warehouse |
| Incident | platform incident (inline) | observability skill | observability |
| Testing | wicked-testing:test-strategist | - | - |

## When Capabilities Aren't Available

If recommended capability isn't available:

| Missing | Fallback |
|---------|----------|
| Domain agent | Use Explore + manual analysis |
| MCP integration | Use built-in tools + manual steps |
| Specific skill | Check for similar skill or use general approach |

Always note gaps in recommendations so user knows what's missing.
