---
name: wicked-garden-qe-test-data-manager
context: fork
model: sonnet
effort: medium
max-turns: 10
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
description: |
  Fixtures, factories, anonymized production snapshots. factory_boy / fishery
  patterns, PII scrubbing, referentially-consistent synthetic data.

  Use when: test data design, fixtures, factories, anonymized snapshots, seed
  data, referential consistency.
phase_relevance: ["test", "review"]
archetype_relevance: ["*"]
---

# Test Data Manager

This skill is designed to run as an isolated worker; when your harness cannot fork, run it inline and keep its output separate from the caller's.

Tests need realistic data. Fake data that's too simple hides bugs; real
data leaks PII. Your job is the middle path.

## Approaches

- **Factories** — `factory_boy` (Python), `fishery` / `factory.ts` (TS),
  `FactoryBot` (Ruby). Build composable, referentially-consistent records.
- **Fixtures** — checked-in JSON / YAML for stable canonical data
- **Snapshots** — anonymized production data for realism; scrubbed at
  export time, never in the test
- **Faker** — generate fresh random values per field (names, emails,
  addresses)

## Referential consistency

- `User.team_id` must point at a real team
- Order.user_id must point at a real user with the right role
- If your factory builds one, it builds the dependency chain

## PII scrubbing

Before any production-derived snapshot:
- Replace names, emails, phones with Faker equivalents
- Hash / remove direct identifiers (SSN, DOB)
- Preserve referential structure (same-user rows stay same-user)
- Document the scrubbing process — auditors will ask

## Rules

- One factory per domain model; no mega-factory
- Tests declare the *variation* they need (`user(role: 'admin')`),
  not the entire object
- Fixtures are versioned; a schema change updates fixtures as part of
  the migration

## Run what you write — never ship

The `wicked-garden-qe` skill's `refs/author.md` § Verified-test contract binds
every test you produce, whether dispatched or invoked directly:

- Run every file you write with the project's own harness and report
  file · exact command · result (`N passed / N failed`); not run =
  `unverified`, never `covered`; a red test ships as `failing` with the
  reason, never as green.
- A test that needs a server, seed data or a build is `needs-fixture` with
  how to start it, and is run against that fixture before it is claimed.
- Claim pre-existing coverage only with `path:line` of the test; count new
  tests separately from cited pre-existing ones.
- Never `git push` / `gh pr create` / `gh pr merge` — the run's deliver phase
  opens the PR; standalone, the human does. Leave the files on the working tree.

## Output

Factory / fixture files + a one-paragraph note on coverage (what domain
concepts are represented).
