# Migration to wicked-garden v7.0

## TL;DR

As of v7.0, wicked-garden requires wicked-testing as a peer plugin. Run
`npx wicked-testing install`. SessionStart blocks crew phases if wicked-testing
is missing.

**Authoritative migration reference**:
[mikeparcewski/wicked-testing — WICKED-GARDEN.md](https://github.com/mikeparcewski/wicked-testing/blob/main/docs/WICKED-GARDEN.md)

This file is a pointer only. All detail lives upstream.

---

## What Changed

QE behavior — test planning, authoring, execution, review — moved to the
[wicked-testing](https://github.com/mikeparcewski/wicked-testing) plugin.
wicked-garden still owns crew workflow, phase management, gate enforcement,
memory, and the 12 non-QE domains.

---

## Grace-Period Timeline

| Release | State |
|---------|-------|
| **v7.0** | `/wicked-garden:qe:*` commands aliased to `/wicked-testing:*`. Deprecation notice on each call. |
| **v7.1** | Aliases removed. `/wicked-garden:qe/*` commands, `agents/qe/`, `skills/qe/`, `commands/qe/` deleted (issues #551, #552, #553). |

Update before v7.1 to avoid broken commands.

---

## Version Compatibility

wicked-garden `^7.0` requires wicked-testing `^0.1`. The `wicked_testing_version`
field in `plugin.json` carries the pinned range. The SessionStart hook reads the
installed version and warns each session if it falls outside the range.

For the full version pinning policy see
[INTEGRATION.md §8](https://github.com/mikeparcewski/wicked-testing/blob/main/docs/INTEGRATION.md#8-version-pinning)
in the wicked-testing repo.

---

## Install

```bash
npx wicked-testing install
npx wicked-testing status
```

Verify the crew cycle works end-to-end:

```bash
/wicked-garden:crew:start "tiny refactor"
```

---

## Rollback

Pin to the latest v6.x release if you cannot upgrade wicked-testing yet:

```bash
claude plugins add mikeparcewski/wicked-garden@6
```

v6.x ships its own QE layer and does not require wicked-testing.

---

## Troubleshooting

- **"unknown subagent_type: wicked-testing:xxx"** — wicked-testing is not
  installed. Run `npx wicked-testing install`.
- **Version mismatch warning at session start** — installed version is outside
  `^0.1.0`. Run `npx wicked-testing install` to update.
- **Empty gate verdicts** — wicked-bus may not be running. wicked-garden's crew
  gate subscribes to `wicked.verdict.recorded`. Run `npx wicked-bus status`.
- **Old `/wicked-garden:qe:*` commands missing** — you are on v7.1+; aliases
  were removed. Use `/wicked-testing:*` equivalents (see upstream migration
  guide for the full command map).

For additional troubleshooting detail see the
[wicked-garden integration guide](https://github.com/mikeparcewski/wicked-testing/blob/main/docs/WICKED-GARDEN.md).

<!-- v7.0.1 follow-up (AC-23): add a defense-in-depth facilitator check that logs a structured error when wicked-testing is absent, independent of the SessionStart block. Out of v7.0 scope. -->
