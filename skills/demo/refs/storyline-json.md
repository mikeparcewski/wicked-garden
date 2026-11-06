# storyline.json: the storyline as data (crew Demo video runs)

In a crew Demo video run the recording is made by the engine's `demo_record` step on the host, inside its jail,
with network to the app's one port. It runs no code you write: it takes `storyline.json`, checks it, and compiles
it into the same recorder `storyline.mjs` drives by hand (`refs/storyline-api.md`). The person approves the
storyline at the plan gate; the recorder reads the approved copy, not your later edits.

## Files (in the plan directory your step names)

- `chapters.json`: `[{"key": "01-board", "title": "The board", "blurb": "...", "tags": [], "resets": []}]`
- `storyline.json`: its `segments` keys equal `chapters.json`'s keys, in the same order.
- `script.md`: the presenter script (unchanged).

## Shape

```json
{
  "title": "Escalations demo",
  "ready": {"role": "heading", "name": "Escalations"},
  "intro": {"title": "Escalations, at a glance", "body": "Three minutes", "ms": 5000},
  "segments": [
    {"key": "01-board", "title": "The board", "blurb": "Where the day starts", "tags": ["read-only"],
     "steps": [
       {"caption": {"kicker": "Board", "title": "Everything open, by region", "readMs": 3000}},
       {"point": {"target": {"section": "Open tickets"}, "label": "Open now"}},
       {"time": {"label": "load", "steps": [
         {"click": {"target": {"role": "tab", "name": "How it counts"}}},
         {"waitVisible": {"target": {"text": "How it counts"}}}]}},
       {"hold": {"ms": 1500}}
     ]}
  ],
  "closing": {"title": "Thanks", "body": "Loaded in {{timings.01-board.load}}", "ms": 8000}
}
```

- `ready`: a target that proves the app rendered. Each chapter starts on the launch page and waits for it (30 s);
  never seeing it fails the take `app_not_ready`. Pick it from the probe summary.
- `intro`, `closing`, `brand: {name, accent: "#rrggbb"}`: optional.

## Steps (exactly one verb per step)

| Step | Fields |
|---|---|
| `go` | `path`: a path starting with `/`, under the app's launch path (letters, digits and `._~%/?&=+-`) |
| `caption` | `kicker`, `title`, `body?`, `readMs?` |
| `point` / `unpoint` | `target`, `label` / `{}` |
| `click` | `target` |
| `type` | `target`, `text` |
| `hold` | `ms` |
| `card` | `title`, `body?`, `ms` (shows, holds, removes itself) |
| `waitVisible` | `target` |
| `waitForPath` | `path`: waits until the app is at that path or below it (under the launch path) |
| `fast` | `label`, `factor` (2-16), `until: {target}` or `until: {path}` — a time-lapse over a real wait (up to 120 s) |
| `time` | `label` (letters, digits, spaces, `._-`), `steps` — measures them into the chapter's timings (not nested) |

A `target` is one of `{"role": "button", "name": "Save"}`, `{"text": "..."}`, `{"section": "<heading>"}`,
`{"button": "<visible text>"}`, `{"testId": "..."}`, `{"css": "..."}`, with optional `"nth": 0` and `"exact": true`.
Add `"in": "content"` when the target is inside the app's own frame (a crew app renders its pages, charts and
tables in a frame inside the page): the probe summary lists such frames under `frames`.

Limits: 12 chapters, 60 steps a chapter, 30 s for any `ms` (an intro at least 1.5 s), keys at most 48 characters
(`^[a-z0-9][a-z0-9-]*$`, not `intro`), plain text only (no HTML), 64 KB a file. Every wait gives up after 30 s
(`fast`: 120 s). A storyline whose own fixed timing passes 12 minutes is refused: its holds, captions, cards and
each step's motion, plus about 12 s a chapter for its card, the launch page and the ready check (a wait counts its
minimum, not its timeout).

## What fails a take (and comes back to you)

| Cause | Means |
|---|---|
| `storyline_refused` | a field this form does not take, or a limit; the reason names the field |
| `app_not_ready` | the `ready` target never showed, or an app page did not load |
| `left_app` | a click or `go` took the app frame out of the launch path |
| `side_effect_blocked` | the app tried a request the recorder refuses (any write but the app's own query, another origin) |
| `chapter_mismatch` | the video's chapters are not the approved ones |

The recorder is read-only: show a control, never press one that saves, launches, approves or deletes. It opens no
popup and starts no web worker. When the host itself cannot record (no ffmpeg or browser, the app not answering,
the capture stalling), the run stops at a gate that offers a retry; the take never comes back to you for that.
