# core-1.2.0-mini-cobol.json

A domain model (schema 1.2.0) exactly as `wicked-core domain-graph --out` writes it, kept so
garden's schema tests check the vendored schema against core's real output, not a hand-written
document.

How it was made:

- Store: wicked-core's `tests/fixtures/domain_v3/mini-cobol.sql` (the estate store after garden's
  `domain-run` wrote one run over the tree beside it; its header names the garden commit, the
  estate version and every tree file's sha256), loaded with `sqlite3 store.db < mini-cobol.sql`.
- Checkout: a copy of wicked-core's `tests/fixtures/domain_v3/mini-cobol/`.
- Builder: `wicked-core domain-graph --db store.db --repo-root <copy> --out core-1.2.0-mini-cobol.json`,
  built from wicked-core PR 1922 (J6 C1b + C2).
- Result: 4 statements (1 Checked, 3 open), 1 rule group, 4 follow-ups, 4 targets, accounting
  `{targets 4, accounted 2, open 3, stale 0}`.

Regenerate it the same way when the schema changes (and re-vendor `vendor/` from the same core).
