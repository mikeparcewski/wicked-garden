# Wicked-Crew v3 Degradation Paths

How wicked-crew behaves when components are unavailable.

## Specialist Unavailability

When a recommended specialist plugin is not installed, crew falls back to built-in agents.

### Specialist → Fallback Agent Mapping

| Specialist | Fallback | Capabilities Preserved | Capabilities Lost |
|------------|----------|------------------------|-------------------|
| wicked-jam | facilitator | Basic brainstorming, perspective gathering | Dynamic persona assembly, multi-round discussion |
| wicked-qe | reviewer | Basic review checklist | Gate framework, test scenario generation, risk matrix |
| wicked-product | reviewer | Code review, issue detection | Multi-perspective Reflexion pattern, judge synthesis |
| wicked-analyst | researcher | Codebase exploration | Deep pattern analysis, data-driven insights |
| wicked-engineering | implementer | Code implementation | Architecture guidance, pattern enforcement |
| wicked-platform | implementer | Basic implementation | CI/CD automation, security scanning, deployment |
| wicked-delivery | (none) | Project files persist | Reporting, cross-project analytics |
| wicked-platform | reviewer | Basic compliance checklist | Regulatory framework knowledge, audit prep |

### Event Emission

When fallback occurs, crew emits:

```json
{
  "event": "crew:specialist:unavailable:warning",
  "context": {
    "specialist_needed": "wicked-product",
    "fallback_agent": "reviewer",
    "capabilities_degraded": ["multi-perspective review", "reflexion pattern"]
  }
}
```

## Utility Plugin Unavailability

### wicked-kanban unavailable

**Impact**: No persistent board, no rich task tracking

**Fallback**:
- Use TodoWrite for in-session tracking
- Tasks stored in markdown files: `~/.something-wicked/wicked-crew/projects/{name}/tasks/`

**Event**: `crew:kanban:unavailable:warning`

### wicked-mem unavailable

**Impact**: No cross-session memory, no decision recall

**Fallback**:
- Project files provide local context
- Decisions documented in `phases/{phase}/decisions.md`

**Event**: `crew:mem:unavailable:warning`

### wicked-cache unavailable

**Impact**: No caching of analysis results

**Fallback**:
- Re-run smart decisioning on each command
- No performance impact (analysis is fast)

**Event**: None (silent degradation)

## Phase-Specific Degradation

### Clarify Phase (no wicked-jam)

**Full capability**:
```
/wicked-jam:brainstorm "{topic}"
→ 4-6 personas, 2-3 rounds, synthesis
```

**Degraded**:
```
Task(subagent_type="wicked-crew:facilitator",
     prompt="Guide outcome clarification")
→ Sequential questions, single-perspective synthesis
```

### Design Phase (no wicked-product)

**Full capability**:
```
/wicked-product:strategy design/ --perspectives architecture
→ Multi-perspective review with Reflexion pattern
```

**Degraded**:
```
Task(subagent_type="wicked-crew:researcher",
     prompt="Research design patterns")
→ Basic pattern search and documentation
```

### QE Phase (no wicked-qe)

**Full capability**:
```
/wicked-qe:analyze --gate strategy
→ Test strategist, risk assessor, gate decision
```

**Degraded**:
```
Inline test strategy creation
→ Basic scenarios from success criteria
→ No risk matrix or gate framework
```

### Build Phase (no wicked-platform, no wicked-kanban)

**Full capability**:
```
Kanban board + devsecops automation
→ Task tracking, CI/CD, security scans
```

**Degraded**:
```
TodoWrite + basic implementation
→ In-session progress tracking
→ Manual git operations
```

### Review Phase (no wicked-product, no wicked-qe)

**Full capability**:
```
Multi-specialist review
→ Security, quality, architecture perspectives
```

**Degraded**:
```
Task(subagent_type="wicked-crew:reviewer",
     prompt="Review against outcome")
→ Single-perspective review
```

## Graceful Degradation Principles

1. **Always functional**: Core workflow works without any specialists
2. **Transparent**: User informed of capabilities available/missing
3. **Additive value**: Each specialist adds capability but isn't required
4. **No hard failures**: Missing plugin = degraded experience, not error
5. **Progressive enhancement**: As plugins are installed, capabilities grow

## Testing Scenarios

To verify degradation behavior:

### Scenario 1: No specialists installed

```bash
# Remove all wicked-* from plugin cache
claude --no-plugins /wicked-crew:start "Add auth to API"
```

Expected:
- Project created with built-in agents
- Signal analysis still runs
- Event: `crew:specialist:unavailable:warning` for each

### Scenario 2: Partial specialists

```bash
# Only wicked-qe installed
claude /wicked-crew:start "Add auth to API"
```

Expected:
- QE specialist engaged for relevant phases
- Other phases use fallback agents
- Mixed events: `engaged:success` + `unavailable:warning`

### Scenario 3: All specialists, no utilities

```bash
# wicked-kanban and wicked-mem not installed
claude /wicked-crew:start "Add auth to API"
```

Expected:
- Full specialist engagement
- Tasks tracked via TodoWrite
- Decisions stored in project files
