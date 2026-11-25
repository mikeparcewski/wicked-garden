---
name: wicked-garden-domain
description: |
  The FOUNDATIONAL domain-model capability: extract a codebase's business rules as
  checked statements, each tied to the code lines it rests on, and build the domain
  model on the estate graph. A scoped run finds the code that decides the scope's
  behaviour, has one seat state each decision and another check it against the
  lines, and wicked-core builds the domain model (schema 1.2.0) from the result.
  No minimum: the model says which statements are checked, which are open, and what
  a person should look at.

  A shared substrate, not a modernization tool: `modernize` derives from it, and
  build / migrate / review / specify / explore read the same model.

  Use when: "extract the business rules / domain model from this codebase", "what
  does this system actually require", "reverse-engineer the domain before we
  build/port/migrate". Works on any codebase (modern or legacy).

  NOT the code transform itself (that is the archetype consuming this model).
metadata:
  role: router
  phases: "discover,extract,blueprint,plan,specify"
  archetypes: "modernize,build,migrate,review,specify,explore"
---

# wicked-garden-domain

The **domain-model capability**: the shared model of what a codebase decides
(business rules as checked statements on the estate graph). The `modernize`
archetype derives from it; build / migrate / review / specify / explore read the
same model.

## How to run it

Run the **Extract domain model** job (wicked-crew's `domain-extraction` preset) on
a registered repository, with a scope: what part of the system the person wants
mapped ("how refunds are approved"). Studio's Start shows the scope card first
(the files and units it found) and carries the scope into the run.

The run is two host steps and no agent seat of its own:

1. `domain-run` runs `scripts/domain/run.py --db <repo store> --repo-root <checkout>
   --scope <scope file>`. It finds the scope's targets and carries a target's settled
   statements unchanged, with no model call, while its code has not changed. Everything
   else (new or changed code, a statement that failed its checks or is still unsettled)
   goes to the run's own seats, one to state each decision and one to check it against
   the cited lines. It writes the plain-words rule groups over the checked statements
   (again only when their inputs changed) and stores it all on the estate nodes.
2. `domain-graph` runs `wicked-core domain-graph`, which builds the domain model
   (schema 1.2.0) from those rows into the same store, where crew and studio read it.

Then **read the run's summary** (`summary.json` beside the run's calls: targets,
accounted, checked, open, follow-ups, model calls) and the model view. Do not edit
the store by hand.

## What the model holds

- **Statements**: one decision each, with its claims (conditions, effects, guards),
  the lines every claim cites, and a status: `Checked` (a second seat confirmed it
  against the code), `open` (not confirmed: see its follow-up), `confirmed` (a
  person confirmed it) or `stale` (the code changed since; the next run checks it
  again).
- **Rule groups**: plain-words sentences written only over Checked statements, each
  citing them. A sentence the check could not support is withheld with its reason.
- **Follow-ups**: what a person should look at: a flagged statement, an open claim, a
  target whose lines were not stated as a rule.
- **Targets**: every unit in scope, and whether its lines are accounted for.

A person rules on an open statement (Confirm or Reject with a note) or on an
unaccounted target (Confirm: "these lines make no business decision") from the
model view. A ruling binds to the statement and to its code: it stops applying when
either changes.

## Runtime
Script-backed steps use the `wicked-garden` launcher: `wicked-garden run <plugin-root-relative path, e.g. scripts/…> [args]`. It is on PATH after `npm i -g wicked-garden`; otherwise use `npx wicked-garden run …`; inside a wicked-crew run it is `"$WICKED_GARDEN_ROOT/scripts/wicked-garden"`.
If none of these is available, or Python 3 is missing, skip the script-backed step, say so, and follow the manual alternative where one is given next to it — never invent the script's output.
Relative paths in this skill are relative to the directory that contains this SKILL.md.

`scripts/domain/run.py` needs an indexed estate store (`wicked-estate index`) and the
run's model-call channel, which only a crew run provides. Outside a run there is no
manual alternative: say that the extraction runs as a job.

## The schema

The document validates against the domain-model schema (owner:
`wicked-core/crates/wicked-governance/schemas/domain-model.schema.json`; vendored at
`vendor/domain-model.schema.json`, pinned by `vendor/README.md`). Check a document
with `wicked-garden run scripts/domain/validate_domain_model.py <doc.json>`.

## Ground in the repo's method first

Before extracting, check for **wicked-understanding** repo playbooks (the
"how to work in THIS repo" layer). If present, load the matching playbook.
