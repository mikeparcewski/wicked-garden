---
name: wicked-garden-codemod-first
description: |
  The mechanical-first gate for upgrade and modernization work: before any hand
  edit, count the affected sites, look for an existing recipe or tool, try an AST
  codemod, choose the gate that proves the transform, and hand-edit only the
  residue. Records the decision as one `mechanical-first:` block (or a one-line
  written rejection) in the plan or PR description.

  Use when: a dependency or toolchain version upgrade ("upgrade react 17 to 18",
  "bump tokio to 1.40"), a framework or major-version migration, removing
  deprecated calls, an API rename, a lint or format rule rollout, language-level
  modernization (syntax, idioms), replacing one library with another, "port this
  module/app", or any change expected to touch more than about 10 similar sites.
  Not for a one-off bug fix or a new feature.
metadata:
  role: router
  phases: "plan,implement,transform"
  archetypes: "build,migrate,modernize"
---

# Codemod first — the mechanical-first decision

An agent asked to "upgrade X" tends to open files and start editing. For a change with many
similar sites, that is the slowest and least reviewable way to do it. This skill is the gate in
front of the edit: it makes you decide, and write down, whether a mechanical transform does the
bulk. The how-to is `wicked-garden-engineering-large-scale-migration` (MAP → TRANSFORM → GATE and
its ranked technique ladder). Follow it for the transform; this skill only makes sure you start
there.

## Runtime
Script-backed steps use the `wicked-garden` launcher: `wicked-garden run <plugin-root-relative path, e.g. scripts/…> [args]`. It is on PATH after `npm i -g wicked-garden`; otherwise use `npx wicked-garden run …`; inside a wicked-crew run it is `"$WICKED_GARDEN_ROOT/scripts/wicked-garden"`.
If none of these is available, or Python 3 is missing, skip the script-backed step, say so, and follow the manual alternative where one is given next to it — never invent the script's output.
Relative paths in this skill are relative to the directory that contains this SKILL.md.

## When it applies

Run this before the first edit of any change that is:

- a dependency, runtime or toolchain version upgrade, or a major-version migration;
- a removal of deprecated calls, an API rename, or a move off one library onto another;
- a lint or format rule rollout, or language-level modernization (syntax, idioms);
- "port this module or app";
- any change you expect to touch more than about 10 similar sites.

Not sure? `wicked-garden run scripts/engineering/mechanical_first.py applies "<the request>"`
prints `{"applies": true|false, "matched": [...]}`. With no launcher, read the list above and
decide. A one-line bug fix or a new feature does not need it.

## The decision, step by step (before any hand edit)

1. **Inventory.** Count the affected sites with a deterministic search: an AST tool (ast-grep,
   semgrep, tree-sitter, ts-morph, libcst) or `rg` when the pattern is purely textual. Record the
   exact command and the count. An agent's impression of "about 40 places" is not a count.
2. **Recipe check.** Look for an existing recipe or tool for this exact change before writing
   one. Examples of what to look for (not a fixed list): `npx @next/codemod`, `ng update`,
   `npx react-codemod`, jscodeshift transforms, OpenRewrite recipes, `cargo fix --edition`,
   `cargo clippy --fix`, `pyupgrade`, `django-upgrade`, `ruff check --fix`, `go fix`,
   `gofmt -r`, `eslint --fix`, `dotnet upgrade-assistant`, a Renovate or Dependabot preset.
   Record what you checked and what you found.
3. **Codemod.** If no recipe covers it, can an AST codemod (ast-grep, comby, jscodeshift, libcst,
   ts-morph, tree-sitter) express the bulk? Write it, run it, and record what it reports it could
   not handle: that list is the residue.
4. **Gate.** Choose the check that proves the transform kept behaviour: the full test suite, a
   differential run of old against new, a type check, or a lint count driven to 0. Record the
   command.
5. **Residue only.** Hand or AI edits touch only the sites the transform left. Count them.

## Write the decision down

Put exactly one decision in the plan, the phase output or the PR description, in the shape
`refs/decision-block.md` defines:

- the fenced block that starts with the line `mechanical-first:` and carries `inventory`,
  `count`, `recipe_checked`, `codemod`, `gate` and `residue`; or
- when mechanical is the wrong tool, the single line
  `mechanical-first: rejected — <reason>` (for example "3 sites, each semantically different").

Silence is not a choice: a hand edit with neither is the failure this skill exists to stop.
Check your text before you hand it in:
`wicked-garden run scripts/engineering/mechanical_first.py check <file>` (or `-` for stdin)
exits 0 when it holds a valid block or rejection and names what is missing otherwise. With no
launcher, compare it with the template in `refs/decision-block.md` by hand.

## Where it is enforced

Not here, and not by a hook: hooks run only in one CLI's interactive sessions, and crew seats
carry none. The `migrate`, `modernize` and upgrade-shaped `build` playbooks of
`wicked-garden-archetype` call this skill before they transform or implement, and the
`wicked-garden-governed-worker` floor tells every governed seat to. A held steering policy in
wicked-core (the `step:mechanical_first` obligation adds a `mechanical_first` plan step) checks
for the block's exact shape, which is why the shape lives in one file.
