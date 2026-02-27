---
description: Configure wicked-crew preferences and working style
argument-hint: [--autonomy ask-first|balanced|just-finish] [--style verbose|balanced|concise] [--plan-mode on|off]
---

# /wicked-garden:crew:profile

Configure engagement preferences for wicked-crew.

## Instructions

### 1. Parse Arguments

- `--autonomy`: ask-first | balanced | just-finish
- `--style`: verbose | balanced | concise
- `--review`: thorough | standard | quick
- `--plan-mode`: on | off (intercept EnterPlanMode and redirect to wicked-crew)

If no arguments, show current profile and offer to configure interactively.

### 2. Load or Create Profile

Profile location: `~/.something-wicked/wicked-crew/preferences.yaml`

Default profile:
```yaml
autonomy: balanced
communication_style: balanced
review_depth: standard
plan_mode_intercept: true
created: {date}
updated: {date}
```

### 3. Interactive Configuration (no args)

If called without arguments, ask user preferences:

```markdown
## wicked-crew Profile Configuration

### Autonomy Level

How should I engage during projects?

1. **ask-first**: Pause for approval at every decision
2. **balanced** (default): Proceed on minor decisions, ask on major ones
3. **just-finish**: Maximum autonomy with safety guardrails

Current: {current_value}
Choose (1/2/3):
```

Then:

```markdown
### Communication Style

How detailed should updates be?

1. **verbose**: Detailed explanations and context
2. **balanced** (default): Moderate detail
3. **concise**: Brief, essential information only

Current: {current_value}
Choose (1/2/3):
```

### Plan Mode Intercept

```markdown
### Plan Mode Intercept

Should wicked-crew intercept plan mode requests?

1. **on** (default): Redirect EnterPlanMode to wicked-crew for structured planning
2. **off**: Allow Claude's default plan mode

Current: {current_value}
Choose (1/2):
```

### 4. Update Profile

Save preferences:

```yaml
autonomy: {value}
communication_style: {value}
review_depth: {value}
plan_mode_intercept: {true|false}
updated: {date}
```

### 5. Display Confirmation

```markdown
## Profile Updated

| Setting | Value |
|---------|-------|
| Autonomy | {autonomy} |
| Communication | {style} |
| Review Depth | {review} |
| Plan Mode Intercept | {on/off} |

These preferences apply to all wicked-crew projects.

**Quick Update Examples:**
```
/wicked-garden:crew:profile --autonomy just-finish
/wicked-garden:crew:profile --style concise
/wicked-garden:crew:profile --plan-mode off
```
```

### Autonomy Level Details

| Level | Behavior |
|-------|----------|
| ask-first | Always ask before proceeding. Good for learning the workflow. |
| balanced | Ask for major decisions, proceed on minor ones. Default. |
| just-finish | Maximum autonomy. Only pause at guardrails. |

### Guardrails (apply at all levels)

These always require explicit approval:
- Deployments
- File deletions
- Security changes
- External service modifications
