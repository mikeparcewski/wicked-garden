---
description: Show available crew workflow commands and usage
---

# /wicked-garden:crew:help

Display usage information and examples.

## Instructions

Show the following help information:

```markdown
# wicked-crew Help

Dynamic multi-phase workflow engine with signal-based specialist routing. Crew analyzes your project, selects phases, and engages the right specialists automatically.

## Commands

| Command | Description |
|---------|-------------|
| `/wicked-garden:crew:start <description>` | Start a new project with outcome clarification |
| `/wicked-garden:crew:execute` | Execute current phase work with adaptive role engagement |
| `/wicked-garden:crew:approve <phase>` | Approve a phase and advance to next stage |
| `/wicked-garden:crew:gate [target]` | Run QE gate analysis with configurable rigor |
| `/wicked-garden:crew:status` | Show current project status, phase, and next steps |
| `/wicked-garden:crew:evidence [task-id]` | Show evidence summary for a task or project |
| `/wicked-garden:crew:just-finish` | Execute remaining work with maximum autonomy |
| `/wicked-garden:crew:archive <project>` | Archive or unarchive a project |
| `/wicked-garden:crew:profile` | Configure preferences and working style |
| `/wicked-garden:crew:help` | This help message |

## Quick Start

```
/wicked-garden:crew:start "add OAuth2 login to the web app"
/wicked-garden:crew:execute
/wicked-garden:crew:approve clarify
```

## Workflow

1. **Start** a project — crew analyzes signals and selects phases
2. **Execute** each phase — specialists engage based on signal matching
3. **Approve** phases — checkpoints re-analyze and may inject new phases
4. **Gate** critical phases — QE validation before proceeding
5. **Just-finish** — hand off remaining work with full autonomy

## Options

- `--autonomy ask-first|balanced|just-finish`: Control how much crew asks vs decides
- `--style verbose|balanced|concise`: Output verbosity
- `--rigor quick|standard`: Gate analysis depth

## Integration

- **All specialist plugins**: Routed to automatically via signal analysis
- **wicked-kanban**: Task tracking synced via hooks
- **wicked-mem**: Context and decisions persisted across phases
- **wicked-smaht**: Context assembly for each phase
```
