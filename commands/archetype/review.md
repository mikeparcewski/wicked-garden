---
description: Independent assessment with hard verdict (APPROVE/CONDITIONAL/REJECT)
argument-hint: "[artifact / PR / commit]"
phase_relevance: ["*"]
archetype_relevance: ["review"]
---

# /wicked-garden:archetype:review

Run the review archetype: scope → assess → findings → remediate-or-accept. Produces a verdict + remediation list.

Invoke `wicked-garden:archetype` skill with archetype=review. Loads `refs/review.md`. Final verdict is a HARD gate — banned-reviewer enforcement applies (no auto-approve identities).

This is the only review that produces a **binding verdict**. For a code-quality pass use `engineering:review`, for an AI agent system use `agentic:review`, for a UI use `product:ux-review` (see `docs/domains.md` → "review appears in three domains").
