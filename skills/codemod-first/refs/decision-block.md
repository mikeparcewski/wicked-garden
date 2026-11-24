# The mechanical-first decision block

This is the contract between `wicked-garden-codemod-first` and anything that checks for it,
including the wicked-core `mechanical_first` plan step. Keep the shape exact: a checker reads it
line by line, with no model in the loop.

## Form 1: the block

A fenced code block (three backticks or three tildes, with or without an info string) whose
first non-blank line is exactly `mechanical-first:`, followed by one `key: value` line for each
of these six keys. Indentation before a key is allowed. Each key appears once.

| Key | Value |
|---|---|
| `inventory` | the exact command that counted the sites |
| `count` | the number of sites it found: a whole number, 0 or more |
| `recipe_checked` | which recipes or tools you looked for, and what you found |
| `codemod` | the tool and transform you ran, or `none — <why>` |
| `gate` | the exact command that proves the transform |
| `residue` | the sites left for hand or AI edits: a whole number, 0 to `count` |

Template (copy it, then fill every value):

```
mechanical-first:
  inventory: <command>
  count: <n>
  recipe_checked: <what you checked> — <what you found>
  codemod: <tool and transform, or "none — <why>">
  gate: <command>
  residue: <n>
```

Worked example:

```
mechanical-first:
  inventory: ast-grep run -p 'moment($$$)' -l ts --json=compact src | python3 -c 'import json,sys; print(len(json.load(sys.stdin)))'
  count: 212
  recipe_checked: npx @date-fns/upgrade — no such codemod; jscodeshift moment-to-date-fns transform — covers format/add/diff
  codemod: jscodeshift -t moment-to-date-fns.js src (self-flagged 9 sites: locale-dependent parsing)
  gate: npm test && npx tsc --noEmit
  residue: 9
```

## Form 2: the rejection

When a mechanical transform is the wrong tool, write one line, outside any code block:

```
mechanical-first: rejected — <reason>
```

The separator is an em dash (`—`) with a space on each side, and the reason is not empty, for
example `mechanical-first: rejected — 3 sites, each semantically different`.

## What fails

- no block and no rejection (a hand edit with no decision);
- a block outside a fence: the block is always fenced (``` or ~~~), and a fence closes only on a
  bare run of the same character at least as long as the one that opened it;
- a block whose first line is not exactly `mechanical-first:`, or that holds an unknown key: the
  six keys are the whole block (no `- ` list markers, no extra notes; put notes outside it);
- a block missing a key, a key with an empty value, or a key given twice;
- `count` or `residue` that is not a whole number (at most 9 digits), or `residue` greater than
  `count`;
- a rejection with no reason, or with anything but an em dash (`—`) after `rejected`;
- more than one decision.

A decision quoted as code is not a decision: a rejection inside a fence (a list item's or a
block quote's included), inside an inline code span, or indented 4 spaces or a tab (an indented
code block), does not count. Count sites from structured matches, not from
printed lines: a tool's human output can split one match over several lines or merge two.

Check it: `wicked-garden run scripts/engineering/mechanical_first.py check <file>` (or `-` for
stdin) prints `{"ok": …, "form": "block" | "rejected" | null, "errors": [...], "block": {…} | null}` and exits 0 when
the text holds a valid form, 1 when it does not, 2 on a usage error.
