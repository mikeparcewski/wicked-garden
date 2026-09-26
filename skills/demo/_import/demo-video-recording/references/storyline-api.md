# Storyline API

A demo video is described by one **storyline module** (plain JavaScript, ESM). The runner records each segment on its
own, then stitches them into one MP4 with chapters.

```sh
cd <skill>/scripts && npm install && npx playwright install chromium    # once
node <skill>/scripts/record.mjs path/to/storyline.mjs              # record missing segments, then stitch
node <skill>/scripts/record.mjs path/to/storyline.mjs 03-search    # (re)record one or more segments, restitch
node <skill>/scripts/record.mjs path/to/storyline.mjs --all        # re-record everything
node <skill>/scripts/record.mjs path/to/storyline.mjs --stitch     # only stitch what exists
node <skill>/scripts/record.mjs path/to/storyline.mjs --reencode   # rebuild every segment from saved frames, restitch
node <skill>/scripts/record.mjs path/to/storyline.mjs --list       # segments and whether each is recorded
```

Options: `--out <dir>` (default: `demo-video/` next to the storyline), `--keep-closing` (see below). Environment: `FFMPEG` (path to ffmpeg; ffprobe
is found next to it), `DEMO_BASE_URL` (overrides `baseUrl`), `DEMO_HEADFUL=1` (show the browser while recording).

Output in `<out>/`: `<slug>.mp4` (stitched, one chapter per segment), `chapters.md`, `timings.json`, and per segment
`segments/<key>/segment.mp4` plus the raw capture (`frames/`, `timeline.json`) that `--reencode` rebuilds from.
The MP4 holds one video stream plus a small data stream: the chapter track ffmpeg writes for players that read
QuickTime-style chapters. That is expected.

## Module shape

```js
// storyline.mjs
export default {
  title: "Acme Console demo",              // video title metadata; also the output file name (slugified)
  baseUrl: "http://localhost:3000",        // the app under test
  brand: {
    name: "Acme Console",                  // shown in the window's address bar and the caption band
    logo: "./brand/logo.svg",              // optional, path relative to this file (SVG inlined)
    accent: "#ee0000",                     // kicker, callouts, chapter numbers, progress
  },
  startPath: "/",                          // optional, page each segment opens on (default "/")
  stickyOffset: 88,                        // optional, px left above tall elements scrolled into view (app header)
  locale: "en-US", timezoneId: "America/New_York",   // optional browser locale / timezone
  closingMs: 10000,                        // optional, how long the closing card holds

  // Optional: runs behind each chapter's opening slide (the slide hides it), before the app is sent to startPath.
  // Reset data, log in, pick a persona. `seg.resets` is whatever you put on the segment. Not called for intro segments.
  async beforeSegment(ctx, seg) {},

  segments: [
    { key: "00-intro", intro: true, async run(ctx) { await ctx.card(`<div data-logo></div><h1>...</h1>`, 6000); } },
    {
      key: "01-dashboard",                 // folder name and CLI handle; order in this array = order in the video
      title: "Morning triage",             // chapter title (slide, progress label, MP4 chapter)
      blurb: "One sentence on what this chapter proves.",
      tags: ["Dashboard", "Next actions"], // capability chips on the chapter slide
      resets: ["CASE-1"],                  // free-form; passed to beforeSegment
      async run(ctx) { /* see below */ },
    },
  ],

  // Optional: HTML for a closing card, given every segment's measured timings ({ key: { label: seconds } }).
  closing(allTimings) { return `<div data-logo></div><h1>...</h1>`; },
};
```

A segment with `intro: true` has no chapter slide or number and ends on its own card, so the intro cuts card-to-card
into chapter 1's slide. Every other segment opens on a full-screen chapter slide (number, "Chapter N of M", title, blurb,
tags) and ends by fading to the plain stage background, so segments join with a clean cut and never need
frame-accurate stitching.

The closing card, if any, is appended to the last segment and baked into its frames. Whenever you re-record any other
segment, the runner re-records the last segment too so the card never shows stale numbers (`--keep-closing` skips
that). Keep the last segment short (a wrap-up) for that reason.

## The `ctx` object

| Member | What it does |
|---|---|
| `ctx.app` | Playwright `FrameLocator` for the app (it runs in an iframe inside the stage). Build locators from it. |
| `ctx.page` | The stage `Page` (keyboard, `waitForResponse`, `waitForEvent("filechooser")` all see the app frame). |
| `ctx.go(path)` | Load `baseUrl + path` in the app frame and wait for the network to settle. A full reload: the window shows white for a moment, so between pages prefer clicking the app's own links (`ctx.click`), which uses its client-side routing. Use `go` for the first page of a segment. |
| `ctx.caption(kicker, title, body?, readMs?)` | Lower-third caption under the window. `body` may contain `<em>`. `readMs` defaults to a reading-time estimate. |
| `ctx.point(locator, label, { below?, hold?, reveal? })` | Scroll the element into view and draw a labelled callout around it (clipped to the visible viewport). |
| `ctx.unpoint()` | Remove the callout. |
| `ctx.click(locator, { after? })` | Animate the visible cursor to the element, ripple, click. |
| `ctx.type(locator, text, { delay? })` | Click, then type visibly. |
| `ctx.fast(label, factor, fn)` | Run `fn` (a wait on the app or a model) as a time-lapse: shows a "`factor`× · label · m:ss real time" badge and compresses the span in post. |
| `ctx.waitForResponse(regex, { method?, timeout? })` | Wait for a response from the app whose URL matches (any method unless `method` is given, e.g. `"GET"`). Create the promise **before** the click that triggers it. |
| `ctx.waitForPost(regex, timeout?)` | Shorthand for a POST response. |
| `ctx.waitVisible(locator, timeout?)` | Wait until an element is on screen, e.g. results that replace loading placeholders after the response arrives. |
| `ctx.waitForPath(regex, timeout?)` | Wait until the app's path (+ query) matches. Client-side routing changes the URL without a page load, so "network idle" can return while the old page is still showing. |
| `ctx.time(label, fn)` | Run `fn`, record its wall-clock seconds under `label` in this segment's timings, return `fn`'s result. |
| `ctx.section(title)` | The innermost `<section>` containing a heading named `title` (a trailing count badge like "Needs attention 2" is fine), else the innermost `<section>` containing that exact text. Matches outside any `<section>` (sidebar links, breadcrumbs) never count. |
| `ctx.button(re)` | A `<button>` by visible text regardless of ARIA role (tabs and toggles are often `role=radio`). |
| `ctx.card(html, ms)` / `ctx.uncard()` | Full-stage card (title, transition or closing slide). `<div data-logo></div>` renders the brand logo. |
| `ctx.hold(ms)` | Pause on the current picture. |
| `ctx.hideCursor()` | Fade the cursor out (before a closing card). |
| `ctx.timings` | This segment's timings object (written to `timings.json`). |
| `ctx.stage` | The underlying `Stage` for anything not covered above. |

## Rules of thumb

- Wait on **network responses** (`waitForResponse` / `waitForPost`), then on the result element (`waitVisible`), never on
  fixed sleeps, for anything the app computes. After a click that changes page, wait with `waitForPath` or `waitVisible`.
- Probe first: `node <skill>/scripts/probe.mjs <baseUrl> /page ...` lists headings, sections, buttons with roles,
  inputs and links, read-only, and saves a screenshot per page.
- Put the **caption before the navigation** it describes, with a short `readMs`, so the words and the picture change together.
- Keep every segment **self-contained**: it navigates from `startPath`, resets what it uses in `beforeSegment`, and never
  depends on state another segment created. Then any segment can be re-recorded alone.
- Mark real waits with `ctx.fast` and a factor (4× for chat answers, 8× for long jobs). Never cut them silently.
- Measure with `ctx.time` and put **measured** numbers on the closing card; keep estimates out of the video.
