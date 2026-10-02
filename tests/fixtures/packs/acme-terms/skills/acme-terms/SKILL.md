---
name: acme-terms
user-invocable: true
description: |
  ACME terms router: checks a document for the banned and preferred terms in
  ACME's style list. One action, check (dispatch the terms checker).

  Use when: "check our terms", "banned words", "style list review".
---

# ACME terms

One router per domain: this skill fronts the `acme-terms` domain and hands the
check to its worker, `acme-terms-checker`.
