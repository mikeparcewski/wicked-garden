---
description: Show available agentic architecture commands and usage
---

# /wicked-garden:agentic:help

Display usage information and examples.

## Instructions

Show the following help information:

```markdown
# wicked-agentic Help

Design, review, and audit agentic AI systems — agent topologies, trust boundaries, framework selection, and safety validation.

## Commands

| Command | Description |
|---------|-------------|
| `/wicked-garden:agentic:ask <question>` | Ask about agentic patterns, frameworks, and best practices |
| `/wicked-garden:agentic:audit [path]` | Deep trust and safety audit with risk classification and compliance |
| `/wicked-garden:agentic:design [description]` | Interactive architecture design with pattern recommendations |
| `/wicked-garden:agentic:frameworks` | Research, compare, and select agentic frameworks |
| `/wicked-garden:agentic:review [path]` | Full codebase review with agent topology analysis |
| `/wicked-garden:agentic:help` | This help message |

## Quick Start

```
/wicked-garden:agentic:ask "when should I use multi-agent vs single agent?"
/wicked-garden:agentic:design "customer support bot with escalation"
/wicked-garden:agentic:review ./agents --quick
```

## Examples

### Framework Comparison
```
/wicked-garden:agentic:frameworks --compare langgraph,crewai --language python
```

### Safety Audit
```
/wicked-garden:agentic:audit ./src --standard SOC2 --scenarios
```

### Architecture Design
```
/wicked-garden:agentic:design "multi-agent code review pipeline" --output design.md
```

## Integration

- **wicked-engineering**: Architecture patterns and code review
- **wicked-qe**: Test strategy for agent systems
- **wicked-platform**: Security and compliance validation
- **wicked-crew**: Specialist routing for agentic architecture phases
```
