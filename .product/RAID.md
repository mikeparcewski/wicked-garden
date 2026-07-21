---
name: RAID
title: wicked-garden — Risks, Assumptions, Issues, Dependencies
status: draft
version: 0.1
date: 2026-07-21
author: mike.parcewski@gmail.com
review-required: true
---

# RAID Log

## Risks

| ID | Risk | Likelihood | Impact | Mitigation |
|----|------|-----------|--------|------------|
| RISK-001 | Archetype detection accuracy degrades for ambiguous or very short prompts | Medium | Medium | Detector returns confidence score; low-confidence prompts prompt for clarification. Multi-archetype output handles mixed-intent work. |
| RISK-002 | wicked-loom/wicked-vault peer absent → evidence gate fails closed | High (setup) | Low (expected) | Failing closed is the intended behavior. `/wg-check` validates peers at setup; setup skill guides installation. |
| RISK-003 | codegraph not built → blast-radius/lineage/wicked-patch unavailable | High (optional) | Medium | codegraph is explicitly opt-in; skills degrade gracefully to text-search when graph is absent. |
| RISK-004 | Plugin not loaded in `claude -p` non-interactive mode | Medium | High | Documented mitigation: user must add `--plugin-dir` via clis.toml override (garden#994 resolution). Long-term fix: persistent worker sessions (core#13). |
| RISK-005 | Council seat (Antigravity/Codex) unavailable or returns garbage | Medium | Low | Council aggregation tolerates partial failures; the skill surfaces which seats failed. |
| RISK-006 | Hook scripts fail on Windows without correct Python fallback | Low | High | All scripts use cross-platform patterns (tempfile.gettempdir, python fallback chain). CI must include Windows runner. |
| RISK-007 | Slim Body Contract violated → parent context bloat | Low | Medium | `/wg-check --full` enforces the limit. CI validates component manifest on every PR. |

---

## Assumptions

| ID | Assumption |
|----|-----------|
| ASS-001 | The host harness (Claude Code, Codex, Cursor, …) handles all planning, parallelism, and LLM calls. wicked-garden does not re-implement harness capabilities. |
| ASS-002 | Users install the required peers (`wicked-testing`/`wicked-vault`, `wicked-loom`) before using the evidence gate. The setup skill validates this. |
| ASS-003 | The codegraph (`.codegraph/codegraph.db`) is built and up-to-date when blast-radius/lineage/wicked-patch are used. |
| ASS-004 | Harness plugins are loaded in interactive mode; non-interactive (`claude -p`) mode requires explicit plugin-dir configuration. |
| ASS-005 | The `WICKED_VAULT_ACTOR` environment variable is set to a meaningful, stable actor identity for hard-gate evidence recording (not OS `$USER`). |
| ASS-006 | wicked-bus is optional; garden emits events fail-open when bus is unavailable. |

---

## Issues

| ID | Issue | Status | Resolution |
|----|-------|--------|-----------|
| ISS-001 | Plugin not loaded in `claude -p` subprocess (garden#994) | Closed | User-level clis.toml override; add `--plugin-dir ~/.claude/plugins` to claude seat's `headless_invocation`. |
| ISS-002 | Schema drift risk: domain-model schema vendored in 3 places (brain canonical, wicked-core/tests/, garden skills/domain/vendor/) | Open | Drift guard test pending; garden's vendor copy must match canonical on each release. |
| ISS-003 | Harness drift test for garden's schema vendor skips rather than fails when canonical path absent | Open | Fix: convert `pytest.skip` to `pytest.fail` so the drift guard is fail-closed. |

---

## Dependencies

| Dependency | Type | Required | Notes |
|-----------|------|----------|-------|
| Claude Code (or compatible harness) | Runtime | Yes | Plugin host. Must support `context: fork`, hooks, skills. |
| wicked-vault ≥ 0.4.0 | Runtime | Yes (for evidence gate) | Evidence backend. `0.4.0` introduced fail-closed `attest` on weak identity. |
| wicked-loom | Runtime | Yes (for evidence gate) | Gate/resolve engine. Resolved via `WICKED_LOOM_BIN` → config → PATH → `npx`. |
| wicked-testing | Runtime | Yes (for acceptance) | The acceptance pipeline is the standard gate mechanism. |
| wicked-brain | Runtime | Optional | Cross-session memory + codegraph. Required for blast-radius, lineage, wicked-patch. |
| wicked-bus | Runtime | Optional | Event audit trail. Garden emits events fail-open without it. |
| codegraph (`@colbymchenry/codegraph`) | Runtime | Optional | Static graph builder. Powers blast-radius/lineage/wicked-patch. |
| Python ≥ 3.9 | Runtime | Yes | Required for all hook scripts and CLI tools. |
| node.js ≥ 18 | Runtime | Yes | Required for npm peer installs and wicked-vault/loom. |
