---
name: presentation
namespace: wicked-garden:presentation:presentation
description: >
  Full-featured presentation creation skill for wicked-garden. Use this skill whenever the user
  wants to create, plan, or brainstorm a presentation in any format — especially when they mention
  slides, decks, topics, content directories, or say things like "make a deck", "build a
  presentation", "I need slides on X", "turn this into a presentation", "show this as an HTML
  page", or "make a reveal.js deck." Also triggers on: "learn my brand", "extract styles from
  this deck", "sync registry", "what templates do I have", "render as HTML", or any request
  to create a presentation with style awareness or content sourcing. This skill coordinates the
  full workflow: style learning from existing assets, content indexing, integration with brainstorm
  and research capabilities, registry sync, four distinct creation modes (interactive brainstorm,
  content-driven create, fast path, overview), and dual-format rendering to .pptx (via PptxGenJS)
  and/or self-contained .html (via reveal.js) from a single deck spec.
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

Fire contextual hints whenever these conditions are detected. Hints are brief, actionable, friendly.

| Condition | Hint |
|---|---|
| No style profile exists | *"No style profile found — using minimal light. Run style extraction on existing decks to match your brand."* |
| Topic only, no content, research off | *"This will be AI-generated without source material. Consider enabling research or providing a content directory."* |
| Slide count >> content volume | *"That's a lot of slides for the content available — I'd suggest N. Want me to adjust?"* |
| Index has relevant content | *"Found related content in your index — want to include it?"* |
| `brainstorm` skill unavailable | *"Brainstorm skill not found — starting in create mode instead."* |
| `research` skill unavailable | *"Research skill not found — I'll work with what you provide."* |
| No content + no research + shallow topic | *"Not much to work with yet. Try: providing a file, enabling research, or expanding the topic description."* |
| Image/PDF provided without context | *"Got it. Should I use these for content, style reference, or both?"* |
| Prior versions exist for this topic | *"Found prior versions of a deck on this topic — start fresh or build from the latest?"* |
| Registry available but not synced | *"Your design registry hasn't been synced this session — want to pull latest?"* |
| Unsplash chosen, no attribution preference set | *"Unsplash images require attribution — I'll add it to speaker notes by default. Change this in your profile."* |
| Format not set, deck will be shared as URL | *"This looks like something you'd share as a link — HTML output might work better. Want to switch or add both formats?"* |
| Format not set, deck needs post-editing | *"Looks like you'll want to edit this after — use pptx format to keep it editable in PowerPoint."* |

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
