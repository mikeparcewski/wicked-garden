---
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Task
  - Skill
  - AskUserQuestion
description: "Critically analyze any work request before implementation — challenge assumptions, find root causes, identify opportunities, and propose better approaches."
argument-hint: "<description or GH#number> [--deep] [--batch]"
---

# /wicked-garden:deliberate

Analyze any work request through the five-lens deliberate framework before jumping to implementation. Works for bugs, features, content, design, architecture — anything.

## Arguments

- `description` (required): Issue description, GitHub issue number (e.g., `#42`), or quoted text
- `--deep`: Run blast-radius and lineage analysis for affected areas
- `--batch`: Process multiple issues (comma-separated numbers)

## Instructions

### 1. Parse Input

If the argument is a GitHub issue number (`#N` or just a number):

```bash
gh issue view {number} --json title,body,labels,comments 2>/dev/null
```

Extract title, body, and any discussion context. If not a GH issue, use the raw description.

### 2. Gather Context

**Read project descriptors** (if they exist):
- `CLAUDE.md`, `README.md` for project context
- Recent git log for related changes:
  ```bash
  git log --oneline -20
  ```

**Search for affected areas** :
- Extract key references from the description
- Use `/wicked-garden:search:code` for symbol search
- If `--deep` flag: use `/wicked-garden:search:blast-radius` on key symbols

**Recall relevant memories**:
```
Skill(skill="wicked-garden:mem:recall", args="\"{key terms}\" --limit 5")
```

### 3. Detect Context and Load Lens

Determine what kind of work this is (code, content, design, architecture, or mixed) and load the appropriate domain lens from the deliberate skill refs:

- Code changes → `refs/code-lens.md`
- Content/docs → `refs/content-lens.md`
- Design/UX → `refs/design-lens.md`
- Architecture/system → `refs/architecture-lens.md`

Multiple lenses can apply. Load what's relevant.

### 4. Apply Five Lenses

Dispatch to an Explore agent for thorough analysis:

```
Task(
  subagent_type="Explore",
  prompt="Analyze this work request through five critical lenses. Read relevant files to ground your analysis.

REQUEST: {title}
DESCRIPTION: {body}
AFFECTED AREAS: {files/pages/components from context gathering}
CONTEXT TYPE: {code/content/design/architecture}

Apply each lens:

**Lens 1 — Is This Real?**
- Is this actually a problem, or working as intended?
- Is this a symptom or the root cause? Would fixing it just move the pain?
- What evidence exists? Observed or theoretical?
- What's the cost of doing nothing?

**Lens 2 — What's Actually Going On?**
- Trace to the real origin — don't stop at the first layer
- Is the framing itself wrong?
- What else shares the same root cause?

**Lens 3 — What Else Can We Improve?**
- Are adjacent areas suffering from the same weakness?
- Can we generalize instead of point-fixing?
- Is there duplication to consolidate?
- Would a structural change prevent similar asks?

**Lens 4 — Should We Rethink the Approach?**
- Would a different structure make this disappear?
- Are we patching around a flawed model?
- What would we build if starting fresh?

**Lens 5 — Is There a Better Way?**
- Can we solve by removing instead of adding?
- Can we solve with configuration instead of implementation?
- Is there a simpler approach that covers 90% of cases?

Return a structured Deliberation Brief with:
- Assessment (validity, root cause, blast radius)
- Opportunities (cleanup, generalization, rethink)
- Recommendation (fix/redesign/generalize/defer/close + rationale)
- Scope change (expand/contract/same)
- Guidance (specific next steps)"
)
```

### 5. Present Deliberation Brief

Format the agent's findings:

```markdown
## Deliberation Brief: {title}

### Assessment
**Validity**: {Real problem / Symptom / Not a problem / Wrong framing}
**Root cause**: {actual cause, not what was reported}
**Blast radius**: {what else is affected}

### Opportunities
**Cleanup**: {what can be improved alongside}
**Generalization**: {can we abstract or consolidate?}
**Rethink**: {should we redesign the approach?}

### Recommendation
**Strategy**: {Fix / Redesign / Generalize / Defer / Close}
**Rationale**: {why this approach over alternatives}
**Scope**: {Expand / Contract / Same — what changed from original ask}

### Guidance
{specific direction for whoever does the work}
```

### 6. Store Deliberation

Store as a memory for future reference:

```
Skill(skill="wicked-garden:mem:store", args="\"Deliberation: {title} — {strategy}: {one-line rationale}\" --type decision --tags deliberation,{project}")
```

### 7. Crew Integration

If a crew project is active, update the project with resolution findings:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/phase_manager.py {project} update \
  --data '{"deliberations": [{"issue": "{title}", "strategy": "{strategy}", "scope_change": "{change}"}]}' \
  --json
```

## Batch Mode

When `--batch` is used with multiple issue numbers:

1. Fetch all issues in parallel
2. Run the five-lens analysis on each
3. Cross-reference: do any issues share root causes?
4. Present a consolidated deliberation table with individual briefs

## Examples

```bash
/wicked-garden:deliberate "Auth tokens expire too early on mobile"
/wicked-garden:deliberate #281
/wicked-garden:deliberate --batch "280,281"
/wicked-garden:deliberate --deep "Navigation feels confusing on the settings page"
/wicked-garden:deliberate "README is outdated and contradicts the API docs"
```
