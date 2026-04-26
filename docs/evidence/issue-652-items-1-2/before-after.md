# Before/After: Issue #652 Items 1+2

## File Sizes

| File | Before | After | Change |
|------|--------|-------|--------|
| `agents/jam/quick-facilitator.md` | — (new) | 89 lines | +89 |
| `agents/jam/brainstorm-facilitator.md` | 305 lines | 305 lines | unchanged |
| `skills/jam/SKILL.md` | 191 lines | 42 lines | -149 (−78%) |
| `commands/jam/quick.md` | 26 lines | 21 lines | -5 |

## What Was Removed from SKILL.md

- Persona archetype pool table (lives in `brainstorm-facilitator.md` lines 82-89)
- Convergence mode table and mechanics (lives in `brainstorm-facilitator.md` lines 96-130)
- Discussion round details (Round 1/2/3 structure — lives in agent)
- Synthesis quality section ("Good synthesis / Bad synthesis" — lives in agent)
- Multi-AI step details (lives in agent, quick-facilitator explicitly omits it)
- Full native task code blocks (lives in agent and command)
- wicked-brain integration code blocks (lives in agent)
- Crew engagement table (crew reads agent frontmatter directly)

## What Was Kept in SKILL.md

- Frontmatter description
- Session types: 3 one-liner bullets (quick / brainstorm / council)
- Quick-start dispatch examples (one per session type)
- Agent cross-references (`quick-facilitator.md`, `brainstorm-facilitator.md`)
- refs/ cross-references

## Dependency Check

No bidirectional dependency found. `brainstorm-facilitator.md` does not reference
`SKILL.md` content — all convergence/persona mechanics in the agent are self-contained.
The SKILL.md archetype table was a duplicate of content already in the agent.
Safe to remove from SKILL.md.
