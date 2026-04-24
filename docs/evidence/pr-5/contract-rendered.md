# wicked-garden Drop-In Plugin Contract

EPIC: #601
Version: v9
Status: Authoritative

---

## The principle

Plugins are first-class. wicked-garden provides the philosophy and
unique-value core: crew orchestration, council, dynamic SDLC, brain+bus
integration, and the drop-in plugin contract itself. Plugins fill specialized
domains — testing, presentation, search, diagramming, whatever teams need.

No plugin should patch wicked-garden's internals to integrate. The contract
is entirely in the plugin's own files: its `plugin.json`, its skill
descriptions, and its bus event naming. wicked-garden discovers and respects
compliant plugins without coordination.

The corollary: wicked-garden never duplicates a plugin's value. When a
well-positioned plugin owns a domain (wicked-testing owns QE, figma owns
design, wicked-brain owns knowledge retrieval), wicked-garden surfaces it
via routing — not by adding parallel skills that compete.

---

## What a compliant plugin looks like

### 1. Skills use v9 discovery-shape descriptions

Every skill description in the plugin's `plugin.json` is the entire signal
Claude sees before deciding whether to invoke the skill. Shape it accordingly:

```yaml
description: |
  {One verb-first sentence — what the skill does.}
  Use when: {trigger phrase 1}, {trigger phrase 2}, {trigger phrase 3}.
  {Optional: one sentence on what it returns.}

  NOT for: {anti-trigger 1} (use {native tool or other skill}),
  {anti-trigger 2} (use {alternative}).
```

The five rules from `docs/v9/discovery-conventions.md` apply without
exception:

1. Trigger language matching Claude's internal phrasing (`Use when:`)
2. Anti-trigger language preventing mis-routing (`NOT for:`)
3. Passes the no-wrapper test (Bash + Grep + Read in 3 calls doesn't replicate it)
4. Single-purpose, verb-first, scoped
5. Progressive disclosure: SKILL.md ≤200 lines, refs/ for depth

See `docs/v9/discovery-conventions.md` for detailed guidance and bad/good
examples. This document references those rules — it does not repeat them.

### 2. `plugin.json` includes a scope statement

The manifest declares what the plugin owns. This is not metadata — it tells
wicked-garden's routing layer what to defer:

```json
{
  "name": "my-plugin",
  "version": "0.1.0",
  "description": "One sentence: what domain this plugin owns.",
  "skills": [...],
  "agents": [...],
  "commands": [...]
}
```

The `description` field at manifest level is the scope statement. It must
be specific enough to distinguish the plugin's domain from adjacent
wicked-garden pillars. "Quality engineering workflows" is specific.
"Tools for developers" is not.

### 3. Plugin skills do NOT duplicate wicked-garden core or native Claude tools

See the non-duplication rule section below.

### 4. Bus events use the canonical naming convention

Event names follow `{domain}:{action}:{outcome}` (lowercase, colon-separated):

```
wicked.teststrategy.authored    ✓
wicked.verdict.recorded         ✓
wicked.testrun.finished         ✓
MY_PLUGIN_RESULT                ✗  (wrong shape)
my-plugin:done                  ✗  (wrong separator)
```

Bus events are optional — a plugin that stores state locally and has no
cross-plugin coordination need does not have to emit events. But if it does,
the naming shape is required for wicked-garden's event adapter to pick them
up in crew context scoring.

### 5. Persistent state routes through wicked-brain:memory

Plugins that need cross-session persistence call `wicked-brain:memory`
(store mode) rather than maintaining their own memory system. This keeps
the knowledge graph unified — a decision stored by wicked-testing is
surfaced by `wicked-garden:ground` and by wicked-garden's brain adapter.

Plugins that maintain their own SQLite ledger for run data (like
wicked-testing's evidence store) are fine; that is domain-local operational
state, not the cross-session knowledge layer. The rule applies to
decisions, patterns, and architectural gotchas that other sessions should
find.

---

## The wicked-testing exemplar

wicked-testing (`/Users/michael.parcewski/Projects/wicked-testing`) is the
canonical compliant plugin. Every rule above has a live instance in its
codebase.

### Manifest-level scope

```json
{
  "name": "wicked-testing",
  "version": "0.3.3",
  "description": "Standalone QE library — 5-core testing surface
    (plan/authoring/execution/review/insight), SQLite ledger with
    fixed-SQL oracle, optional wicked-bus + wicked-brain integration."
}
```

The description declares exactly what it owns: the QE workflow surface,
the evidence ledger, the oracle. It says "standalone" — works without
wicked-garden. It says "optional integration" — respects when bus/brain
are absent. wicked-garden can read this description and know what to
defer to wicked-testing, and what NOT to duplicate.

### Exemplar skill descriptions

**`wicked-testing:plan`**

```
One skill for everything before tests get written. Figures out what to
test, what can go wrong, and whether the design lets you test at all.
When to use: before the build phase of a feature, when a PR's scope is
unclear and you need to know what to test, when acceptance criteria were
just drafted (requirements-quality gate), when a design doc is ready but
no code exists yet (testability gate).
```

Why it passes: single focus (pre-test planning), trigger language matches
the moment ("before the build phase", "AC just drafted"), anti-triggers
are implicit in the dispatch table (dispatches to specialist agents, not
general-purpose tools). Passes no-wrapper test — routes to four distinct
agents with domain context Claude cannot replicate inline.

**`wicked-testing:authoring`**

```
Turns a plan or a diff into runnable tests. Two modes: scenario
authoring (markdown files the executor runs later) and test code
generation (pytest / jest / etc. that runs in CI).
When to use: you have a strategy from wicked-testing:plan and need the
actual tests, you're mid-build and need unit / integration tests for the
last change, you need to convert an existing scenario into
framework-specific code, you need fixtures or anonymized sample data.
```

Why it passes: verb-first ("Turns a plan... into runnable tests"),
two concrete modes (no junk drawer — modes are complementary, not
orthogonal), trigger language matches build-phase moments, dispatch table
names specific agents per input type.

**`wicked-testing:execution`**

```
The doer. Takes a scenario or test command, runs it, captures
everything, writes the ledger entry. Evidence lives under
.wicked-testing/evidence/<run-id>/.
When to use: you have a scenario ready and need a real run with
evidence, you want to run the existing test suite and record the verdict
in the ledger, you're in a crew test phase and need all scenarios
executed.
```

Why it passes: single purpose (run + capture + record), trigger language
matches the crew test-phase moment, the evidence path is concrete so
callers know what they'll get. Passes no-wrapper test: the evidence
manifest, ledger write, and bus event chain cannot be reproduced in three
native tool calls.

**`wicked-testing:review`**

```
Reviewing is its own discipline. This skill is the place where verdicts
are rendered — not inside the executor, not as a side effect of running.
When to use: a run just finished and needs an independent verdict,
post-implementation: does the code actually match the spec?, the test
suite itself needs a quality pass, a code review needs a
testability-focused perspective.
```

Why it passes: the opening sentence is the design principle AND the
anti-trigger in one ("not inside the executor, not as a side effect").
Verdict independence is the unique value — Claude cannot self-grade with
scrubbed context natively. Trigger language maps to review-gate moments
in the crew SDLC.

**`wicked-testing:insight`**

Why it passes: scoped to the analytical surface (trend queries against
the SQLite ledger), not a duplicate of execution or review. The ledger
query is unique value — no native tool aggregates historical test runs.

### How wicked-testing plugs into crew phases

wicked-garden's `gate-policy.json` routes the test-strategy phase to
`wicked-testing:authoring` via the crew test-strategist dispatch (#595):
when a crew project reaches the build phase, the gate adjudicator checks
for a wicked-testing strategy artifact before approving advancement.

This integration requires zero changes to wicked-testing. The plugin
exposes `wicked-testing:plan` with trigger language matching "before the
build phase." The crew facilitator reads that trigger, dispatches the
skill, and the artifact lands in the evidence bundle.

### Bus event emission

wicked-testing emits on the wicked-bus when present:
`wicked.teststrategy.authored`, `wicked.scenario.authored`,
`wicked.testrun.started`, `wicked.testrun.finished`,
`wicked.evidence.captured`, `wicked.verdict.recorded`.

Events matching the active crew `chain_id` score 0.8+ in wicked-garden's
chain-aware smaht context assembly. A plugin that emits correctly becomes
part of the ambient context Claude sees at every turn.

---

## Registration and dispatch contract

### How Claude discovers plugin skills

At session start, the bootstrap hook reads all installed plugins'
`plugin.json` manifests and builds the skill registry. Skill descriptions
from the manifest are the discovery surface — Claude sees them when
selecting skills.

A plugin's skills are first-class entries in this registry. They compete
on description quality. A plugin with weak trigger language will be
underselected; a plugin with sharp v9-shaped descriptions will be reached
for at exactly the right moments.

There is no "register with wicked-garden" call. Compliant `plugin.json`
+ compliant skill descriptions = automatic discovery.

### How wicked-garden dispatches TO plugins

wicked-garden dispatches to plugins via the standard `Task` tool with the
plugin's `subagent_type`:

```
Task(
  subagent_type="wicked-testing:test-strategist",
  prompt="Generate a test strategy for {target}..."
)
```

The `subagent_type` must match a name declared in the plugin's `agents`
array in `plugin.json`. wicked-garden's facilitator reads agent frontmatter
to route — the plugin's agents are discovered exactly like wicked-garden's
own agents.

For skill invocations (not subagent dispatch), wicked-garden uses the
`Skill` tool:

```
Skill(wicked-testing:plan, target="{path}")
```

The skill name must match `plugin.json`'s `skills[].name` exactly.

### How plugins dispatch back

A plugin that produces a verdict or evidence artifact writes it to a
path and returns the path. wicked-garden's gate adjudicator reads from
that path. The dispatch-back contract is:

1. **Verdict**: return a structured object with `verdict` (PASS / FAIL /
   CONDITIONAL / N-A / SKIP / INCONCLUSIVE) and `evidence_path`.
2. **Evidence path**: a relative path under `.wicked-testing/evidence/`
   or the plugin's equivalent evidence root.
3. **Bus event** (optional): emit `{domain}.verdict.recorded` with
   `chain_id` matching the caller's active chain.

wicked-garden's gate adjudicator accepts any `verdict` from a registered
plugin agent. It does not require a specific return format beyond the
fields above.

---

## The non-duplication rule

Plugins MUST NOT author skills that duplicate:

- **Native Claude tools**: Bash, Read, Edit, Grep, Task, Agent. If a
  skill's entire body reduces to "call Bash with these args" or
  "call Grep with this pattern," it is a wrapper. Cut it.
- **wicked-garden core surfaces**: the five unique-value pillars (crew
  orchestration, council, dynamic SDLC, brain+bus integration, drop-in
  plugin contract). A plugin must not add a "plan my sprints" skill that
  re-implements the facilitator rubric, or a "multi-model verdict" skill
  that re-implements `jam:council`.
- **Another well-positioned plugin**: if wicked-testing owns QE,
  figma owns design, and wicked-brain owns knowledge retrieval, a new
  plugin must not add QE / design / retrieval skills without a
  demonstrably distinct value proposition.

The test is the same one applied in the v9 audit:

> Does this provide value Claude can't get from native tools (Bash, Grep,
> Read, Edit, Task, Agent) OR from another well-positioned skill?

If no: do not author it. The plugin's value proposition is the specialized
domain it owns, not the general-purpose infrastructure it wraps.

### What this looks like in practice

**CUT**: A plugin proposes a skill `smart-git` that "summarizes recent
commits with context." Claude can do this: `Bash("git log --oneline -20")`
+ one sentence of synthesis. The skill is a wrapper. Cut it.

**KEEP shape for the same domain**: A plugin proposes `release-impact` that
"traces which test scenarios were authored against tickets in the last
release, identifies scenarios with no coverage, and cross-references the
commit graph against the evidence ledger." This cannot be replicated in
three native tool calls — it requires a graph traversal over cross-plugin
data. This passes.

See `docs/evidence/pr-5/non-duplication-sample.md` for a worked example.

---

## Authoring checklist

Before opening a plugin PR or marketplace submission:

- [ ] Every skill description passes the five v9 discovery conventions
      (see `docs/v9/discovery-conventions.md`)
- [ ] No skill wraps a native tool (apply the no-wrapper test: Bash +
      Grep + Read in three calls does not replicate the skill's value)
- [ ] No skill duplicates an existing well-positioned plugin or
      wicked-garden core pillar
- [ ] SKILL.md is ≤200 lines; depth detail is in refs/
- [ ] `plugin.json` manifest includes a specific `description` scope statement
- [ ] Bus events (if any) use `{domain}:{action}:{outcome}` naming
- [ ] Persistent cross-session knowledge routes through
      `wicked-brain:memory`, not a plugin-local memory system
- [ ] Agents declare `subagent_type` matching the plugin namespace
      (`{plugin-name}:{agent-name}`)
- [ ] Graceful degradation: plugin works standalone when wicked-bus /
      wicked-brain are absent (bus/brain integration is optional but
      encouraged)

---

## Review process

Plugin contributions to the wicked-garden marketplace follow the same
gate pattern used for wicked-garden's own PRs:

1. **Evidence**: author runs the authoring checklist above and submits
   evidence artifacts alongside the PR (skill audit, non-duplication
   analysis, dogfood check).
2. **Council review**: `wicked-garden:jam:council` runs a multi-model
   verdict on the plugin's unique-value proposition. One strong dissent
   from council pulls the combined score down (BLEND aggregation:
   `0.4 × min + 0.6 × avg`).
3. **Gate adjudication**: the gate adjudicator checks the checklist
   evidence, council verdict, and description-quality scan. APPROVE /
   CONDITIONAL / REJECT with explicit rationale.
4. **Merge**: CONDITIONAL verdicts require inline fixes before merge.
   REJECT blocks until the plugin's unique-value proposition is
   demonstrably distinct from existing surfaces.

This is the same rigor wicked-garden applies to its own skills. The
plugin contract is not lighter than the internal standard — it is the
same standard applied to an external boundary.

---

## Versioning and lifecycle

### Semantic versioning

Plugin versions follow semver. wicked-garden's discovery layer reads the
`version` field from `plugin.json`. Breaking changes to skill names,
agent names, or command namespaces require a major version bump.

wicked-testing's own versioning is the exemplar: `0.3.3` at the time of
this writing, with a stable skill surface since `0.2.0` and a documented
deprecation window for any renamed skills.

### Deprecation

When a plugin renames or removes a skill:

1. Keep the old skill name in `plugin.json` for one minor release cycle,
   pointing to a thin redirect SKILL.md that says "use {new-name}" and
   does nothing else.
2. Bump the minor version on rename, major version on interface-breaking
   removal.
3. Emit a `wicked.plugin.skill.deprecated` bus event on the old skill's
   first invocation after the rename, with `successor` set to the new
   name.

### End-of-life

A plugin whose domain is absorbed by wicked-garden core (unlikely, given
the non-duplication rule) is deprecated with a minimum two-release notice.
In practice, wicked-garden's policy is to defer, not absorb — a well-run
plugin stays canonical for its domain indefinitely.

---

## Where this lives

`docs/v9/drop-in-plugin-contract.md`

Referenced from:
- v9 epic #601 (pillar #5 acceptance criterion for v9-PR-5)
- `docs/v9/discovery-conventions.md` (skill-description rules apply to
  plugins without exception)
- `docs/evidence/pr-5/` (wicked-testing audit, non-duplication sample,
  dogfood check)

Maintained by: wicked-garden maintainers. Update this doc when the
dispatch contract, gate process, or discovery model changes. The
wicked-testing exemplar section must stay current — if wicked-testing's
plugin.json or skill descriptions change materially, reflect those changes
here.
