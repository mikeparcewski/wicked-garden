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

- `ready`: a target that proves the app rendered, so pick the app's own content, not a toolbar or chrome around
  it. Each chapter gets ready behind its chapter card, before anything is on screen:
  1. The launch page loads.
  2. The network goes quiet.
  3. `ready` becomes visible.
  4. The chapter's first target becomes visible. That is the first required `waitVisible`, `point`, `click` or
     `type` before any `go`, `waitForPath`, `fast` or `time`.

  Each target gets up to 60 s. Never seeing one fails the take `app_not_ready`, naming the target. A slow app's
  extra wait is cut from the video (the frames cut show only the card).
- `hide`: chrome to keep out of the picture, such as a dev banner or a cookie bar. It is a list of at most 12
  `{"css": "<one selector>", "in"?: "content"}`, hidden with `display: none` for the whole take. Never write a
  step to dismiss chrome: hide it.
- `intro`, `closing`, `brand: {name, accent: "#rrggbb"}`: optional.

**A crew app** (the probe's `result.json` says `"recorded_view": "app_frame"`): the video shows only the app's
own frame. Studio's page around it (banners, the chat, the sidebar) is never filmed, so there is nothing to
dismiss. Every target, `ready` included, carries `"in": "content"`; one that does not is refused, naming the
field.

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

Any `click`, `point` or `waitVisible` may add `"optional": true` beside its verb, for example
`{"click": {"target": {...}}, "optional": true}`. An optional step whose target is not there within 5 s, or whose
action fails, is skipped and listed in `record.json` (`skipped_steps`). Use it for nice-to-have moments only,
never for the point of the demo and never inside `time`. A required step that fails fails the chapter, and the
reason names the step (`storyline.segments[1].steps[8] (click role "button" "…")`).

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
| `app_not_ready` | the `ready` target or the chapter's first target never showed, or an app page did not load |
| `step_failed` | a required step failed; the reason names it (`storyline.segments[i].steps[j] (verb target)`) |
| `left_app` | a click or `go` took the app frame out of the launch path |
| `side_effect_blocked` | the app tried a request the recorder refuses (any write but the app's own query, another origin) |
| `chapter_mismatch` | the video's chapters are not the approved ones |

The recorder is read-only: show a control, never press one that saves, launches, approves or deletes. It opens no
popup and starts no web worker. When the host itself cannot record (no ffmpeg or browser, the app not answering,
the capture stalling), the run stops at a gate that offers a retry; the take never comes back to you for that.
