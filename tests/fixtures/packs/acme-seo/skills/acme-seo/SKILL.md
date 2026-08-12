---
name: acme-seo
user-invocable: true
description: |
  ACME SEO domain router: keyword research, content audits, and ranking
  verdicts with recorded evidence. Two actions — keywords (dispatch the
  keyword analyst) and audit (dispatch the content auditor; its verdict is
  recorded via wicked-vault so "done" is re-derived, never asserted).

  Use when: "keyword research", "SEO audit", "why don't we rank",
  "content optimization", "meta description review".
phase_relevance: ["design", "build", "review"]
archetype_relevance: ["review", "build"]
---

# ACME SEO

One router per domain — this skill fronts the `acme-seo` domain and routes
its actions to fork workers. It never does the analysis itself.

## Actions

| Action     | Worker                      | What you get                        |
|------------|-----------------------------|-------------------------------------|
| `keywords` | `acme-seo-keyword-analyst`  | keyword map + intent clusters       |
| `audit`    | `acme-seo-content-auditor`  | seo-audit verdict, evidence-recorded|

## Routing

1. Classify the ask. Keyword strategy → `keywords`. Existing-content
   review → `audit`.
2. Dispatch the worker with the target URLs / content paths.
3. For `audit`, the worker records its findings via
   `wicked-vault record --phase seo-audit --actor acme-seo-content-auditor`
   so the review archetype's produces-gate can re-derive the verdict.

Never self-assert an audit passed — the gate re-derives `seo-audit`
through the vault.
