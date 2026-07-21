---
name: REQ-004-ways-of-working
title: wicked-garden — Ways of Working
status: draft
version: 0.1
date: 2026-07-21
author: mike.parcewski@gmail.com
review-required: true
---

# REQ-004 — Ways of Working

This document describes how contributors develop, validate, and release wicked-garden. The development tools described here (`/wg-*`) live in `.claude/` and are not distributed to marketplace users.

---

## Adding a Skill

### 1. Scaffold

```bash
# Domain router skill (user-invocable):
/wg-scaffold skill my-skill --domain engineering

# Fork worker skill (context:fork, dispatch-only):
/wg-scaffold worker my-worker --domain platform

# Hook script:
/wg-scaffold hook my-hook
```

The scaffolder generates:
- `skills/{domain}/SKILL.md` (or `skills/{domain}-{role}/SKILL.md` for fork workers) with frontmatter stub.
- A `refs/` directory placeholder for on-demand content.
- For hooks: a script stub under `hooks/scripts/` with a registration entry in `hooks/hooks.json`.

Naming rules:
- Domain router skill: `wicked-garden-{domain}` (kebab-case, max 64 chars).
- Fork worker skill: `wicked-garden-{domain}-{role}` with `context: fork` frontmatter.
- Back-compat alias (optional): `subagent_type: wicked-garden:{domain}:{role}` in frontmatter for pre-v12.25 callers.

### 2. Implement

Skill design follows progressive disclosure:
- **Frontmatter** (~100 words): name, description (the trigger — written to be picked up by the harness), and minimal metadata. Always loaded; keep it tight.
- **SKILL.md body** (≤200 lines): overview and navigation to refs. Must stay slim — it loads into the parent context permanently.
- **`refs/` files** (200-300 lines each): the detailed content, rubrics, and playbooks. Loaded on demand via dispatch.

Apply the slim body contract:
- Pattern A (Advisory/State): ≤ 8 lines — for state mutation, no dispatch.
- Pattern B (Write Brief + Dispatch): ≤ 30 lines — for session-specific work.
- Pattern C (Interactive Branch + Dispatch): ≤ 35 lines — for user decision before dispatch.

Collapse rubric-wrappers to inline refs: if an action is purely loading a checklist and applying it, move the checklist to `refs/<name>.md` and apply inline — do not add a `Task()` dispatch hop unless real parallelism, a real external tool, or an independent gate is involved.

For hook scripts: stdlib-only Python, no third-party imports. Use `python3 -c "..."` with `2>/dev/null || python -c "..."` fallback for JSON output. Cross-platform: use `tempfile.gettempdir()`, not `/tmp`; use `sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh"` for Python invocation.

Coding rules (R1–R6): no dead code, no bare panics, no magic values, no swallowed errors, no unbounded ops, no god functions.

### 3. Validate

```bash
# Fast structural check (CI-friendly):
/wg-check

# Full marketplace readiness (validation + skill review + value assessment):
/wg-check --full
```

`/wg-check` verifies:
- Frontmatter completeness and format.
- Skill naming conventions (kebab-case, prefix, max length).
- Body line count (slim body contract).
- Hook registration consistency.
- `components.json` sync status (run `scripts/ci/sync_components.py` to regenerate).

`/wg-check --full` additionally runs a skill review (trigger effectiveness, description quality) and a value assessment (does the action earn its dispatch overhead?).

Testing rules (T1–T6): determinism, no sleep-based sync, isolation, single assertion focus, descriptive names, provenance.

---

## Issue Workflow

```bash
# Triage, implement, and open PR for a GitHub issue:
/wg-issue 42

# List open issues:
/wg-issue --list
```

`/wg-issue 42` classifies the issue into one or more archetypes, loads the appropriate playbook, and executes the phase shape. On completion, it opens a PR. For bugs, this typically runs the `build + review` archetype pair. For feature requests, it may run `specify → build`.

When testing wicked-garden machinery and a bug is found, file a GitHub issue immediately — do not accumulate findings in a local `.md` log file:

```bash
gh issue create --label bug \
  --title "<surface>: <one-line>" \
  --body "<location> | <observed vs expected> | <impact> | <fix proposal>"
```

---

## Marketplace Sync

`components.json` is a derived manifest of all skill surfaces. It must be regenerated whenever a skill is added, renamed, or removed:

```bash
python3 scripts/ci/sync_components.py 2>/dev/null || python scripts/ci/sync_components.py
```

The sync script reads all skill SKILL.md frontmatter and writes the updated manifest. CI validates that `components.json` matches the current skill tree — a stale manifest is a CI failure.

---

## Release

```bash
# Dry run (validate, do not publish):
/wg-release --dry-run

# Bump version and publish:
/wg-release --bump minor
/wg-release --bump patch
/wg-release --bump major
```

The release process:
1. Validates plugin structure (`/wg-check --full`).
2. Bumps `version` in `plugin.json` and `marketplace.json`.
3. Regenerates `components.json` via `scripts/ci/sync_components.py`.
4. Commits the version bump.
5. Tags the release and pushes to the marketplace registry.

Version scheme: semver. `minor` for new capabilities or skill additions. `patch` for bug fixes and rubric updates. `major` for breaking changes (plugin API, peer version floor changes, archetype contract changes).

---

## CI Checks

Two primary GitHub Actions workflows:

**`validate.yml`** — runs on every push and PR:
- Plugin structure validation (frontmatter, naming, slim body contract).
- `components.json` sync check.
- Hook script syntax validation (Python stdlib-only check).
- Compiler output AST check (stdlib-only enforcement in emitted `gate.py`).
- Cross-platform path checks (no hardcoded `/tmp`, no bare `python3` without fallback).

**`test.yml`** — runs on push to `main` and on release branches:
- Unit tests: `tests/` directory via pytest.
- Scenario tests: `scenarios/` directory via the wicked-testing acceptance gate.
- Compiler tests: `tests/compiler/test_compile.py` (AST-enforced stdlib-only check on emitted gate).
- Hook integration tests: fire hook events and verify output format.

A PR is not merge-ready until both workflows are green. The wicked-testing acceptance gate (when configured) additionally requires an independent QE verdict — the evaluator agent is not the agent that ran the tests.

---

## Code Review Protocol

All PRs follow the wicked-ecosystem merge protocol:

1. Open the PR on a branch — do not push fixes straight to the default branch.
2. Wait 6–8 minutes for automated reviewers (Gemini Code Assist, GitHub Copilot) and CI to post.
3. Read every automated reviewer comment. Evaluate each on its merits; address valid findings with follow-up commits to the same branch.
4. Merge only when comments are resolved and CI is green.

Vendor contributions (external PRs that bundle legitimate skill rewrites with frontmatter regressions or hook changes) must be rejected as bundles. Salvage valid wins in-house.

---

## Storage Paths

Never hardcode `~/.something-wicked/` in consumer code. Use:
- `get_local_path()` from `scripts/_paths.py` for constructing project-scoped paths.
- `DomainStore` from `scripts/_domain_store.py` for domain-keyed persistence.
- `SessionState` from `scripts/_session.py` for per-session ephemeral state.

Project scope is derived from `cwd` hash: `~/.something-wicked/wicked-garden/projects/{slug}/{domain}/{subpath}`.

---

## Memory and Brain

In wicked-garden development sessions:
- **Do not** directly edit any `MEMORY.md` file.
- **Do** use `wicked-brain:memory` (store mode) to persist decisions, patterns, and gotchas.
- **Do** use `wicked-brain:search` / `wicked-brain:query` for retrieving past context.
- **Always** prefer `wicked-brain:search` over Grep/Glob/Agent(Explore) for open-ended search within the codebase.
- wicked-brain is the source of truth. The server auto-starts on any brain skill invocation.
