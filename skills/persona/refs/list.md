# persona list — Discover Available Personas

Full output contract for the `list` action of the consolidated `wicked-garden-persona` skill (former `commands/persona/list.md`). Discover all
available personas — built-in specialists, custom personas, and cached personas.

## Arguments

Parse from the args passed to the `list` sub-action:

- `--role` (optional): Filter by role category (e.g., engineering, devsecops, product, quality-engineering)

## Execution

### Step 1: Fetch persona list

Build the command with optional role filter:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" \
  scripts/persona/registry.py --list [--role "${role}"] --json
```

If `--role` is present in the args, include `--role <value>` in the command.

### Step 2: Format output

Present the front door first, then personas grouped by **value tier**, not just by
source. Each row MUST include the exact invocation so no separate
documentation lookup is needed.

**Front door (always show first):**

```markdown
## Personas

The high-leverage move is your OWN house persona that encodes a failure-mode
defense. Start here:

- Define one: `/wicked-garden-persona define <name> --focus "<focus>" --constraints "FAILURE MODE — …"`
- Then invoke: `/wicked-garden-persona as <name> <task>`
```

**Value tiers.** A persona is **Methodology** if its registry record carries a
non-empty `constraints` list (it defends a named failure mode / hard constraint).
Otherwise it is **Generic** (a role restatement the base model largely already
supplies). Compute this from the `constraints` field returned by the registry;
do not hardcode the split.

The curated built-in surface is intentionally **small**: only the three
methodology exemplars below carry rich profiles. A blinded lift eval
(`tests/persona/EVAL_RESULTS.md`, 2026-06-12) found the built-in personas
produce **lift=0** vs the base model, so the generic role personas were demoted
to **thin role records** — still invokable, but with no curated constraints (the
base model already plays those roles). The real product is the `define` action.

```markdown
### Methodology personas (carry a failure-mode defense — prefer these)
| Name | Focus | Invoke |
|------|-------|--------|
| platform | Security, blast radius, secret handling... | `/wicked-garden-persona as platform <task>` |
| qe | Test value, recovery paths, anti-happy-path... | `/wicked-garden-persona as qe <task>` |
| agentic | Agent safety, termination, idempotency... | `/wicked-garden-persona as agentic <task>` |

### Generic personas (thin role lens — base model already plays these)
<details><summary>Show generic role names (no curated constraints — define your own for lift)</summary>

These names still resolve (engineering, product, data, jam) but carry no curated
profile — they apply the role as a plain lens. For durable value, define a HOUSE
persona instead. Any unlisted role name falls back gracefully (the `as` action
lists what's available rather than crashing).

| Name | Focus | Invoke |
|------|-------|--------|
| engineering | Code quality, architecture... | `/wicked-garden-persona as engineering <task>` |
| product | Requirements, UX, business value... | `/wicked-garden-persona as product <task>` |
| data | Pipelines, ML guidance, analytics... | `/wicked-garden-persona as data <task>` |
| jam | Ideation, multi-perspective... | `/wicked-garden-persona as jam <task>` |
</details>

### Custom Personas
| Name | Focus | Invoke |
|------|-------|--------|
| pragmatic-tech-lead | Delivery over perfection | `/wicked-garden-persona as pragmatic-tech-lead <task>` |

### Cached Personas (cross-project)
| Name | Focus | Invoke |
|------|-------|--------|
| my-persona | Shared focus | `/wicked-garden-persona as my-persona <task>` |
```

Rules:
- **Tier split is data-driven**: a persona with a non-empty `constraints` list is
  Methodology; one with an empty `constraints` list is Generic. Custom personas
  follow the same rule.
- Generic, custom, and cached sections render inside a `<details>` block (collapsed)
  so the methodology tier and the define front door are what the user sees first.
- Truncate the focus/description column at 60 characters if needed (add "...")
- Only show sections that have personas (omit Custom and Cached sections if empty)
- If `--role` was specified and returns zero results, show: "No personas found with role '{role}'."
- Fallback personas (architect, skeptic, advocate) are shown in a "### Fallback Personas" section when specialist.json is unavailable. `skeptic` is Methodology (it carries constraints); `architect` and `advocate` are Generic.

### Step 3: Show tip

After the table(s), add:

```
**Tip:** The highest-leverage persona is your own — one that encodes a house
failure-mode defense the base model won't volunteer:
`/wicked-garden-persona define <name> --focus "<focus>" --constraints "FAILURE MODE — …" --not-focus "…"`.
Use the engineering domain's review action with `--persona <name>` to route a
code review through any persona's lens.
```
