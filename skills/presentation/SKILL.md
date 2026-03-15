---
name: presentation
description: |
  Presentation creation skill. Use when: "make a deck", "build a presentation", "I need slides
  on X", "turn this into a presentation", "make a reveal.js deck", "learn my brand", "extract
  styles", "sync registry", "render as HTML." Four creation modes (brainstorm, create, fast path,
  overview), style learning from existing assets, shared design registry, and dual-format rendering
  to .pptx (PptxGenJS) and self-contained .html (reveal.js) from a single deck spec.
disable-model-invocation: true
---

# Presentation

Creates presentations as `.pptx`, self-contained `.html` (reveal.js), or both — from ideas, content,
or both. Learns visual style from existing assets. Integrates with `brainstorm` and `research`
skills. Backed by a shared git design registry. Generates a single **Deck Spec** (structured JSON)
and renders to any requested format — content is generated once, rendered anywhere.

---

## Quick Reference

| What you want | How to invoke |
|---|---|
| Learn style from existing decks/assets | Say "learn my brand" or "extract styles from [path]" → [learn.md](refs/learn.md) |
| Full interactive creation | Say "make a presentation" or "build a deck" → choose brainstorm or create mode |
| Fast, minimal-questions creation | Say "quickly make a deck on [topic]" or "fast path for [topic]" |
| Skeleton structure only | Say "give me a deck outline for [topic]" |
| Output as PPTX | Request "pptx format" or "PowerPoint" (default) |
| Output as HTML (reveal.js) | Request "html format" or "reveal.js" |
| Output both formats | Request "both formats" |
| Re-render existing spec to new format | Say "re-render [deck-name] as html" |
| Audit deck quality | Say "audit [deck-name]" or "audit my deck" → [audit.md](refs/audit.md) |
| Check CSS zones and layout contract | Say "check CSS" or "validate zones" → [css-contract.md](refs/css-contract.md) |
| Check cross-deck consistency | Say "check consistency" or "compare [deck-a] and [deck-b]" → [consistency.md](refs/consistency.md) |
| Lint content quality | Say "lint my deck" or "check content" → [content-lint.md](refs/content-lint.md) |
| Set layout fidelity | Request "best fidelity", "draft fidelity", or "rough fidelity" |
| Fidelity details | [fidelity.md](refs/fidelity.md) |
| Manage style profiles | Say "list my profiles" or "manage profiles" → [profiles.md](refs/profiles.md) |
| Shared design registry | Say "sync registry" or "pull registry assets" → [registry.md](refs/registry.md) |
| Version history | Say "show version history for [deck]" |
| Full wizard reference | [wizard.md](refs/wizard.md) |
| Output format details | [output-formats.md](refs/output-formats.md) |
| Image sourcing rules | [images.md](refs/images.md) |
| Slide template library | [templates.md](refs/templates.md) |

---

## Entry Points

### Standard Start

Say "make a presentation" or "build a deck" to launch the creation wizard. Optionally specify
format upfront: "make a reveal.js presentation" (html) or "create a deck in both pptx and html."
Specify fidelity upfront if needed: "best fidelity", "draft", or "rough." Read
[wizard.md](refs/wizard.md) for full question flows. Read [fidelity.md](refs/fidelity.md) for
what each fidelity level does.

### Fast Path

Say "quickly make a deck on [topic]" or "fast path for [topic]" for one-input, no-further-questions
generation. Uses last-used profile or default. Fidelity defaults to `draft`. Flags conflicts rather
than asking. Produces versioned output and a one-line decision summary. Optionally specify format
("fast deck on [topic] as html") or fidelity ("fast, best fidelity").

### Overview

Say "give me a deck outline for [topic]" or "skeleton deck on [topic]" for two-question generation.
Produces a skeleton deck in default format — section dividers, placeholder content slides, no filler
content. Designed for human completion or as input to a subsequent create run.

### Learn

Say "learn my brand" or "extract styles from [path]" to run style extraction on PPTX, PDF, or
image assets. Saves a named style profile for future decks. Read [learn.md](refs/learn.md).

### Render (re-render existing spec)

Say "re-render [deck-name] as html" or "re-render [deck-name] to pptx" to render an existing
Deck Spec to a new format without regenerating content. Any prior version can be re-rendered to
any supported format. Read [output-formats.md](refs/output-formats.md).

### Profile Management

Say "list my profiles", "export profile [name]", "import profile [file]", or "set default profile
[name]" to manage style profiles. Say "assemble a profile" for the interactive assembly flow.
Read [profiles.md](refs/profiles.md).

### Registry

Say "sync registry", "pull registry assets", "push palette [name]", or "list registry" to manage
the shared design asset registry. Read [registry.md](refs/registry.md).

### Versions

Say "show version history for [deck]" to list all versions with metadata. Say "diff v1 and v2 for
[deck]" to get a structural diff summary.

### Audit

Say "audit [deck-name]" or "audit my deck" for a full quality score across structure, content,
CSS, consistency, and lint categories. Say "compare [deck-a] and [deck-b]" for cross-deck
consistency analysis. Say "lint my deck" for content-only checks. Read [audit.md](refs/audit.md).

---

## Plugin Storage

All persistent state lives in plugin storage (managed by wicked-garden's plugin storage API).
Never hardcode paths. Use the storage keys defined in each reference file. Storage namespaces:

| Namespace | Contents |
|---|---|
| `presentation:profiles` | Learned and assembled style profiles |
| `presentation:index` | Content index metadata |
| `presentation:versions` | Version history records |
| `presentation:specs` | Deck Spec JSON — one per version, the canonical intermediate representation |
| `presentation:registry-cache` | Local copy of pulled registry assets |
| `presentation:session` | Current session state (last-used profile, mode, format, fidelity, etc.) |

---

## Hint System

Contextual hints fire automatically during creation flows — missing profiles, content gaps, format
suggestions, registry sync reminders, and more. See [hints.md](refs/hints.md) for the full hint
table and edge case handling.

---

## Dependency Check (run at startup)

```
brainstorm skill  → available / not available (degrade gracefully)
research skill    → available / not available (degrade gracefully)
registry remote   → reachable / unreachable (warn, continue offline)
content index     → exists / stale / missing (offer to build)
style profile     → loaded / missing (offer learn or built-in)
```

Show a compact status summary at startup if any dependency is missing or stale.

---

> **Note**: Slash command entry points (`/wicked-garden:presentation:*`) are planned as a follow-on
> project. Until then, this skill is activated automatically by smaht context assembly when
> presentation intent is detected. Natural language invocation ("make a deck", "build a
> presentation") routes here without explicit command invocation.

## Reference Files

Read these on demand — do not load all at once.

| File | Read when... |
|---|---|
| [wizard.md](refs/wizard.md) | Running any creation flow — has full question sequences for all four modes |
| [output-formats.md](refs/output-formats.md) | Output format selected, render requested, or format questions arise |
| [fidelity.md](refs/fidelity.md) | Fidelity level selected or quality/layout behavior questions arise |
| [learn.md](refs/learn.md) | User requests style extraction, or style extraction is needed |
| [profiles.md](refs/profiles.md) | User manages profiles, or profile selection is needed during wizard |
| [registry.md](refs/registry.md) | User requests registry operations, or registry assets are needed during creation |
| [templates.md](refs/templates.md) | Selecting slide layouts during generation |
| [images.md](refs/images.md) | Sourcing images for any slide |
| [versioning.md](refs/versioning.md) | Any version-related operation |
| [hints.md](refs/hints.md) | Extended hint logic and edge case handling |
| [audit.md](refs/audit.md) | Running a quality audit or re-audit on a deck |
| [css-contract.md](refs/css-contract.md) | CSS zone class definitions and visual QA contract |
| [consistency.md](refs/consistency.md) | Cross-deck or within-deck consistency checks |
| [content-lint.md](refs/content-lint.md) | Content quality lint rules and findings |
| [edit-coordination.md](refs/edit-coordination.md) | Session lock and render guard coordination |
