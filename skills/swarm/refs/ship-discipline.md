# Ship discipline — branch, prove, review, merge, release

Shipping is its own wave, and it only runs **when the user asks**. A swarm
produces many units of verified work; landing them cleanly without trampling
each other or skipping the gate is the discipline this ref captures. It composes
`wicked-garden:worktrees` (isolation + dangling-commit safety) and the gate
machinery from `refs/receipts-and-evidence.md`.

> **Do not push / open PRs / release until explicitly asked.** The garden's
> house rule: commit or push only when the user requests it; if on the default
> branch, branch first. The swarm authors and verifies by default — shipping is
> opt-in.

## Branch per unit

Each unit lands on **its own branch** — never a shared swarm branch — so units
ship, review, and roll back independently:

- One branch per unit (e.g. `swarm/<unit-name>/<change>`).
- **Conventional commits** (`feat:` / `fix:` / `refactor:` / `chore:`) with the
  body referencing the unit and the receipt. This keeps the provenance check in
  the `wicked-garden-crew-reviewer` fork skill happy (commit messages should reference traceability
  anchors).
- **Trust-but-verify every reported commit SHA** (`wicked-garden:worktrees` §1):
  a subagent's reported SHA can be a dangling commit. Run the ancestry check
  before you treat the work as on a branch — especially with many implementers
  committing concurrently.

## CI-green gate (the receipt, again)

A unit does not merge on a green local run alone — the claim is re-derived:

- `/wicked-garden-prove tests-pass --by "<unit test cmd>"` (and `build-clean`,
  `lint-clean`) must return `satisfied: true, re_derived: true`.
- For hard-gate units, `--with-attestations` + an independent
  `wicked-vault attest --opinion pass` (evaluator ≠ implementer).
- If the unit's repo has a compiled gate (`/wicked-garden-prove compile`), let
  `.wicked/gate.py` run in CI — it re-derives through wicked-vault with no
  garden runtime present.

A red or fail-closed (`gate: "unavailable"`) result blocks the merge. Fix the
cause; never narrate around a failing gate.

## Independent code review + RESOLVE comments

- Each unit's PR gets an **independent** review — a different agent/human than
  the implementer (reviewer-separation; the `wicked-garden-crew-reviewer` fork skill and the vault
  both enforce evaluator ≠ creator). For high-stakes units run a
  `wicked-garden:jam:council` for multi-model perspective.
- **Resolve every bot/review comment** before merge — address it or reply why
  it's out of scope. An unresolved comment is an open finding, not noise.

## Clean merge tree

- **Rebase stragglers onto main** before merging so the tree stays linear and
  each unit's history is legible — don't let a late unit merge a stale base.
- Merge units in dependency order if any depend on each other (most swarm units
  are independent by construction — see `refs/fan-out.md`).
- After merge, confirm the branch's work is actually in main by **ancestry**,
  not by on-disk worktree presence (`wicked-garden:worktrees` §"authoritative
  signal") — then delete the branch + log the deletion.

## Tag-driven release + version sync

- Release is **tag-driven**: cut a tag, let CI build/publish from it.
- **Version-sync** anything that must agree (package manifest, lockfile, any
  embedded version constant) in the same release commit — a drifted version is a
  silent ship bug.

## Root causes + second-order regressions

- Fix **root causes**, not symptoms (the verify wave will catch a symptom-patch
  that doesn't re-derive).
- Watch for the **second-order regression** the change itself can introduce.
  Worked example: a CI workflow edit that quietly **drops a test gate** — the
  suite goes "green" because it stopped running, not because it passed. The
  verifier's over-claim check (`refs/independent-verification.md` §3) is exactly
  what catches this: re-run from clean and confirm the gate still actually runs.

## The ship checklist (per unit)

```
[ ] on its own branch, conventional commits, SHA verified by ancestry
[ ] /wicked-garden-prove → satisfied + re_derived for tests/build/lint
[ ] hard-gate units: independent wicked-vault attest --opinion pass
[ ] independent review done; all review/bot comments resolved
[ ] rebased onto current main; clean tree
[ ] (release) tag cut; versions synced
[ ] branch merged, confirmed in main by ancestry, then deleted + logged
```
