---
phase_relevance: ["clarify", "design", "build", "test"]
archetype_relevance: ["specify", "build", "ship", "review"]
---

<!-- Action ref of the `wicked-garden-qe` router (TH-7, ADR 0006 "qe campaign
     homes into the four planes"). Loaded on demand via Read() from the
     router's `campaign` action — not a skill. -->


# qe campaign — recon + generation playbook

Turns a target repo into a machine-readable, dependency-ordered campaign
plan: a capability inventory derived from three lenses, bound to a scenario
ladder that CONFORMS to `${CLAUDE_PLUGIN_ROOT}/schemas/campaign-recon.schema.json`
(format v2; spec:1 plans still validate) — **never a parallel format**.
Scenario bodies stay scenario-format markdown (v1.1 —
[refs/scenario-format.md](scenario-format.md)); the plan orders and binds
them, it never replaces that format.

Execution, grading, and gating are NOT this action's job: the human
confirmation leg is § intake ([refs/intake.md](intake.md) — the plan
proposed as a HITL gate, approve/amend/reject), confirmed plans run through
§ execute / the model-free runner (`scripts/qe/runner`), grades come from
§ accept, and the acceptance gate re-derives "done" from ledger evidence
(ADR 0006 separation of duties).
Execution, grading, and gating are NOT this action's job: confirmed plans
run through § execute / the model-free runner (`scripts/qe/runner`), grades
come from § accept, and the acceptance gate re-derives "done" from ledger
evidence (ADR 0006 separation of duties). Flaky verdicts at that gate follow
[refs/campaign-flake-policy.md](campaign-flake-policy.md) (TH-21): bounded
diagnostic re-runs with BOTH verdicts recorded, a hunter-owned quarantine
lane (owner + deadline), quarantined scenarios excluded-with-reason — never
silently dropped, never retried-to-green.

## Usage

```
wicked-garden-qe campaign [target-repo] [--name <campaign>] [--out <dir>] [--json]
```

- `target-repo` — path to the repo under test (default: current dir)
- `--name` — campaign name (default: `<repo>-<yyyymmdd>`)
- `--out` — plan root (default: `.wicked-qe/campaigns/<name>/`)

## The three lenses (recon)

Run all three; each contributes provenance-tagged inventory entries. The
glue derives the `sources` block from what actually contributed — never
assert it by hand.

### Lens 1 — estate code graph (`source: "estate"`)

When the target repo is indexed in wicked-estate, seed the inventory from
the graph — route/handler/component nodes and the injected edges grep never
sees (event→consumer, command→agent):

1. Probe availability first (fail-open, never crash):
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/_estate_client.py"` — `health` +
   `stats`; or dispatch `Skill(skill="wicked-garden-search")` for
   blast-radius/lineage questions.
2. Query surfaces: `SearchEntity` for routes/handlers/components; follow
   injected edges to consumers. Every claim gets a `file:line` citation.
3. **Honest degradation:** if estate is unreachable OR the repo is not
   indexed, contribute ZERO estate entries and say so — the plan then
   carries `sources.estate: "unindexed"` and coverage claims must repeat it.
   Never silently substitute grep results as "estate".

### Lens 2 — docs recall (`source: "docs"`, always PROPOSED)

`Skill(skill="wicked-garden-mem")` recall over the target's docs/READMEs/
sites for claimed capabilities the graph and probes did not surface.
**Every doc-derived claim enters as `status: "proposed"`** — pending human
review, exactly the incident-to-scenario pending-review pattern
(`../../qe-incident-to-scenario-synthesizer/SKILL.md`). The assembler
enforces this; a rung certifying a proposed capability cannot be
`confirmed`.

### Lens 3 — live probe (`source: "probe"`)

Against an ISOLATED instance only (79xx port, scratch `--db`, never
7701/7810 or real state dirs):

- **Health endpoints** — hit `/api/v1/health`-class routes; capture JSON.
- **Committed endpoint manifests** — wicked-crew commits
  `packages/crew/endpoint-manifest.json` (`{version, apiTypesVersion,
  endpoints[]}`); convert it to inventory entries mechanically:

  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/scripts/qe/campaign_plan.py" \
    from-endpoint-manifest <repo>/packages/crew/endpoint-manifest.json
  ```

- **DOM landmarks** — `data-testid` inventory read from the BUILT dist
  actually served, never source recon alone (selector drift is the proven
  failure mode; record the artifact identity in the environment manifest).

## Assembly + validation (fail-closed)

Assemble with the glue — it derives `sources` honestly, forces doc-derived
entries to `proposed`, and rejects any plan that does not conform:

```python
# python3, from ${CLAUDE_PLUGIN_ROOT}
from scripts.qe.campaign_plan import assemble_plan, persist_plan

plan = assemble_plan(
    target={"repo": "<owner/name or path>", "ref": "<sha>", "surface_url": "<url>"},
    estate_capabilities=[...],   # lens 1 (empty ⇒ sources.estate = "unindexed")
    docs_capabilities=[...],     # lens 2 (forced status: proposed)
    probe_capabilities=[...],    # lens 3
    scenarios=[...],             # dependency-ordered rungs (deps = earlier ids only)
    environment_manifest={"ref": "environment-manifest.json"},
    name="<campaign-name>",
)
persist_plan(plan, out_dir=".wicked-qe/campaigns/<name>")  # raises on any defect
```

Or validate a hand-assembled plan:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/qe/campaign_plan.py" validate <plan.json>
```

Rules the validator enforces beyond the JSON schema: ladder order (deps
reference EARLIER rungs only), rung→capability binding resolves, doc-derived
= proposed, no estate-sourced entries in an `unindexed` plan, `confirmed`
rungs never certify still-proposed capabilities, and `isolation` requires
spec 2 (v1 plans without it remain valid).

### Rung design (the ladder)

- Order rungs so cheap API smoke certifies the substrate before UI journeys
  (`deps` encode it; the schema's ladder is topological by construction).
- Every rung carries `pass_criteria` = terminal_state + artifact +
  consumer_state — launch ≠ done, all three are mandatory.
- `claim_ceiling`: a rung whose user journey is API-substituted caps at
  `machinery-verified` — certify the user journey, not the proxy.
- `category`: `api` | `ui` | `desktop` (plan taxonomy). Generated stubs map
  `api`→`api`, `ui`→`browser`, `desktop`→`desktop` (scenario-format v1.1).
  Desktop rungs are tiered HONESTLY — see the tier ladder in
  [refs/scenario-format.md](scenario-format.md#desktop-tiers-category-desktop):
  T0 crew-governed PTY is the only tier a campaign may rely on today
  (campaign-proven; pass FILE PATHS through PTY prompts, never bodies —
  1022B limit); T1 `_electron` waits for a target; T2 computer-use is
  exploratory and ALWAYS reviewer-graded; T3 is deferred in writing.
- `isolation` (spec 2, optional): `shares-state` (default when absent —
  conservative on purpose) | `exclusive` | `stateless`. Copy the scenario
  file's `isolation` frontmatter onto its rung — the PLAN is what the
  scheduler mapping consumes, never scenario markdown.

### Isolation & parallel execution (TH-22)

The proven campaign ladder was dependency-ordered because scenarios mutate
ONE daemon's shared state (projects, repos, runs accumulate). The moment a
campaign runs as a parallel DAG (wicked-core's scheduler via crew's
`/api/v1/campaigns`, TH-9), unannotated parallelism = the classic e2e race.

- The rung's `isolation` value is the machine-consumed annotation. TH-9's
  scenario→CampaignNode mapping reads it from `campaign-recon.json`:
  `stateless` nodes may run in parallel against one target instance;
  `shares-state` nodes are serialized per target instance; `exclusive`
  nodes get DAG serialization edges OR a per-node isolated profile (fresh
  `WICKED_HOME` / `--db` / `--bus-db` — the campaign runbook's proven
  recipe).
- **Until that mapping consumes the annotation, campaigns MUST run with
  `max_concurrency: 1`** — correct, just slow; the constraint is explicit,
  never accidental.
- Fixture namespacing is the `stateless` contract: the runner provides a
  per-run `QE_FIXTURE_NS` default for spec interpolation (the mapper sets
  one per node); stateless scenarios embed it in every fixture name they
  create (`scripts/qe/runner/README.md`).

## Persistence

- **Plan + stubs**: `persist_plan` writes `campaign-recon.json` and
  scenario-format v1.1 stubs under `.wicked-qe/campaigns/<name>/scenarios/`
  (stubs fail until authored — never a silent PASS; every stub carries an
  explicit `isolation:` line, defaulting to `shares-state`).
- **Ledger**: record the campaign as a `strategies` row (body = the plan
  JSON) and each rung as a `scenarios` row via wicked-ledger's DomainStore —
  stable scenario id = capability-id + slug so flake history accrues across
  re-runs. Proposed rungs keep `pending-review` status in their scenario
  frontmatter until a human confirms.
- Doc-derived (proposed) rungs surface to the human as a review list —
  approve flips capability + rung to `verified`/`confirmed`; reject deletes
  the rung; amend edits then re-validates. The wire for that review is
  § intake ([refs/intake.md](intake.md)): the whole plan proposed as a HITL
  gate on the campaign's governed crew run.

## Degradation rungs — break-it scenarios per external dependency (TH-23)

The campaign's proven negative pattern (S19 estate-binary-absent, S20
daemon-kill — both PASSED because the consumer told the truth), generalized:
for every DECLARED external dependency of the target,
`${CLAUDE_PLUGIN_ROOT}/scripts/qe/campaign_degradation.py` generates a
break-it capability + rung + scenario stub whose pass bar is **honest error
naming + zero crashes + recovery** — distinct honest answers for distinct
absent states, never a generic 500, never a fake success. `augment` appends
them to an existing plan fail-closed (degradation rungs are
`isolation: exclusive`, so spec-1 plans are refused without an explicit
bump). Full playbook + the external-deps declaration format:
[refs/campaign-degradation.md](campaign-degradation.md).

## Rerun — verdict diffs vs the prior run (TH-23)

A campaign rerun reuses the PERSISTED strategy and its committed
deterministic specs; the diff half consumes the ledger's run history (the
runs + verdicts rows accruing under stable scenario ids, TH-6):

```bash
node "${CLAUDE_PLUGIN_ROOT}/scripts/qe/lib/campaign-rerun.mjs" \
  --strategy <campaign-dir | campaign-recon.json> \
  [--since <ISO-8601>] [--require-rerun] [--json] [--out <file>]
```

Per-scenario deltas: `regression` (PASS → deny — exit 1) · `fixed` ·
`still-failing` · `unchanged-pass` · `new` · `not-rerun` (loud; exit 1 under
`--require-rerun`) · `ungraded-current` (blocks — grade through the accept
trio first, never diff an executor claim). Grades follow the scoreboard's
rule: newest NON-executor verdicts row only (TH-10), INCONCLUSIVE denies.

## CI assembly — PR subset + governed nightly (TH-23)

The GH Actions recipe lives at [refs/campaign-ci.md](campaign-ci.md) with
copyable workflows in `${CLAUDE_PLUGIN_ROOT}/docs/examples/`: **PR** runs
the deterministic subset only (runner specs, executor claims, zero tokens);
**nightly** runs the full governed campaign through crew's
`/api/v1/campaigns` — budget-capped (TH-20 knobs pinned explicitly),
flake-policied at the gate (TH-21), graded by the accept trio, ending in the
rerun diff above. The first dogfood corpus is wicked-crew's own e2e suite
folded into scenario format (`wicked-crew/e2e/campaign/`).

## Dispatch guard (mandatory for every qe dispatch)

Before ANY `Skill(...)` dispatch from this action (and the other qe
actions), resolve the specialist through the guard — it asserts the resolved
worker is a garden `wicked-garden-qe-*` skill that ships in the catalog and
BLOCKS retired surfaces with a clear error (never a silent rewrite):

<!-- historical: the dispatch-guard demo deliberately names a retired specialist to show the block -->
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/qe/campaign_dispatch.py" wicked-garden-qe-scenario-executor
# → wicked-garden-qe-scenario-executor          (exit 0)

python3 "${CLAUDE_PLUGIN_ROOT}/scripts/qe/campaign_dispatch.py" wicked-testing-a11y-test-engineer
# → dispatch guard: BLOCKED retired specialist ... (exit 2)
```
<!-- /historical -->

`wicked-testing-*` resolution is blocked at dispatch (wicked-testing retired <!-- historical -->
2026-08, Phase 6) — the error names the `wicked-garden-qe-*` replacement.
If a retired name reaches you (stale playbook, stale installed agent), fix
the caller; do not work around the guard.

## Output

- Path to `campaign-recon.json` + the scenario stub list
- The `sources` line verbatim (indexed/unindexed, docs_recall, live_probe) —
  an unindexed plan says so in the summary, never buried
- Count of proposed entries awaiting human review
- Ledger strategy id (when the ledger is reachable)

## References

- `${CLAUDE_PLUGIN_ROOT}/schemas/campaign-recon.schema.json` — the contract
- `${CLAUDE_PLUGIN_ROOT}/scripts/qe/campaign_plan.py` — assembler/validator
- `${CLAUDE_PLUGIN_ROOT}/scripts/qe/campaign_dispatch.py` — dispatch guard
- `${CLAUDE_PLUGIN_ROOT}/scripts/qe/campaign_degradation.py` — degradation generator
- `${CLAUDE_PLUGIN_ROOT}/scripts/qe/lib/campaign-rerun.mjs` — rerun verdict diffs
- [refs/scenario-format.md](scenario-format.md) · [refs/execute.md](execute.md) ·
  [refs/accept.md](accept.md) · [refs/campaign-flake-policy.md](campaign-flake-policy.md) ·
  [refs/campaign-degradation.md](campaign-degradation.md) ·
  [refs/campaign-ci.md](campaign-ci.md) · ADR 0006 (`docs/adr/`)
