---
description: Independent assessment with hard verdict (APPROVE/CONDITIONAL/REJECT)
argument-hint: "[artifact / PR / commit]"
phase_relevance: ["*"]
archetype_relevance: ["review"]
---

# /wicked-garden:archetype:review

Run the review archetype: scope → assess → findings → remediate-or-accept. Produces a verdict + remediation list.

Invoke `wicked-garden:archetype` skill with archetype=review. Loads `refs/review.md`. Final verdict is a HARD gate — banned-reviewer enforcement applies (no auto-approve identities).
