---
description: Schema/API/data shape change with expand-contract pattern
argument-hint: "[migration description]"
phase_relevance: ["*"]
archetype_relevance: ["migrate"]
---

# /wicked-garden:archetype:migrate

Run the migrate archetype: plan → expand → backfill → cutover → contract. Produces shape change + tested rollback proof.

Invoke `wicked-garden:archetype` skill with archetype=migrate. Loads `refs/migrate.md`. Cutover gate is HARD — pre-cutover checklist (rollback tested, backfill verified, dual-write soaked) before each switch.
