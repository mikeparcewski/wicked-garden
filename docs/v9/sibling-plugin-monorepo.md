# wicked-garden-monorepo — Sibling Plugin Design Brief

Issue: #722 (reframe — see jam analysis at
<https://github.com/mikeparcewski/wicked-garden/issues/722#issuecomment-4364107563>)
Status: **deferred** — no work started in core; this doc is the brief
for a future sibling-plugin author. Demand criteria below.

---

## Why this is a sibling plugin

Wicked-garden core stays small on purpose. From `ETHOS.md`:

> **Local-first, graceful degradation, always works standalone.** Every
> tool degrades cleanly when its dependencies are absent. No required
> network calls, no required external services.
>
> **Not closed.** Third-party plugins integrate via the v9 drop-in
> contract. Specialized domains belong in their own plugins, not in
> wicked-garden core.

The original framing of #722 added substantial new core surface — a
`repos:` block on `process-plan`, a `multi_repo.py` module, a
DAG validator, worktree lifecycle hooks, cross-repo evidence
aggregation, a per-archetype gate-adjudicator extension. ~800–1200 LOC
of always-on machinery, owned by core, paid for by every user, used by
~2% of teams.

The reframe (this doc) keeps wicked-garden core honest:

1. Core ships an **advisory hint only** — the optional
   `affected_repos: [string]` field on `process-plan.json`, surfaced as
   one line in `crew:status` and `smaht:briefing`, plus a one-paragraph
   nudge in the multi-repo archetype prompt. ~150 LOC, zero new failure
   surfaces, fully backward-compatible.
2. Cross-repo orchestration — the DAG, worktrees, merge ordering,
   evidence aggregation — lives in **`wicked-garden-monorepo`**, a
   sibling v9 plugin built when there is real demand. Until then, this
   document is the design brief that keeps the option alive without
   bloating core.

The canonical sibling-plugin example is **wicked-testing**
(`/Users/michael.parcewski/Projects/wicked-testing`). It demonstrates
every contract beat: scope-stating manifest, v9 discovery-shape skill
descriptions, optional bus/brain integration, no duplication of core
or native tools. `wicked-garden-monorepo` should follow the same shape
— see `docs/v9/drop-in-plugin-contract.md` for the full ruleset.

---

## Demand criteria — when to actually build it

The plugin should be authored when **either** of:

1. **Five or more user issues** ask for one of the deferred capabilities
   (worktree provisioning, merge-order DAG, cross-repo evidence
   aggregation, per-repo gate-adjudicator extension). Less than five →
   the advisory hint plus per-repo crew sessions is doing the job.
2. **A sibling-plugin author signs up** to own the plugin end-to-end
   (write the code, maintain the discovery-shape skill descriptions,
   keep the marketplace listing current). The drop-in contract requires
   plugin authors, not wicked-garden maintainers, to own their plugin's
   lifecycle.

If neither holds, leave the advisory hint in place and revisit on the
next major release. Premature plugin authoring is the same anti-pattern
as premature core abstraction — both pay maintenance cost up front for
hypothetical future demand.

---

## Architecture — bus-as-truth alignment

The brain memory `bus-as-truth-event-sourced-crew-state` and PR #738
(closed) established the load-bearing rule: crew state is event-sourced
through wicked-bus chains, not synthesized into parallel write stores.
A cross-repo project is the same shape as a single-repo project, just
**N chain_id siblings under one root**:

```
root chain:    cross-feature-X.root
              ├── repo-foo:  cross-feature-X.repo-foo.root
              │              ├── cross-feature-X.repo-foo.clarify
              │              ├── cross-feature-X.repo-foo.design
              │              └── cross-feature-X.repo-foo.build
              ├── repo-bar:  cross-feature-X.repo-bar.root
              │              └── ...
              └── repo-baz:  cross-feature-X.repo-baz.root
                             └── ...
```

The plugin **MUST NOT** add a fourth write store. The bus event log
already carries every artifact landing, gate verdict, and phase
transition the plugin needs to coordinate across repos. The plugin's
job is to shape, query, and aggregate those events — not to mirror
them into a new database.

This is the same rule wicked-testing follows: it owns its `.wicked-testing/`
SQLite ledger for **operational** evidence (run records, scenario
files), but **decisions, patterns, and gotchas** route through
`wicked-brain:memory`. wicked-garden-monorepo's `repos.json` (described
below) is operational state local to the plugin; cross-repo
**decisions** still route through wicked-brain memory.

---

## Schema — repo DAG (full version, owned by the plugin)

The plugin's `process-plan` extension upgrades the advisory
`affected_repos: [string]` field that core ships into a richer
`repos:` block. The plugin reads this block; core never touches it.

```jsonc
{
  // ... all existing wicked-garden process-plan fields ...

  // Advisory list — produced by the facilitator, read by core
  // crew:status / smaht:briefing surfaces. Always present in
  // multi-repo plans; the plugin's repos: block expands it.
  "affected_repos": ["repo-foo", "repo-bar", "repo-baz"],

  // Plugin-owned block. Core ignores this entirely.
  "repos": {
    "repo-foo": {
      "url":          "git@github.com:org/repo-foo.git",
      "default_branch": "main",
      "worktree_path":  ".worktrees/repo-foo",   // resolved by the plugin
      "merge_order":    1,                        // 1-based; lower lands first
      "depends_on":     [],                       // names of repos that must
                                                  // ship first (DAG edges)
      "owns_artifacts": ["api-contract"],         // canonical-source repo for
                                                  // these named artifacts
      "rollback_plan":  "phases/build/rollback-foo.md"
    },
    "repo-bar": {
      "url":          "git@github.com:org/repo-bar.git",
      "default_branch": "main",
      "worktree_path":  ".worktrees/repo-bar",
      "merge_order":    2,
      "depends_on":     ["repo-foo"],             // DAG edge
      "owns_artifacts": [],
      "rollback_plan":  "phases/build/rollback-bar.md"
    },
    "repo-baz": {
      "url":          "git@github.com:org/repo-baz.git",
      "default_branch": "main",
      "worktree_path":  ".worktrees/repo-baz",
      "merge_order":    2,
      "depends_on":     ["repo-foo"],
      "owns_artifacts": [],
      "rollback_plan":  "phases/build/rollback-baz.md"
    }
  }
}
```

DAG validation rules the plugin enforces (none of these belong in core):

- Every key in `repos` MUST appear in `affected_repos` (and vice
  versa) — no silent drift between the advisory list and the plugin's
  block.
- `depends_on` references MUST resolve to other keys in `repos` —
  no dangling edges, no self-loops.
- The DAG MUST be acyclic — cycles fail closed with a structured
  error citing the offending edge.
- `merge_order` MUST be consistent with `depends_on` (a repo cannot
  have a lower merge_order than any of its dependencies) — the plugin
  derives `merge_order` from `depends_on` if the field is omitted.
- `owns_artifacts` entries MUST be unique across all repos — no two
  repos own the same canonical artifact.

---

## Worktree lifecycle (plugin-owned)

Worktree provisioning is a per-repo operation governed by the plugin:

1. **Provision** — at the start of the build phase, the plugin walks
   `repos[]`, runs `git -C {repo_url_clone} worktree add {worktree_path}`
   for each entry, and emits
   `wicked.multirepo.worktree.provisioned` per repo (with the active
   crew `chain_id` so wicked-garden's chain-aware smaht scoring lights
   up the events).
2. **Track** — the plugin maintains `repos.json` under
   `.wicked-garden-monorepo/repos.json` as **operational** state (the
   wicked-testing equivalent of `.wicked-testing/evidence/`). This is
   plugin-local; it does NOT shadow core's `process-plan.json`.
3. **Conflict handling** — when a worktree's `git status` shows
   uncommitted changes at provisioning time, the plugin fails closed
   with an explicit error and a `wicked.multirepo.worktree.conflict`
   event. No silent overwrite.
4. **Cleanup** — at project archive (or explicit teardown command),
   the plugin runs `git worktree remove {worktree_path}` for each
   tracked repo and emits `wicked.multirepo.worktree.removed`.
5. **Idempotency** — re-running provision MUST be safe. If a worktree
   already exists at the expected path on the expected branch, the
   plugin emits `wicked.multirepo.worktree.reused` instead of failing.

See the brain memory `parallel-agent-rate-limit-collision-gotcha` —
when the plugin fans out provisioning across N repos, it MUST throttle
to avoid the same rate-limit collision wicked-garden's parallel
dispatch path has tripped on before.

---

## Cross-repo merge ordering

The plugin watches build-phase completions across the chain siblings
and emits `wicked.multirepo.merge.ordered` events that **core crew
consumes** as advisory hints. Core's behaviour:

- When `wicked.multirepo.merge.ordered` arrives with the active chain's
  `chain_id`, the chain-aware smaht events adapter scores it 0.8+ and
  surfaces the advised next-merge repo in `crew:status`.
- Core does NOT enforce the order — it surfaces the recommendation and
  lets the user (or the plugin's own dispatch agent) act on it.
- The plugin's merge-order policy lives entirely in the plugin: read
  the DAG, watch build-completion events, emit the next-up repo.

Event shape:

```json
{
  "event_type": "wicked.multirepo.merge.ordered",
  "chain_id":   "cross-feature-X.root",
  "next_up":    "repo-foo",
  "blocked_on": [],
  "rationale":  "merge_order=1, depends_on=[]",
  "ts":         "2026-05-02T12:00:00Z"
}
```

---

## Cross-repo evidence aggregation

Evidence aggregation is the plugin's most distinctive value
proposition — Claude cannot replicate it in three native tool calls
(it requires a graph traversal over chain siblings). The plugin's
evidence skill:

1. Reads gate-result events from each chain sibling
   (`cross-feature-X.repo-foo.review.gate`,
   `cross-feature-X.repo-bar.review.gate`, etc.).
2. Aggregates the per-repo verdicts into a combined cross-repo verdict
   using BLEND (the same `0.4 × min + 0.6 × avg` core uses for
   multi-reviewer aggregation in `gate_dispatch.py`). One repo's strong
   REJECT pulls the combined verdict down proportionally.
3. Emits a single `wicked.multirepo.evidence.aggregated` event with
   the combined verdict, per-repo breakdowns, and a path to the
   aggregated evidence bundle.
4. Surfaces the combined verdict in `crew:status` via a
   `### Cross-Repo Evidence` additive section (rendered only when at
   least one chain sibling has a gate result).

---

## Plugin manifest scope statement

Per `docs/v9/drop-in-plugin-contract.md` §2, the manifest's
`description` field is the scope statement core's routing layer reads
to decide what to defer:

```jsonc
{
  "name": "wicked-garden-monorepo",
  "version": "0.1.0",
  "description": "Cross-repo SDLC for wicked-garden — worktree
    provisioning, merge-order DAG, and cross-repo evidence aggregation
    for projects that span 2+ repositories. Reads the optional
    `affected_repos` advisory field on wicked-garden process-plans and
    extends it with a plugin-owned `repos:` block. Optional bus + brain
    integration. Standalone — works without wicked-garden installed
    when used as a pure git-worktree orchestrator.",
  "skills": [
    {
      "name": "wicked-garden-monorepo:provision",
      "description": "Provisions per-repo git worktrees from a process-plan's `repos:` block. Use when: starting the build phase of a multi-repo project, re-provisioning after a checkout reset, validating that all repos are at the expected branches. NOT for: single-repo projects (use core crew), shallow clones (use Bash directly)."
    },
    {
      "name": "wicked-garden-monorepo:order",
      "description": "Computes the next merge target from the DAG of `repos[].depends_on`. Use when: a build phase just completed and you need to know which repo to merge next, the DAG itself needs validation. NOT for: single-repo merges (use git directly)."
    },
    {
      "name": "wicked-garden-monorepo:aggregate-evidence",
      "description": "Aggregates per-repo gate-result events from chain siblings into a single cross-repo verdict using BLEND. Use when: a cross-repo review gate needs a combined verdict, the per-repo evidence bundles need to be folded into one. NOT for: per-repo evidence collection (each chain sibling's review gate already does that)."
    }
  ],
  "agents": [
    {"name": "wicked-garden-monorepo:dag-validator"},
    {"name": "wicked-garden-monorepo:worktree-provisioner"},
    {"name": "wicked-garden-monorepo:merge-orchestrator"},
    {"name": "wicked-garden-monorepo:evidence-aggregator"}
  ]
}
```

Each skill description follows the v9 discovery conventions
(verb-first, `Use when:` triggers, `NOT for:` anti-triggers, no-wrapper
test passing). The aggregate-evidence skill is the plugin's no-wrapper
proof point — the BLEND aggregation across chain siblings cannot be
reproduced in three native tool calls.

---

## Bus events emitted (canonical naming)

Per `docs/v9/drop-in-plugin-contract.md` §4, event names follow
`{domain}:{action}:{outcome}` (lowercase, colon-separated):

```
wicked.multirepo.dag.validated         {chain_id, repos[], cycles[]}
wicked.multirepo.worktree.provisioned  {chain_id, repo, worktree_path}
wicked.multirepo.worktree.conflict     {chain_id, repo, reason}
wicked.multirepo.worktree.reused       {chain_id, repo, worktree_path}
wicked.multirepo.worktree.removed      {chain_id, repo}
wicked.multirepo.merge.ordered         {chain_id, next_up, blocked_on, rationale}
wicked.multirepo.merge.completed       {chain_id, repo, sha}
wicked.multirepo.evidence.aggregated   {chain_id, verdict, per_repo, bundle_path}
```

All events MUST carry the active crew `chain_id` so wicked-garden's
chain-aware smaht events adapter scores them 0.8+ and surfaces them in
the ambient context Claude sees at every turn. This is the same hook
wicked-testing uses for its `wicked.verdict.recorded` events.

---

## What core promises (and does not promise)

Core wicked-garden ships **only**:

- The optional `affected_repos: [string]` field on `process-plan.json`,
  validated for shape (list of non-empty strings) by
  `scripts/crew/validate_plan.py`. No DAG, no semantic validation.
- A read-only renderer (`scripts/crew/affected_repos.py render`) that
  surfaces the field as one advisory line in `crew:status` and
  `smaht:briefing`. Fail-open: missing / empty / malformed → silence.
- A one-paragraph nudge in the multi-repo archetype prompt of
  `agents/crew/process-facilitator.md` Step 6 telling the facilitator
  to open one crew project per repo and link via shared `chain_id`
  prefix.
- This design doc.

Core wicked-garden does **not** ship:

- A `repos:` block reader, writer, or validator
- Worktree provisioning, tracking, or cleanup
- A merge-order DAG validator
- Cross-repo evidence aggregation
- A per-archetype `multi-repo` extension to the gate adjudicator
- A `multi_repo.py` module of any kind

Those are the plugin's value proposition. Until the plugin exists, the
advisory hint plus per-repo crew sessions cover the 80% case at 10% of
the cost.

---

## Authoring checklist for the future plugin author

Before opening the plugin's first PR (per
`docs/v9/drop-in-plugin-contract.md` §"Authoring checklist"):

- [ ] Every skill description passes the five v9 discovery conventions
- [ ] No skill wraps a native tool — apply the no-wrapper test
- [ ] No skill duplicates core (the `affected_repos` advisory line
      stays in core; the plugin owns the DAG and everything downstream)
- [ ] Each SKILL.md is ≤200 lines; depth in `refs/`
- [ ] Manifest `description` is the scope statement quoted above (or a
      tightened variant — keep "standalone" and "optional integration")
- [ ] Bus events follow the `{domain}:{action}:{outcome}` shape and
      carry `chain_id` for chain-aware smaht scoring
- [ ] Cross-session decisions route through `wicked-brain:memory` —
      operational `repos.json` is plugin-local, but architectural
      decisions are not
- [ ] Worktree provisioning throttles fan-out (parallel-agent
      rate-limit memory)
- [ ] Plugin works standalone when wicked-garden is absent (it can
      still provision worktrees from a hand-written `repos.json`); bus
      and brain integration are optional but encouraged

---

## Related references

- `ETHOS.md` lines 60–66 — "Not closed. Third-party plugins integrate
  via the v9 drop-in contract."
- `docs/v9/drop-in-plugin-contract.md` — the contract every sibling
  plugin follows; wicked-testing is the canonical example.
- `docs/v9/discovery-conventions.md` — skill-description rules.
- `scripts/crew/affected_repos.py` — the core renderer this plugin
  extends.
- `scripts/crew/validate_plan.py` — the schema validator that accepts
  the optional `affected_repos` field.
- `scripts/crew/archetype_detect.py::_detect_multi_repo` — the
  archetype detector that triggers the multi-repo prompt.
- Issue #722 + jam analysis at
  <https://github.com/mikeparcewski/issues/722#issuecomment-4364107563>
- PR #738 / Brain memory `bus-as-truth-event-sourced-crew-state` — the
  load-bearing rule that cross-repo state stays in the bus, not in a
  parallel write store.
