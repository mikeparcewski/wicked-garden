---
name: acme-seo-scraper
description: |
  Scrapes SERPs. Deliberately BROKEN: this is a worker
  ({vendor}-{domain}-{role}) but it does not declare context: fork.

  NOT THIS WHEN: ranking analysis — use `acme-seo-ranker`
  (which deliberately does NOT point back, breaking reciprocity).
---

# Scraper (broken fixture)

Worker without `context: fork` — must trip PK016. Its NOT-THIS-WHEN
reference above must trip PK030 because the ranker does not reciprocate.
