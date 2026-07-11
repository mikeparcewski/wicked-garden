# Action stub: {{command_name}} (dispatches to a fork worker)

Skills-only layout: a former "command that dispatches to an agent" is now an
ACTION of a consolidated per-domain router skill (skills/{domain}/SKILL.md)
that dispatches to a context:fork WORKER skill. Copy this section into the
router's body (and add a row to its Action router table); there is no
commands/ file.

## Action: {{command_name}}

{{description}}.

### 1. Parse arguments

Extract from the invocation args:
- `target` (required): the target to analyze
- `--option` (optional): additional options

### 2. Dispatch to the {{agent_name}} fork worker

```
Skill(
  skill="{{plugin_name}}-{{agent_name}}",
  args="{{agent_task_description}} | target: <target> | focus: <checklist>"
)
```

`{{plugin_name}}-{{agent_name}}` is the dash-qualified worker skill name
(e.g. `wicked-garden-engineering-solution-architect`). The worker returns
findings as structured markdown with file:line references.

### 3. Present results

```markdown
## {{command_name}}: <target>

### Summary
<worker findings summary>

### Details
<structured findings>

### Recommendations
1. <action item>
```
