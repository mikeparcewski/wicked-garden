---
name: acme-seo-scraper
description: |
  Scrapes SERPs. Deliberately BROKEN: this is a worker
  ({vendor}-{domain}-{role}) but it declares no metadata.role: worker.

  NOT THIS WHEN: ranking analysis — use `acme-seo-ranker`
  (which deliberately does NOT point back, breaking reciprocity).
---

# Scraper (broken fixture)

Worker-shaped name without `metadata.role: worker` — must trip PK016. Its NOT-THIS-WHEN
reference above must trip PK030 because the ranker does not reciprocate.
