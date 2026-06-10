# wickedagile — brand palette & type

The brand system for **wickedagile** and everything built on it (wicked-garden,
the wicked-\* tools, decks, docs, future properties). The garden is *content*
that sits on this substrate — the brand is not the garden.

Decided 2026-06-09 (palette supplied by Michael; harbor-blue ground). Live
implementation: `src/styles/global.css`.

## The palette (the seven)

| Hex | Name | Role |
|---|---|---|
| `#356d8c` | harbor blue | THE brand blue — deepened to `#224a60` as the day canvas (panels/surfaces step back up toward it) |
| `#eae5b6` | butter | type, in both themes |
| `#ffda19` | signal yellow | THE brand accent — CTAs, wordmark, stamps |
| `#c6a413` | mustard | foundation hue, floor stamps |
| `#313132` | charcoal | night canvas family, type-on-yellow |
| `#9d4f56` | wine | creation/solo hue (lifted on the blue ground) |
| `#60acc6` | sky | workflow/layers hue |

Vintage harbor-poster energy: a blue ground, butter type, and a signal-yellow
stamp, with mustard, wine, and sky doing the supporting work.

## Neutrals (the substrate)

| Token | Day (default) | Night (`.dark`) | Use |
|---|---|---|---|
| canvas | `#224a60` deep harbor | `#232324` charcoal | page background |
| canvas-2 | `#1c4053` | `#2a2a2b` | footer / recessed bands |
| surface | `#2a566e` | `#313132` | cards, panels |
| surface-2 | `#315f7a` | `#3a3a3b` | nested surfaces |
| ink | `#eae5b6` butter | `#eae5b6` butter | type |
| muted | `#b9d2df` mist | `#b7b3a4` stone | secondary type |

The ground is blue by day and charcoal by night — butter type on both. There
is no white-paper mode; the blue IS the brand.

## Brand accent

| Token | Day | Night | Use |
|---|---|---|---|
| accent | `#ffda19` signal yellow | `#ffda19` | CTAs, links, wordmark "agile", focus rings |
| accent-bright | `#ffe45c` | `#ffe45c` | vines, selection, glows |
| on-accent | `#313132` charcoal | `#1e1e1f` | type on yellow fills |

Yellow is a *stamp*, not a wash — it never becomes a background tint.

## Support hues

`--ct-*` variants are the AA text-safe versions — on the blue ground they are
*lightened* (the inverse of a paper theme); on charcoal the lifted values pass
as-is.

| Hue | Day | Day text (`ct`) | Night | Voice |
|---|---|---|---|---|
| foundation (mustard) | `#c6a413` | `#efdc8a` | `#d8b82e` | groundwork, memory |
| workflow (sky) | `#60acc6` | `#bfe4f4` | `#60acc6` | process, verification |
| creation (wine) | `#d8868e` lifted | `#f2d4d7` | `#c67079` | making, output |

### Garden role mapping (content-level, wicked-garden only)

| Role | Token | Day | Night |
|---|---|---|---|
| the gate | `--c-gate` | `#ffda19` yellow | `#ffda19` |
| the floor | `--c-floor` | `#c6a413` mustard | `#d8b82e` |
| the layers | `--c-layer` | `#60acc6` sky | `#60acc6` |
| solo beds | `--c-solo` | `#c97f87` wine (lifted) | `#c67079` |

These are stamps on the brand ground — garden semantics, not brand identity.

## Type

| Role | Face | Notes |
|---|---|---|
| Display | **Archivo Variable**, weight 800–900, `font-stretch: 122%` | the loud Swiss voice; headlines, wordmark |
| Body | **Hanken Grotesk Variable** | calm humanist counterweight |
| Mono | **JetBrains Mono Variable** | kickers (letter-spaced uppercase), commands, chips, stats |

All self-hosted via Fontsource. The expanded width axis IS the display
identity — never use Archivo at normal width for headlines.

## Texture & gesture

- **Word-vines** — a plant grows from beneath key words (stem along the
  baseline, leaves, a curling tendril) in the word's hue. Lives in
  `components/react/Marker.tsx`.
- **Film grain** — fixed SVG-noise overlay.
- **Grid floor** — faint 64px butter-hairline grid, radially masked.
- **Pills** — fully-rounded buttons/chips, mono uppercase, letter-spaced.

## Rules

1. The ground is harbor blue (day) or charcoal (night); yellow stays a stamp.
2. One support hue per moment — never rainbow a section.
3. Small colored text on the blue ground uses the lightened `--ct-*` value (AA).
4. Display = Archivo expanded 800+; if it's not expanded, it's not display.
5. Night mode is a first-class twin, not an afterthought.
