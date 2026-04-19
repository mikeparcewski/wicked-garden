---
description: Translate jargon-heavy crew output into plain, grade-8 English
argument-hint: "<text-or-path-to-explain> [--style paired|plain-only]"
---

# /wicked-garden:crew:explain

Take any crew output — gate findings, reviewer briefs, phase summaries, process
plans — and convert the specialist vocab into plain, grade-8 English. Output is
2-4 sentences that tell the user what happened and what to do next.

> **Common pattern**: Run `/wicked-garden:crew:status` first to see project state, then
> pipe confusing output through `crew:explain` to get a plain-English summary.

## Arguments

- `<text-or-path>` — the jargon-heavy block to explain. May be inline text or a
  path to a file containing the block (e.g.
  `phases/design/gate-result.json`).
- `--style paired` — keep the original block and append a `**Plain:**` line.
- `--style plain-only` (default for direct invocation) — replace the jargon
  block entirely.

## Instructions

### 1. Determine input

If the argument starts with `./`, `/`, or `phases/`, treat it as a file path.
Otherwise, treat it as inline text to explain.

```bash
if [ -f "$ARG" ]; then
  INPUT="$(cat "$ARG")"
else
  INPUT="$ARG"
fi
```

### 2. Invoke the explain skill

Use the `wicked-garden:crew:explain` skill. Pass the input block plus the
chosen style:

```
Skill: wicked-garden:crew:explain
Args: {"text": INPUT, "style": STYLE}
```

The skill follows its SKILL.md rules: max 4 sentences, grade-8 reading level,
no specialist vocab. See `skills/crew/explain/SKILL.md` for the full rulebook.

### 3. Emit output

Print the skill's result verbatim. Do not wrap in extra prose.

## Configuration

The orchestrator honors `crew.output_style` in project config:

- `terse` — never invoke this skill (raw jargon only)
- `paired` — invoke with `--style paired` (default)
- `plain-only` — invoke with `--style plain-only`

Set at project start via `/wicked-garden:crew:profile` or by editing the
project config directly.

## Examples

```bash
# Inline text
/wicked-garden:crew:explain "Gate code-quality CONDITIONAL 0.62 < 0.70"

# From a gate-result file
/wicked-garden:crew:explain phases/design/gate-result.json

# Keep the jargon, add a plain-English line after it
/wicked-garden:crew:explain "BLEND: REJECT > CONDITIONAL > APPROVE" --style paired
```

## Notes

- This command is safe to run on any text — it never mutates project state.
- When invoked during a phase transition, the orchestrator uses `crew.output_style`
  to decide whether to append a plain-language line to every gate finding.
- The skill is also invoked automatically by reviewer briefs when
  `crew.output_style != terse`.
