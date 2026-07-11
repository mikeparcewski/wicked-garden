# Run Workflow — operational runbook

How to run a user-invoked deliberation end-to-end. The five lenses, the brief
template, and the domain lens refs live in `SKILL.md` — this ref covers only
the operational steps around them. Works for bugs, features, content, design,
architecture — anything.

## Arguments

- `description` (required): Issue description, GitHub issue number (e.g., `#42`), or quoted text
- `--deep`: Run blast-radius and lineage analysis for affected areas
- `--batch`: Process multiple issues (comma-separated numbers)

## Steps

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

**Search for affected areas**:
- Extract key references from the description
- Use `wicked-brain:search` for symbol search
- If `--deep` flag: use the `wicked-garden-search` skill's `blast-radius` action on key symbols

**Recall relevant memories**:
```
Skill(skill="wicked-brain:memory", args="\"{key terms}\" --limit 5")
```

### 3. Detect Context and Load Lens

Determine what kind of work this is (code, content, design, architecture, or mixed) and load the appropriate domain lens from this skill's refs:

- Code changes → `refs/code-lens.md`
- Content/docs → `refs/content-lens.md`
- Design/UX → `refs/design-lens.md`
- Architecture/system → `refs/architecture-lens.md`

Multiple lenses can apply. Load what's relevant.

### 4. Apply Five Lenses

Dispatch to an Explore agent for thorough analysis. Do NOT restate the five
lenses in the prompt — instruct the subagent to load them from this skill:

```
Task(
  subagent_type="Explore",
  prompt="Analyze this work request through the five-lens deliberate framework.
Load the wicked-garden-deliberate skill (skills/deliberate/SKILL.md) and apply
its five lenses ('Is This Real?', 'What's Actually Going On?', 'What Else Can
We Fix While We're Here?', 'Should We Rethink the Design?', 'Is There a Better
Way?') exactly as defined there. Read relevant files to ground your analysis.

REQUEST: {title}
DESCRIPTION: {body}
AFFECTED AREAS: {files/pages/components from context gathering}
CONTEXT TYPE: {code/content/design/architecture}
RELEVANT LENS REFS: {the refs selected in Step 3 — load these too}

Return a structured Deliberation Brief (template in the skill's SKILL.md) with:
- Assessment (validity, root cause, blast radius)
- Opportunities (cleanup, generalization, rethink)
- Recommendation (fix/redesign/generalize/defer/close + rationale)
- Scope change (expand/contract/same)
- Guidance (specific next steps)"
)
```

### 5. Present Deliberation Brief

Format the agent's findings using the **Deliberation Brief** template from
`SKILL.md` (Assessment / Opportunities / Recommendation / Guidance).

### 6. Store Deliberation

Store as a memory for future reference:

```
Skill(skill="wicked-brain:memory", args="\"Deliberation: {title} — {strategy}: {one-line rationale}\" --type decision --tags deliberation,{project}")
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

Invoke the `wicked-garden-deliberate` skill with:

```
"Auth tokens expire too early on mobile"
#281
--batch "280,281"
--deep "Navigation feels confusing on the settings page"
"README is outdated and contradicts the API docs"
```
