# Surfaces: the protocol-2 declaration and its messages

DES-EDITOR-PLUGIN-CONTRACT-001 §5-§6. The host renders an editor's three surfaces from ONE declaration,
`surfaces` in `wicked-pack.json` (`editors[]`), echoed in `plugin.ready.payload.surfaces`. The two must be the
same canonical JSON (conformance case 13), or the host refuses protocol 2 and shows the editor the protocol-1
way. `surfaces` is required when `protocol` lists 2 and refused when it doesn't (`pack check` PK069).

## Shape

```jsonc
"protocol": [1, 2],
"surfaces": {
  "card": {                                   // required
    "interactive": true,                      // the frame takes pointer and keys in the card (default false)
    "aspect": "auto",                         // "16:9" (default) | "4:3" | "auto": you report ui.height
    "actions": [                              // ≤ 4, drawn by the HOST in the card footer
      { "id": "next", "label": "Next part", "verb": "plugin" },     // host.action {id} to you
      { "id": "ask", "label": "Ask about it", "verb": "host:ask" }  // the host's own; host:export needs artifact.export
    ]
  },
  "options": { "tabs": [                      // ≤ 5, added to the host panel on Options
    { "id": "parts", "label": "Parts", "render": "plugin" },        // a frame of yours, told host.tab
    { "id": "view", "label": "View", "render": "controls", "controls": [
      { "id": "density", "label": "Density", "type": "segmented",
        "options": [{ "id": "roomy", "label": "Roomy" }, { "id": "compact", "label": "Compact" }] },
      { "id": "numbers", "label": "Show numbers", "type": "toggle" } ] } ] },
  "full": { "modes": ["simple", "advanced"], "default": "simple" }  // omit modes for one mode
}
```

Rules (garden's `pack check`, crew's registry and studio's host apply the same ones):

- Ids `^[a-z][a-z0-9-]{0,31}$`, unique per scope (actions; tabs; controls in a tab; options in a control).
- Labels 1-24 characters of `A-Z a-z 0-9`, space and `·-'`; no word mixing letters and digits; no word that
  starts with a host decision word (approve, accept, deliver, merge, send, launch, delete, remove, stop, deny,
  allow, grant, install), look-alikes included. Those verbs are host controls only.
- Controls: `toggle`, `segmented` / `select` (2-8 options), `color`, `text` (`maxChars` 1-200, default 200),
  `range` (finite `min < max`, `0 < step ≤ max - min`, bounds within ±1e9, `step ≥ 1e-6`, at most 1e6 steps,
  and `step ≥ max(|min|, |max|) × 1e-12`). At most 12 per tab. No HTML, no conditionals.
- `full.modes` is exactly `["simple","advanced"]`; `default` needs `modes`. No `options` = no Options button;
  no `full` = no Full screen button.
- Unknown fields refuse the whole declaration.

## Messages (protocol 2 only; all keep the `{p:'wicked.editor', v:1}` envelope)

| Direction | type | kind | payload → reply |
|---|---|---|---|
| host → you | `host.hello` | event | v1 fields + `protocol` (1 or 2), `surface` (`card` / `options` / `full`), `tab?`, `mode?` |
| host → you | `host.surface` | event | `{surface, mode?}`: the card ↔ full morph of THIS instance; never reload or re-read |
| host → you | `host.mode` | request | `{mode}` → `{mode}`: the mode you now show (full screen only; answer within 2 s) |
| host → you | `host.action` | request | `{id}` → `{handled, status?}` (≤ 120 chars). Carries NO user activation: act only through granted requests |
| host → you | `host.tab` | event | `{tab}`: which plugin tab the options instance shows |
| host → you | `host.selection` | event | `{anchors}`: another surface of the same artifact pointed |
| host → you | `options.changed` | request | `{tab, id, value}` → `{applied, rev, values, reason?}`; bump `rev` on every change of your truth |
| you → host | `options.values` | event | `{tab, rev, values}`: the options instance sends one per controls tab when it starts |
| you → host | `ui.height` | event | `{px}`: card with `aspect:"auto"` only; clamped to 120-560 |
| you → host | `ui.morph` | event | `{to: 'full' | 'card'}`: ask the host to morph |
| you → host | `theme.set` | request | `{base, tokens}` → `{version}`; `head_moved` when the head moved. Needs `artifact.theme` |

A protocol-1 host never sends these; a protocol-2 host sends them only to an editor that negotiated 2.

## Conformance (cases 13-17)

13 the surfaces the host renders are the manifest's · 14 the card mounts, `ui.height` within 2 s when `auto`,
every `plugin` action answered within 2 s · 15 every plugin tab mounts as an options instance and survives
`host.selection`; each controls tab's `options.values` is accepted, and a valid change is answered within 2 s, applied or refused · 16 card → full
keeps the instance (no reload, no second `plugin.ready`); each mode echoed within 2 s · 17 (protocol-1 editors)
cases 1-12 under the protocol-2 host. The activation rule (a `host.action` cannot authorize a `tools/call`) is
the host's, checked in studio's CI.
