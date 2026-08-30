---
phase_relevance: ["design", "build", "test"]
archetype_relevance: ["build", "ship", "review"]
---

<!-- Action ref of the `wicked-garden-qe` router (TH-23 / test-R19a,
     ADR 0006 "qe campaign"). Loaded on demand via Read() from the router's
     `campaign` action — not a skill. -->

# qe campaign degradation — break-it scenarios per external dependency

The campaign's proven negative pattern, generalized into a generator
archetype. In the 2026-08 studio E2E campaign, **S19** (estate binary made
absent → the surface still answered, honestly: `200 {graph: null}` naming
the missing binary, distinct from 404 "graph not built") and **S20** (daemon
kill → the UI showed a named disconnect state, WS reconnected on restart)
both **PASSED because the consumer told the truth about a broken
dependency**. That is the pass bar this generator encodes for every declared
external dependency of a campaign target:

> **Honest error naming + zero crashes + recovery.**
> Distinct honest answers for distinct absent states — never a generic 500,
> never a fake success, never fabricated data.

No qe specialist covers this layer: `qe-chaos-test-engineer` is
Toxiproxy/tc/infra-level (network faults into a running dependency), while
this archetype tests the *consumer's honesty* when a dependency is simply
**gone** — binary absent, daemon down, state dir unwritable.

## Usage

```bash
# Emit capabilities + rungs + scenario markdown (JSON to stdout, writes nothing)
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/qe/campaign_degradation.py" generate \
  --deps external-deps.json --plan-name <campaign>

# Append degradation rungs to an existing campaign plan (fail-closed:
# validates the augmented plan in full before writing anything)
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/qe/campaign_degradation.py" augment \
  --deps external-deps.json --plan <campaign-dir>/campaign-recon.json \
  --out <campaign-dir> [--after <rung-id>] [--allow-spec-bump]
```

## The external-deps declaration

Dependencies are **declared, never guessed** — the operator (or the campaign
recon action, from its capability inventory) states what the target depends
on. A skipped dependency is a degradation scenario that never exists, so the
loader fails closed on every defect instead of skipping entries.

```json
{
  "deps": [
    {
      "id": "estate-binary",
      "kind": "binary",
      "name": "wicked-estate",
      "healthy_signal": "GET /api/v1/projects/:id/graph returns the graph JSON",
      "category": "api"
    },
    { "id": "crew-daemon",   "kind": "daemon",    "name": "wicked-crew daemon", "category": "ui" },
    { "id": "qe-ledger-dir", "kind": "state-dir", "name": ".wicked-qe ledger dir" }
  ]
}
```

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | kebab-case dep id — becomes `degradation-<id>` capability + rung ids |
| `kind` | yes | `binary` \| `daemon` \| `state-dir` \| `custom` |
| `name` | yes | Human name of the dependency (appears in every honest-answer assertion) |
| `category` | no | Rung category `api` (default) \| `ui` \| `desktop` |
| `healthy_signal` | recommended | The healthy probe — the recovery assertion (A3) needs a baseline; left undeclared, the generated capability says so honestly |
| `consumer_surface` | no | Overrides the generated capability `surface` text |
| `break`, `honest_signal`, `recovery` | `custom`: `break`+`honest_signal` required | Override the archetype defaults; for `custom` there ARE no defaults — the caller declares |
| `archetype` | no (`custom` only) | Slug for the broken state (default `custom-break`) |
| `citations` | no | `file:line` citations copied onto the capability entry |

## Built-in break archetypes

One per dependency kind — the S19/S20/ledger-readonly negatives, generalized:

| Kind | Broken state | Honest signal (the pass bar) | Recovery bar |
|---|---|---|---|
| `binary` | **absent** — unresolvable on EVERY resolution path (PATH shadow, rename, override env at a nonexistent path); partial breakage tests nothing | consumer keeps answering and NAMES the missing binary, distinct from "not yet built" and every other absent state (the S19 rule) | restoring the binary restores the healthy answer WITHOUT a consumer restart (or the restart need is itself named) |
| `daemon` | **down** — SIGTERM, or point the consumer at a closed port (never at a *different* live daemon) | a NAMED connection-failure / disconnected state for this dependency (the S20 rule) — no fake success, no unhandled crash | daemon restart reconnects WITHOUT a consumer restart (S20's WS-reconnect bar) |
| `state-dir` | **readonly** — write permission revoked while the consumer runs | writes fail NAMING the directory and operation; reads still serve; no partial/corrupt state; never a fake write success | restored permission lets the next write succeed; no earlier "successful" write was silently dropped |
| `custom` | caller-declared | caller-declared (`honest_signal`) | caller-declared (default: healthy signal returns without restart) |

## What gets generated

For each dep: a capability inventory entry (`degradation-<id>`,
`source: "human"` — declared, so verified), a plan rung
(`degradation-<id>-<archetype>`) whose `pass_criteria` encode the three
assertions, and a scenario-format v1.1 markdown file following the campaign
**stub doctrine**: the placeholder step `exit 1`s until a human/agent
authors the concrete break/verify/restore commands — **a generated
degradation scenario can never silently PASS**.

Invariants the generator enforces (fail-closed, in `augment`):

- **`isolation: exclusive` on every degradation rung** — breaking a shared
  dependency is the format's own definition of exclusive (TH-22); that also
  means a spec:1 plan is REFUSED unless `--allow-spec-bump` (a silent
  version bump is a versioning lie).
- **`claim_ceiling: machinery-verified`** — a break-it scenario proves the
  machinery's honesty, not a user journey.
- **id collisions are refused, never renamed or merged.**
- `--after <rung-id>` must name an existing rung; degradation rungs then
  depend on it (they append at the ladder's end, so topological order holds).
- The augmented plan must pass `campaign_plan.plan_errors` **in full** before
  anything is written.

## Executing degradation scenarios

- **Isolated instances only** — 79xx port, scratch `--db`/`--bus-db`, scratch
  state dirs. Breaking a real daemon or a real state dir is an incident, not
  a test.
- Author the healthy-baseline capture FIRST (A3 diffs against it).
- Grading goes through the accept trio like every campaign scenario
  ([refs/campaign-grading.md](campaign-grading.md)) — "it printed an error"
  is not automatically honest: the reviewer checks the answer NAMES the
  dependency and is DISTINCT from other absent states.

## References

- `${CLAUDE_PLUGIN_ROOT}/scripts/qe/campaign_degradation.py` — the generator
- [refs/campaign.md](campaign.md) · [refs/scenario-format.md](scenario-format.md) ·
  [refs/campaign-ci.md](campaign-ci.md) (nightly wiring) · ADR 0006 (`docs/adr/`)
