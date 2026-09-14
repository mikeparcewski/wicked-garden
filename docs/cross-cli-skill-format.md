# Cross-CLI skill format

wicked-garden is installed into Claude Code, Codex, OpenCode, Pi and Antigravity by third
parties and snapshotted by wicked-crew for every seat. Only Claude Code reads Claude Code's
plugin frontmatter — so a skill's identity, dispatch shape and prose must not depend on it.
This page is the format; `scripts/_skill_meta.py` is its one reader; the lint
(`tests/test_skill_portability.py`) enforces it; `tests/cross_cli_baseline.json` lists what
still has to be translated (12.37.x batches; the strict release deletes the baseline).

## Frontmatter: the closed key set

```yaml
---
name: wicked-garden-<dir segments joined by '-'>
description: "One paragraph. What it does, when to use it. ≤ 1024 characters."
license: MIT                       # optional
compatibility: any                 # optional
mandates:                          # optional — skills this one requires the seat to hold
  - wicked-garden-core
metadata:                          # string → string; the ONLY nesting
  role: worker                     # worker | router | module | floor  (required)
  phases: "build,review"           # or "*" — replaces the legacy phase_relevance
  archetypes: "build,modernize"    # or "*" — replaces the legacy archetype_relevance
---
```

Exactly these top-level keys: `name`, `description`, `license`, `compatibility`, `metadata`,
`mandates`. Everything else — `context`, `subagent_type`, `allowed-tools`, `model`, `effort`,
`max-turns`, `color`, `user-invocable`, `disable-model-invocation`, `tool-capabilities`,
`phase_relevance`, `archetype_relevance`, `portability`, `status` — is a Claude Code plugin hint
no other CLI (and neither wicked-crew nor wicked-core) reads; the lint token
`claude-frontmatter-key` flags it. `metadata` values are strings (`"a,b"` lists, `"*"` for all).

## `metadata.role` — the closed role set

| role | meaning | who reads it |
|---|---|---|
| `worker` | a dispatchable specialist (`skills/<domain>-<role>/`); the only role loaders register as an AgentProfile / crew phase worker | `_agents.py`, `_validate_registry.py`, `crew/specialist_resolver.py`, `ci/sync_components.py`, `ci/find_orphan_agents.py`, `pack/check.py` PK015/PK016, hooks |
| `router` | an operator-facing entry point (`skills/<domain>/SKILL.md`), listed in help | `tests/test_help_skill_tree.py`, `pack/check.py` PK015 |
| `module` | NOT an entry point: a nested reference module a router/worker pulls in, or a retired redirect stub — the same meaning wicked-crew's `skillKindOf` gives `module` | everyone else, by exclusion |
| `floor` | a discipline handed whole to every governed unit (`wicked-garden-governed-worker`); never dispatchable, never an AgentProfile, exempt from the router line cap like a worker | `ci/validate.py` cap, `pack/check.py` PK020 |

**Transition inference** (`skill_role()`, mirrors wicked-crew's fallback order): a declared
`metadata.role` always wins (an unknown value reads `module` — never a silent worker); with none
declared, `context: fork` → `worker`, `user-invocable: true` → `router`, else `module`. Pack
authors: a `{vendor}-{domain}-{role}`-named skill with no `metadata.role: worker` **fails**
`pack check` (PK016) — a worker is never dropped silently.

## Dispatch: the Hand-off paragraph

No `Task(`, `Skill(`, `Agent(`, `TaskCreate(`/`TaskUpdate(`/`TodoWrite(`, `subagent_type` or
`AskUserQuestion` in a skill body (`claude-dispatch`; an assignment, constructor or lambda context — `x = Agent(`,
`new Agent({`, `lambda: Agent(` — is framework code in a sample, not a dispatch), and no Claude tool call either — `Read(`,
`Write(`, `Edit(`, `MultiEdit(`, `Bash(`, `Glob(`, `Grep(`, `WebFetch(`, `WebSearch(`, `NotebookEdit(`
with an argument shape after the paren (`claude-tool-call`): say what to do with your harness's file
reader / shell / file search instead. The one cross-CLI dispatch shape is a paragraph that starts with
`Hand-off` and names the skill:

> **Hand-off** — open the `wicked-garden-qe` skill and run its `review` action with the PLAN path
> as the argument; on Claude Code this is the Skill tool, on any other seat open the named skill
> from your catalog and carry it out inline, then continue here.

Inside that paragraph Claude-specific words are allowed; anywhere else a tool noun (`the Read
tool`), a `.claude/` path or the words `Claude Code` is `claude-only-prose`. A file that dispatches
without a Hand-off paragraph is `handoff-missing`. A line ending in `<!-- historical -->` is never a
finding (it documents a retired shape).

**The `Hand-off (harness-specific)` variant.** A step that exists on ONE harness only (the setup
wizard's `.claude/CLAUDE.md` hint block; the task-list tools' field mapping) is written as a paragraph
starting `**Hand-off (harness-specific)**` that names the harness, says what it does there and says
what every other seat does instead (usually: skip it). It hands the step to the harness, not to a
skill; the same exemption applies inside it. Use it sparingly — a step every seat can do is written
generically instead.

## Products and size

`wicked-testing`, `wicked-brain`, `wicked-signals` are retired and `wicked-loom` is being replaced — the skill TEXT retires the `wicked-loom` reference ahead of the peer itself (`wicked-loom` stays the prove gate's CI peer in `test.yml` / `tests/qe/test_prove.py` until the prove/loom-cutover seam removes it; DES-L6 B6 / review F3) —
by the in-process gate — name their successors (the `qe` domain, wicked-estate through the `mem` /
`search` skills, the built-in gate) or mark the line `<!-- historical -->` (`retired-product-ref`).
A SKILL.md stays under 500 lines and 24 KiB (`skill-too-large`; `scripts/ci/validate.py` applies
the same bound to routers and modules); detail goes in `refs/`. Skill-relative paths, the
`## Runtime` block and the launcher rules from 12.33 are unchanged.

## Tooling

- `python3 tests/test_skill_portability.py` — the report (0 violations, 0 stale baseline entries).
- `python3 tests/test_skill_portability.py --write-baseline` — regenerate the baseline **at B0
  only**; afterwards the file only shrinks (a batch deletes the entries it translated; a stale entry
  fails CI; B18 deletes the file).
- `python3 scripts/ci/validate.py && python3 scripts/_validate_registry.py` — the release gate,
  role-aware.
