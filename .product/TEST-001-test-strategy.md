---
name: TEST-001-test-strategy
title: wicked-garden — Test Strategy
status: draft
version: 0.1
date: 2026-07-21
author: mike.parcewski@gmail.com
review-required: true
---

# TEST-001 — Test Strategy

## Purpose

This document defines the test strategy for wicked-garden. The overarching principle is that wicked-garden dogfoods its own evidence-gate: every release must pass the same re-derive-not-assert gate the plugin ships.

---

## Test Layers

### Layer 1 — Unit Tests (`tests/`)

Pytest-based unit tests covering:
- Archetype detection (`tests/crew/test_archetypes_v11.py`) — scoring accuracy across representative prompts, multi-archetype output, boundary cases.
- Compiler output (`tests/compiler/test_compile.py`) — emitted gate is stdlib-only (AST-enforced), correct contract derivation, trigger installation.
- Evidence gate logic (`tests/qe/`) — vault-gate integration, fail-closed behavior when loom/vault absent.
- Domain store (`tests/test_domain_store.py`) — project scoping, path isolation.
- Hook scripts (`tests/hooks/`) — JSON output format, cross-platform path handling.

Run: `pytest tests/ -v`

### Layer 2 — Scenario Tests (`scenarios/`)

Acceptance scenario files in wicked-testing's scenario format. Each scenario describes a user-observable behavior end-to-end (e.g., "archetype is detected and playbook loaded for a migrate prompt"). Executed via wicked-testing's `execution` skill against the installed plugin.

Run: `/wicked-testing:acceptance-testing scenarios/<scenario>.md`

### Layer 3 — Plugin Validation (`/wg-check`)

The `/wg-check` dev tool validates structural correctness:
- All skills have valid frontmatter (name, description, context)
- Slim Body Contract (≤35 lines for parent-context skills)
- Component manifest (`components.json`) is in sync with actual skills
- No orphaned skill directories

Run: `/wg-check` (fast, CI-friendly) or `/wg-check --full` (includes skill review and value assessment).

### Layer 4 — CI (GitHub Actions)

| Workflow | Trigger | What it checks |
|----------|---------|----------------|
| `validate.yml` | PR, push | Plugin structure, skill frontmatter, component manifest sync |
| `test.yml` | PR, push | `pytest tests/` on ubuntu-latest |
| `pages.yml` | main push | Site build (wg.wickedagile.com) |

CI does NOT run full scenario acceptance (requires live LLM calls) — those gate releases manually.

### Layer 5 — Pre-release Gate

Before every release:
1. `/wg-check --full` — structural + marketplace readiness
2. `/wicked-testing:acceptance-testing` over the core scenario set — produces verdict.json
3. Verdict must be PASS or CONDITIONAL with zero CRITs
4. Adversarial review of any significant behavior change

Evidence artifacts committed to `.product/evidence/`.

---

## What Is NOT Covered

- **LLM judgment quality** — archetype classification accuracy is bounded by the model; tests verify the scoring mechanism not the model.
- **Council seats availability** — external CLI availability (Antigravity, Codex) is not tested in CI.
- **Cross-harness behavior** — only Claude Code is the primary tested harness; Cursor, Codex, OpenCode are validated manually on releases.

---

## Defect Triage

| Severity | Examples | Response |
|----------|---------|---------|
| Critical | Evidence gate fails open; parent-context skill body > 35 lines | Block release; fix before merge |
| High | Archetype detector returns wrong archetype for high-confidence prompts; hook script crashes on Windows | Fix in current sprint |
| Medium | Council seat returns garbage; codegraph unavailable degrades non-gracefully | Fix in next sprint |
| Low | Slow test; cosmetic skill description issue | Backlog |
