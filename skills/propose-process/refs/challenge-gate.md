# Challenge Gate (Issue #442)

Persistent contrarian review. The facilitator auto-inserts the `challenge`
phase between `design` and `build` for complexity ≥ 4.

---

## Why this phase exists

On long-horizon projects the dominant direction can crystallise without
anyone formally maintaining a steelmanned counter-argument. `jam:council`
brainstorms alternatives at a single point in time but writes no persistent
artifact, and no phase gate blocks advancement on unresolved concerns. The
engine can be confidently wrong while appearing thorough.

The `challenge` phase fixes this by:

1. Assigning a dedicated **contrarian** specialist
2. Producing a **persistent** artifact (`phases/design/challenge-artifacts.md`)
   that carries across sessions
3. Hard-blocking `build` writes when the artifact has not cleared

## When to insert

- `complexity >= 4` (default threshold, override via
  `WG_CHALLENGE_MIN_COMPLEXITY` env var)
- `novelty = HIGH` — first-time design pattern in this codebase
- `reversibility = LOW` — one-way doors, migrations, data-format changes
- `blast_radius = HIGH` — cross-service, multi-tenant, or global rollouts

## When to skip

Only with a structured skip reason:

- `complexity_below_threshold` — complexity < 4 AND no other risk signal
- `user_explicit_request` — user has consciously opted out
- `out_of_scope` — the work has no design decisions (pure docs/config)

## Artifact requirements

`phases/design/challenge-artifacts.md` MUST contain:

- `## Strongest Opposing View` — narrative summary of the best counter-case
- `## Challenges` — enumerated `### Challenge CH-XX: <title>` blocks, each
  with `theme`, `raised_by`, `status`, and `steelman` (40+ chars) fields
- `## Convergence Check` — self-assessment of dissent variety
- `## Resolution` — disposition for each challenge

At `complexity >= 4` the artifact must have **at least two distinct themes**
among the challenges. Themes include: correctness, concurrency, security,
operability, cost, ethics, ux.

## Hard rules

- **No resolved without a steelman.** A challenge cannot be marked `resolved`
  unless a `steelman:` field of ≥ 40 characters describes the opposing view.
- **No convergence collapse.** If three or more challenges share the same
  theme the gate reports `CONVERGENCE-COLLAPSE` and blocks.
- **No silent closure.** Every challenge must appear in `## Resolution`.

## Gate reviewer matrix

Defined in `.claude-plugin/gate-policy.json` under `challenge-resolution`:

| Rigor     | Reviewers                                | Mode        |
|-----------|------------------------------------------|-------------|
| minimal   | *(self-check)*                           | self-check  |
| standard  | contrarian                               | sequential  |
| full      | contrarian + independent-reviewer        | parallel    |

## Runtime validation

Any script can validate an artifact:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
   "${CLAUDE_PLUGIN_ROOT}/scripts/crew/challenge_manifest.py" \
   validate phases/design/challenge-artifacts.md
```

Exit codes: 0 OK, 1 INVALID or CONVERGENCE-COLLAPSE, 2 usage error.

## Build-phase enforcement

The PreToolUse hook (`hooks/scripts/pre_tool.py::_check_challenge_gate`)
blocks `Write` / `Edit` during `build` phase when:

- active crew project exists AND
- complexity ≥ `WG_CHALLENGE_MIN_COMPLEXITY` (default 4) AND
- `phases/design/challenge-artifacts.md` is missing, invalid, or has
  convergence collapse AND
- the write is not to the artifact itself and not on the orchestrator
  allowlist (`.something-wicked/`, `*status.md`)

### Rollback

One env var disables the gate:

- `WG_CHALLENGE_GATE=off` — disables ONLY the challenge gate (targeted)

Takes effect immediately without re-starting the session. (v6.0 removed
the global `CREW_GATE_ENFORCEMENT=legacy` switch; broader rollback is a
`git revert` on the PR, not a runtime toggle.)
