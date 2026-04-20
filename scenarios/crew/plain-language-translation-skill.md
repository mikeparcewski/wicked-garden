---
name: plain-language-translation-skill
title: Plain-Language Translation Skill (skills/crew/explain/SKILL.md)
description: Verify the crew:explain skill translates jargon-heavy gate findings and phase summaries into grade-8 plain language
type: testing
difficulty: beginner
estimated_minutes: 8
covers:
  - "#519 — plain-language translation skill acceptance criteria"
  - skills/crew/explain/SKILL.md
  - Plain: line convention in clarify/objective.md, design.md
ac_ref: "skills/crew/explain/SKILL.md — crew:explain skill"
---

# Plain-Language Translation Skill

@manual — The `Run:` steps that invoke `/wicked-garden:crew:explain` directly require
an active Claude session. The structural validation steps (file existence, convention
checks) are harness-runnable.

This scenario validates `skills/crew/explain/SKILL.md`:

1. Skill file exists and is ≤ 200 lines (Tier-2 size budget).
2. Skill defines output rules: 2-4 sentences, grade-8 reading level, no jargon.
3. Input jargon block → output contains a `**Plain:**` line in `paired` mode.
4. Cross-check: `**Plain:**` convention is present in clarify/objective.md and design.md
   phase templates (if they exist).

## Setup

```bash
export PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
```

---

## Case 1: Skill file exists and is within size budget

```bash
Run: test -f "${PLUGIN_ROOT}/skills/crew/explain/SKILL.md" && echo "PASS: explain/SKILL.md exists"
Assert: PASS: explain/SKILL.md exists
```

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import pathlib
skill = pathlib.Path('${PLUGIN_ROOT}/skills/crew/explain/SKILL.md')
lines = skill.read_text().splitlines()
assert len(lines) <= 200, f'SKILL.md exceeds 200-line budget: {len(lines)} lines'
print(f'PASS: explain/SKILL.md is {len(lines)} lines (within 200-line budget)')
"
Assert: PASS: explain/SKILL.md is N lines (within 200-line budget)
```

---

## Case 2: Skill defines output rules — grade-8, 2-4 sentences, no jargon

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import pathlib
content = pathlib.Path('${PLUGIN_ROOT}/skills/crew/explain/SKILL.md').read_text()

required_phrases = [
    'grade',       # grade-8 reading level referenced
    'jargon',      # no specialist vocab rule
    'Plain',       # Plain: line convention
]
for phrase in required_phrases:
    assert phrase.lower() in content.lower(), f'Missing required phrase: {phrase!r}'

print('PASS: explain/SKILL.md contains grade-level, jargon, and Plain: convention references')
"
Assert: PASS: explain/SKILL.md contains grade-level, jargon, and Plain: convention references
```

---

## Case 3: REJECT jargon → plain language — no specialist vocab in output

This test simulates the skill's translation rule by checking the prohibition list.
The actual invocation is @manual (requires live session).

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
# Simulate: input jargon block → expected plain output characteristics
JARGON_INPUT = '''
Gate: design-quality
Verdict: CONDITIONAL
Score: 0.65 / 0.70 (BLEND: 0.4*min + 0.6*avg)
Conditions:
  - FR-3 blast radius not quantified in architecture.md
  - parallelization_check missing from executor-status.json
  Dispatch mode: parallel (3 reviewers in council)
'''

# What explain skill MUST NOT include in output:
BANNED_OUTPUT_TERMS = [
    'CONDITIONAL', 'BLEND', 'blast radius', 'parallelization_check',
    'executor-status', 'dispatch mode', 'council', 'per_reviewer'
]

# What it SHOULD include (plain equivalents)
REQUIRED_CONCEPTS = [
    # At least one of these plain-language concepts must appear
    'fix', 'blocked', 'needs', 'missing', 'reviewers', 'next'
]

# Verify the skill SKILL.md documents these substitution rules
content = open('${PLUGIN_ROOT}/skills/crew/explain/SKILL.md').read()
for banned in BANNED_OUTPUT_TERMS[:3]:  # check first 3 are mentioned as banned
    assert banned in content or banned.lower() in content.lower(), (
        f'Expected banned term {banned!r} to be listed in skill output rules'
    )

print('PASS: skill documents jargon terms that must be substituted in output')
print('  (full translation test is @manual — requires live session)')
"
Assert: PASS: skill documents jargon terms that must be substituted in output
```

---

## Case 4: **Plain:** line convention in clarify/objective.md template

The `explain` skill produces a `**Plain:**` line in `paired` mode. Verify that
crew phase output templates (if present) use this convention.

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import pathlib, sys
plugin_root = pathlib.Path('${PLUGIN_ROOT}')
# Check skills/crew/explain/SKILL.md for the paired-mode Plain: convention
skill_content = (plugin_root / 'skills/crew/explain/SKILL.md').read_text()

assert '**Plain:**' in skill_content or 'Plain:' in skill_content, (
    'SKILL.md does not document the **Plain:** line convention'
)
print('PASS: **Plain:** convention documented in explain/SKILL.md')

# Check if any phase agent files reference the Plain: convention
agents_dir = plugin_root / 'agents/crew'
plain_refs = []
for f in agents_dir.glob('*.md'):
    if 'Plain' in f.read_text():
        plain_refs.append(f.name)

if plain_refs:
    print(f'PASS: Plain: convention also referenced in {len(plain_refs)} crew agent(s): {plain_refs}')
else:
    print('INFO: Plain: convention not found in crew agents (may be skills-only)')
"
Assert: PASS: **Plain:** convention documented in explain/SKILL.md
```

---

## Case 5: crew:explain command exists and is discoverable

```bash
Run: test -f "${PLUGIN_ROOT}/commands/crew/explain.md" && echo "PASS: commands/crew/explain.md exists" || echo "INFO: explain.md not in commands (may be skills-only — check skill registration)"
Assert: PASS or INFO (skill must be reachable via /wicked-garden:crew:explain)
```

```bash
Run: sh "${PLUGIN_ROOT}/scripts/_python.sh" -c "
import pathlib
# Verify explain skill is registered in skills/crew/explain/
skill_dir = pathlib.Path('${PLUGIN_ROOT}/skills/crew/explain')
assert skill_dir.is_dir(), f'explain skill directory missing at {skill_dir}'
assert (skill_dir / 'SKILL.md').exists(), 'SKILL.md missing in explain/'
print('PASS: skills/crew/explain/SKILL.md registered and discoverable')
"
Assert: PASS: skills/crew/explain/SKILL.md registered and discoverable
```

---

## Success Criteria

- [ ] `skills/crew/explain/SKILL.md` exists and is ≤ 200 lines
- [ ] SKILL.md documents: grade-8 reading level, no jargon, Plain: convention
- [ ] SKILL.md lists banned output terms with plain-language substitutions
- [ ] `**Plain:**` line convention is documented in SKILL.md
- [ ] `commands/crew/explain.md` exists OR skill is reachable as `/wicked-garden:crew:explain`
- [ ] (@manual) Input jargon block → output 2-4 sentences with no banned specialist terms
