---
name: acme-terms-checker
metadata:
  role: worker
context: fork
description: |
  Terms checker worker: lists every banned or non-preferred term in a document,
  with the sentence it appears in and the preferred replacement.

  Use when: dispatched by the `acme-terms` router.
---

# ACME terms checker

Read the document, compare it with the style list, and report each hit with its
sentence and the replacement.
