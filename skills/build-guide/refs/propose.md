# Propose the guide

The guide reaches the base only through review: the run's deliver gate inside wicked-crew, or a
PR otherwise. It is never a silent write and never a push to the default branch.

## Outside a wicked-crew run

1. Branch: `git switch -c wicked/build-guide` (or `wicked/build-guide-refresh`).
2. Stage only `.wicked/build-guide.json`. Commit message: `chore(floor): add build/test guide`
   (or `refresh`).
3. Show the user the guide and the probe table, and ask before opening the PR. Use your
   harness's question prompt where it has one; otherwise ask in plain text and wait.
4. Open the PR. Make it a draft when any probe failed or the probe was unavailable. Use the body
   below.

## Inside a wicked-crew run

Write `.wicked/build-guide.json` in the run's worktree and finish your unit. The deliver gate
shows the diff, and the operator approves it there. Ask nothing; a headless run has nobody to
answer. Put the same body in your unit output.

## PR body

```
## Build/test guide (.wicked/build-guide.json)

Derived from: <derivedFrom, one per line>
Runner: <name and --version output>
Schema: <the `schema` field check.py printed>

### Probe results (`wicked-core floor probe`)
<probe.py's markdown table>
— or, when the probe was unavailable —
probe unavailable: the guide is unverified, so the floor will not use it for exclusion.
Rehearsal (unverified, not evidence): <per-check rehearse.py results>

### Notes
- Result kind: <junit|text …>, and why (for text: the runner has no structured output, or its
  structured ids do not round-trip)
- Rehearsal-only findings: <for example, deselect-many failed: vitest rejects a repeated name pattern>
- Attempts: <n of 3> per check
```

## No guide

Open nothing. Report *"no build/test guide: the floor will run this repo's checks exit-code
only"*, and give the reason.
