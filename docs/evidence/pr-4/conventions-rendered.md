# wicked-garden Discovery Conventions

EPIC: #601
Version: v9
Status: Authoritative

---

## The principle: skills are guidance, not infrastructure

A wicked-garden skill is not a library to import or a command to invoke via
toolchain. It is a piece of text that Claude reads at the moment of decision.
When Claude reaches for a skill, it does so because the skill's description
matched the internal phrase Claude was already forming — "I need to ground
myself," "I should deliberate on this before acting," "I want to search the
codebase for symbols."

This means the **description is the entire discovery surface**. The skill body
matters for execution quality. The description determines whether Claude ever
reaches the body at all.

v9 thesis: skills that fail the discovery test are friction, not value. They
occupy Claude's context, generate noise in the skill list, and slow routing.
The cut criterion is binary: does this skill provide value Claude cannot get
from native tools (Bash, Grep, Read, Edit, Task, Agent) or from another
well-positioned skill? If no, delete it. If yes, audit the description for
discovery-shape.

---

## What Claude looks for in a skill description

Five rules, in order of importance:

### 1. Trigger language ("Use when X")

The description must contain explicit trigger phrases matching how Claude
frames problems internally. Claude does not search for skill names — it matches
the mental phrasing at the moment of need.

Good: `Use when: getting mixed signals from the codebase, about to commit to a non-obvious decision`
Bad: `Provides contextual grounding via brain and bus integrations`

The second form describes what the skill does. The first form matches when
Claude would reach for it.

### 2. Anti-trigger language ("NOT for Z")

Every skill must declare what it is NOT for. This prevents mis-routing to
high-cost skills when a cheaper native tool would serve.

Good: `NOT for: routine "what does this code do" questions (use Read or Grep), broad codebase exploration (use Agent(Explore))`
Bad: (no anti-trigger — skill is used for everything vaguely related)

Anti-triggers are as important as triggers. Without them, a skill with broad
trigger language gets invoked in cases where Grep in one call would have been
faster.

### 3. No-wrapper test (does Bash + Grep + Read solve it in 3 calls?)

Before authoring a skill, ask: can a competent Claude with native tools solve
this in three calls or fewer? If yes, the skill is a wrapper — it adds friction
instead of reducing it. The wrapper test catches skills that merely describe
an existing tool's behavior in different words.

Failing examples from the v9 audit:
- `search:code` — wraps `wicked-brain:search`. One Skill call replaces it.
- `search:scout` — described as "quick pattern recon without index." That is Grep.
- `mem:store` — admitted in its own body as "thin wrapper over wicked-brain-memory."

### 4. Single-purpose, verb-first, scoped

A skill that does more than one thing is a junk drawer. Claude cannot route to
a junk drawer with confidence because the trigger language must be broad to
cover all uses, which means it matches everything and helps nothing.

Good name shape: `ground`, `deliberate`, `wickedizer`
Bad name shape: `smaht:context` (does context assembly AND enrichment AND
  event-import routing depending on args), `data:data` (name is meaningless)

Verb-first in the description body: "Pull deeper context from brain + bus when
uncertain" (verb: Pull). Not: "A skill that provides contextual grounding."

### 5. Progressive disclosure (SKILL.md ≤200 lines, refs/ for depth)

The SKILL.md entry point is the overview + quick-start + protocol. Detailed
mechanics belong in `refs/` files loaded on demand. A 400-line SKILL.md
signals a skill trying to do too much — split it or prune it.

Size constraint enforced by `/wg-check`: skills exceeding 200 lines will flag.

---

## Description template (use this verbatim shape)

```yaml
---
name: {verb-or-noun-phrase}   # kebab-case, max 64 chars
description: |
  {One-sentence verb-first summary of what the skill does.}
  Use when: {trigger phrase 1}, {trigger phrase 2}, {trigger phrase 3}.
  {Optional: one sentence on what it returns or outputs.}

  NOT for: {anti-trigger 1} (use {native tool or other skill}), {anti-trigger 2}
  (use {alternative}).
portability: portable   # or: wicked-garden-only if it requires plugin internals
---
```

### Example (from `skills/ground/SKILL.md`)

```yaml
---
name: ground
description: |
  Pull deeper context from brain + bus when uncertain. Use when: getting mixed signals
  from the codebase, about to commit to a non-obvious decision, prior decisions might
  exist for this exact problem, or you want to verify an assumption before action.
  Returns relevant brain memories, recent bus events, and linked priors ranked by
  relevance — not a wall of text.

  NOT for: routine "what does this code do" questions (use Read or Grep), broad
  codebase exploration (use Agent(Explore)), or fetching specific symbols (use
  wicked-brain:search directly).
portability: portable
---
```

---

## Good vs Bad — concrete examples from the v9 audit

### Pair 1: Trigger language

**Bad** (`smaht/SKILL.md` original):
```
description: |
  On-demand context assembly over wicked-brain + wicked-garden:search. v6 replaced
  the v5 push-model orchestrator (deleted in #428) with a pull-model skill...
```
Problem: leads with implementation history. Claude does not think "I need
context assembly via a pull model" — Claude thinks "catch me up" or "what do
we know about X."

**Good** (sharpened form):
```
description: |
  Catch up on what the system knows about a topic. Use when: "resume where we left
  off", "what happened before", "catch me up", "what do we know about X".
  NOT for: real-time event queries (use wicked-bus:query), symbol search
  (use wicked-brain:search directly).
```

### Pair 2: Wrapper vs unique value

**Bad** (`search:scout` — now cut):
```
description: Quick pattern recon without building the index. Grep-like but
  domain-aware.
```
Problem: Grep is already domain-aware when given the right path. This skill
exists to describe Grep with extra words.

**Good** (`search:lineage` — kept as-is):
```
description: Trace data flow from UI event to database column. Use when you
  need to understand end-to-end data movement across service boundaries.
  NOT for: single-file symbol lookup (use wicked-brain:search).
```
Passes the no-wrapper test: no combination of Bash + Grep + Read in three calls
produces a cross-service lineage graph.

### Pair 3: Junk drawer vs single purpose

**Bad** (`data:data` — name and description both fail):
```
name: data
description: Data engineering ops — profile datasets, validate schemas, run
  quality checks, transform pipelines, analyze lineage, review ML models.
```
Problem: six distinct purposes. Claude cannot route to this reliably because
"analyze lineage" has a better match in `search:lineage` and "review ML models"
has a better match in `data:ml`.

**Good** (split verdict: rename `data:data` → `data:profile`, cut `data:numbers`):
```
name: data-profile
description: |
  Profile a dataset: row counts, null rates, type distributions, value ranges.
  Use when: "describe this CSV", "what does this table look like", "data quality
  check", "schema validation". NOT for: pipeline design (use data:pipeline),
  ML model review (use data:ml), SQL queries (use Bash + duckdb).
```

### Pair 4: Anti-trigger prevents mis-routing

**Bad** (`crew:archive` before sharpening):
```
description: Archive a completed crew project.
```
Problem: no anti-trigger. Gets invoked during active projects when users say
"wrap this up" — wrong phase entirely.

**Good** (sharpened):
```
description: |
  Archive a finished crew project to free it from the active project list.
  Use when: project is at status=completed and you want to retire it from view.
  NOT for: mid-project state saves (use crew:status), project deletion
  (there is no delete — archive is permanent).
```

### Pair 5: Size discipline

**Bad** (any SKILL.md > 200 lines that could shed refs):
A SKILL.md with 340 lines including an embedded 60-line ARCHITECTURE section and
three code samples. The code samples belong in `refs/implementation.md`.

**Good** (`deliberate/SKILL.md`): 124 lines. Five lenses defined concisely.
Depth links: `refs/opportunity-patterns.md`, `refs/rethink-framework.md`.
Everything Claude needs to invoke the skill correctly is in the SKILL.md.
Everything an engineer needs to understand how a lens works is in refs/.

---

## Common failure modes

### Trigger-language drift

The description says WHAT the skill does, not WHEN to use it. "Provides
contextual grounding via brain and bus integrations" describes the mechanism.
"Use when getting mixed signals from the codebase" matches the mental phrase.
Drift accumulates as skills are maintained — every time someone edits the
body, the description grows more technical and less trigger-shaped.

Fix: read the description aloud as if you were telling Claude "reach for this
when..." and rewrite it to complete that sentence naturally.

### Wrapper skills

The skill describes something Claude or a native tool already does, just with
different words. The tell: the body's "Step 1" is always the same native tool
call with slightly different parameters. The entire skill reduces to "call
wicked-brain:search with this query shape" — which is what wicked-brain:search
already does.

Fix: apply the no-wrapper test before authoring. If Bash + Grep + Read in
three calls solves it, close the file.

### Multi-purpose junk drawers

A skill that handles three different workflows via args or branching logic.
The trigger language has to be broad to match all three, which means it matches
cases where two of the three workflows are wrong. The skill gets invoked
speculatively and wastes tokens on the preamble before Claude realizes it
matched the wrong branch.

Fix: split into single-purpose skills. If the split produces two skills that
are each too thin to pass the no-wrapper test, that's evidence the original
skill should be cut entirely.

### Missing anti-triggers — mis-routing

A well-triggered skill with no anti-trigger language gets invoked in cases
where a cheaper tool would serve. The cost is latency + tokens on every
invocation. At scale (hundreds of sessions per week), this compounds.

Fix: for every trigger phrase, ask "what would NOT be a good use of this
skill?" Write those as the NOT for list. Minimum: one anti-trigger per skill.

---

## The unique-value test

Every new skill must answer this question before it ships:

> Does this provide value Claude can't get from native tools (Bash, Grep, Read,
> Edit, Task, Agent) OR from another well-positioned skill (wicked-brain:*,
> wicked-bus:*, figma:*, wicked-testing:*, etc.)?

If no: do not author it. The value proposition of wicked-garden is steering
Claude, not wrapping tools Claude can already use.

If yes: audit the description against the five rules above before committing.
Apply them in order — trigger language is the most important; size discipline
is the last check.

If uncertain: write the trigger phrases you would use, then check whether
an existing skill or native tool already matches those phrases. If yes, sharpen
the existing skill's trigger language instead of adding a new one.

---

## Canonical exemplar

`wicked-garden:ground` — see `/skills/ground/SKILL.md`.

This skill was authored as v9-PR-4's keystone: the single most important new
skill in the v9 surface reduction. It demonstrates every rule from this doc:

- Trigger language matches Claude's internal phrasing at the moment of uncertainty
- Anti-triggers prevent mis-routing to expensive grounding when Grep would serve
- Single purpose: pull + rank + cap. Not "context assembly + enrichment + history"
- Progressive disclosure: body is the protocol; no refs/ needed (simple enough)
- Passes the no-wrapper test: the parallel brain+bus fan-out + ranked synthesis
  cap is behavior Claude cannot reproduce in three native tool calls

New skill authors should read `skills/ground/SKILL.md` frontmatter as the gold
standard shape before authoring any new skill.

---

## Where this lives

`docs/v9/discovery-conventions.md`

Referenced from:
- v9 epic #601 (acceptance criterion for v9-PR-4)
- `skills/ground/SKILL.md` is the canonical exemplar this doc points to

Maintained by: wicked-garden maintainers. Update this doc when the discovery
model changes. Do not let skill bodies drift from these conventions without
updating this doc first — the conventions are only as good as the exemplars
that demonstrate them.
