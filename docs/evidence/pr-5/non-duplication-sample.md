# Non-Duplication Rule — Worked Example

PR: v9-PR-5
Date: 2026-04-23

This document walks through the non-duplication rule using a concrete proposed
plugin skill. It shows why one shape is a CUT and what shape would pass instead.

---

## The proposed skill

A plugin author proposes a skill called `smart-git`:

```yaml
name: smart-git
description: |
  Summarize recent commits with context. Use when you want a quick
  overview of what changed in the last week, or before a standup,
  or to orient yourself on a new branch.

  NOT for: full blame analysis (use git blame).
```

### Why this is a CUT

Apply the no-wrapper test:

```bash
# Step 1 — get commits
git log --oneline --since="1 week ago"

# Step 2 — get diff stats
git diff --stat HEAD~7

# Step 3 — Claude synthesizes
"Here is what changed in the last week: ..."
```

Three native tool calls (Bash + Bash + inline synthesis) reproduce the
proposed skill exactly. The "context" the skill claims to add is Claude's
own inline synthesis — which Claude does naturally without being prompted.

The anti-trigger (`NOT for: full blame analysis`) is real but narrow. It
does not prevent the mis-routing problem: Claude would reach for this
skill in any "what changed recently" moment, when Bash with git is faster,
requires no skill invocation overhead, and produces identical output.

Verdict: **CUT — wrapper test fails.**

---

## What a passing shape for the same domain looks like

The same plugin author wants to add genuine value in the git/history domain.
They audit what Claude cannot do natively in three calls and find a real gap:

```yaml
name: release-impact
description: |
  Map which test scenarios were authored against tickets in a release,
  identify tickets with no corresponding scenario coverage, and
  cross-reference the commit graph against the wicked-testing evidence
  ledger to surface tested-vs-shipped divergence.
  Use when: preparing a release readiness report, investigating why a
  shipped feature has no test evidence, or auditing scenario coverage
  before a compliance review.

  NOT for: listing commits (use git log), running tests (use
  wicked-testing:execution), or general codebase search (use
  wicked-brain:search).
```

### Why this passes

Apply the no-wrapper test:

- **Step 1**: enumerate tickets in the release → `git log` + PR API
- **Step 2**: find wicked-testing scenarios linked to those tickets →
  requires querying the wicked-testing SQLite ledger's strategies table
  and joining on ticket IDs in scenario frontmatter
- **Step 3**: compare against the commit graph to find shipped code with
  no evidence → requires graph traversal over two data sources (git tree +
  evidence manifest)
- **Step 4**: surface divergence as a structured report

There is no way to do step 2 or step 3 in three native Bash calls without
owning the wicked-testing ledger schema and the evidence manifest format.
The skill provides a cross-plugin data join that cannot be replicated inline.

It also passes the non-duplication check against wicked-testing's own
surface: `wicked-testing:insight` queries the ledger for trend data, but
it does not cross-reference the git graph or ticket corpus. This skill
adds a distinct join that neither wicked-testing nor wicked-garden currently
provides.

Verdict: **KEEP — no-wrapper test passes, no duplication of existing surfaces.**

---

## The decision rule in one sentence

If Claude can replicate the skill's value by calling Bash, Read, Grep,
or an existing skill in three or fewer steps — cut the skill. The plugin's
job is to provide value the ecosystem does not already contain, not to
rename what already works.
