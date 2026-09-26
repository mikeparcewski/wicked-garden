---
name: demo-video-recording
description: Records polished, captioned product demo videos of a running web app with Playwright, a live walkthrough turned into an offline demo. The app plays inside a browser-window frame on a 1920x1080 stage, with a lower-third caption band beneath it (captions never cover the UI), a visible cursor with click ripples, labelled callouts, chapter slides between segments, an honest time-lapse badge for real waits and a closing card with measured timings. Each chapter is recorded as its own segment with its own data reset, so any one can be re-recorded, then all are stitched into one H.264 MP4 with chapter markers. Use when asked to record, capture or produce a product demo video, screen recording, walkthrough video, feature tour or offline demo; to add captions, lower thirds, callouts or transitions to a recording; or to re-record or stitch demo segments.
license: MIT
compatibility: Requires Node 20+, ffmpeg and ffprobe on the PATH, Playwright with Chromium (npm install and npx playwright install chromium in scripts/), and the web app under demo running and reachable.
metadata:
  version: "1.0"
---

# Demo video recording

Turn a planned demo into a captioned, chaptered video that looks produced rather than screen-grabbed, and that you
can re-record piece by piece when the product or the data changes.

## When to use

- Someone wants a demo video, a walkthrough, a feature tour or an "offline demo" of a web app.
- A recording needs captions, callouts, chapter slides or a professional frame.
- An existing demo video needs one section redone, or segments stitched into one file.

Plan the story first. If there is no chapter list and case bank yet, use the **demo-planning** skill. After
recording, check the result with the **demo-video-review** skill.

## The design in one screen

- **Stage.** The app runs in an iframe inside a browser-style window (1600x900 with a title bar showing the brand name
  and current path) on a 1920x1080 canvas. Captions live in a band *below* the window, so they never cover the UI.
- **Lower-third caption.** Kicker (small, accent colour, uppercase), title (one line), body (up to two lines, muted).
  The brand block and chapter progress sit on the right of the band.
- **Cursor and callouts.** A drawn cursor glides to each target and ripples on click (headless browsers show no
  mouse). Callouts are accent-outlined boxes with a short dark label, clipped to the visible viewport.
- **Chapter slides.** Each segment opens on a full-stage slide (big number, "Chapter N of M", title, one-sentence
  blurb, capability tags) and ends by fading to the plain background, so joins are clean cuts.
- **Honest time-lapse.** Real waits (a model, a job, an upload) run inside `ctx.fast(...)`: the on-screen badge
  shows the factor and the real elapsed time, and post-processing compresses only that span.
- **Measured closing card.** Timings recorded with `ctx.time(...)` feed the closing card. Estimates never appear.
- **Quality capture.** Chrome DevTools screencast frames (JPEG q95, wall-clock timestamps) are resampled to a constant
  30 fps and encoded to H.264 (CRF 17) with MP4 chapter markers. Playwright's built-in video is too soft for text.

Details: [references/stage-design.md](references/stage-design.md). API: [references/storyline-api.md](references/storyline-api.md).
Failure modes and fixes: [references/gotchas.md](references/gotchas.md).

## Workflow

1. **Plan.** One chapter per capability, in story order, each with the cases it uses and how to reset them
   (demo-planning skill). Rehearse the flows live once so captions describe what really appears.
2. **Install.** `cd scripts && npm install && npx playwright install chromium` (once per machine). Check
   `ffmpeg -version` and `ffprobe -version` work, or set `FFMPEG` to the ffmpeg binary.
3. **Write the storyline.** Copy [assets/example-storyline.mjs](assets/example-storyline.mjs) next to your project
   (for example `demo/storyline.mjs`) and replace the segments. Keep each segment self-contained: it starts from
   `startPath`, resets its own data in `beforeSegment`, and never relies on another segment's state.
4. **Probe selectors read-only.** `node scripts/probe.mjs http://localhost:3000 / /reports` loads each page without
   clicking, saves a screenshot and lists headings, sections, buttons with their ARIA roles, inputs and links. Confirm
   every locator you plan to use exists. Headings with count badges, tabs exposed as `role=radio`, paginated lists and
   menus are the usual surprises. For deeper checks write your own script and import Playwright from
   `<skill>/scripts/node_modules/playwright/index.mjs` (it is installed there, not in your project).
5. **Record one segment.** `node scripts/record.mjs demo/storyline.mjs 01-dashboard --out demo/video`. Review its
   stills (demo-video-review skill) before going further: caption timing, callout placement, the opening slide, the join.
6. **Record everything.** `node scripts/record.mjs demo/storyline.mjs --all --out demo/video`. Long runs: keep the
   terminal output, it prints each segment's length and timings as it finishes.
7. **Fix only what broke.** Re-record a single segment by key; the runner restitches automatically, and also re-records
   the last segment when the storyline has a `closing` card (its numbers come from every segment). Encoding changes
   need no re-recording: `--reencode` rebuilds every segment from its saved frames.
8. **Restore the app.** Reset whatever the recording consumed so the live demo starts fresh.

## Commands

```sh
cd <skill>/scripts && npm install && npx playwright install chromium   # once
node <skill>/scripts/record.mjs <storyline.mjs>               # record missing segments, then stitch
node <skill>/scripts/record.mjs <storyline.mjs> 03-search      # (re)record named segments, restitch
node <skill>/scripts/record.mjs <storyline.mjs> --all          # re-record everything
node <skill>/scripts/record.mjs <storyline.mjs> --stitch       # stitch existing segments only
node <skill>/scripts/record.mjs <storyline.mjs> --reencode     # rebuild segments from saved frames, restitch
node <skill>/scripts/record.mjs <storyline.mjs> --list         # which segments are recorded
```

Options: `--out <dir>` (default `demo-video/` next to the storyline). Environment: `FFMPEG`, `DEMO_BASE_URL`,
`DEMO_HEADFUL=1`. Output: `<out>/<slug>.mp4`, `chapters.md`, `timings.json`, `segments/<key>/`.

## Writing good segments

```js
{
  key: "02-search", title: "Find anything", blurb: "One box searches customers, cases and knowledge.",
  tags: ["Search", "Knowledge"],
  async run(ctx) {
    await ctx.caption("Search", "Find anything in one box", "Customers, cases and policy, ranked.", 800);
    await ctx.type(ctx.app.getByPlaceholder(/Search/), "renewal policy");
    await ctx.app.getByPlaceholder(/Search/).press("Enter");
    await ctx.point(ctx.section("Results"), "Best match first", { hold: 4000 });
    await ctx.unpoint();
  },
}
```

- Set the caption **before** the navigation it describes (short `readMs`), so words and picture change together.
- Wait on work with `ctx.waitForResponse(/\/api\/jobs/)` (any method; `waitForPost` for POST only) inside
  `ctx.fast(...)`, then `ctx.waitVisible(result)` if the page shows placeholders first. Never sleep a guessed number of seconds.
- Move between pages by clicking the app's own links (`ctx.click`), not `ctx.go`: a full reload flashes a white window.
  After a client-side route change, wait with `ctx.waitForPath(/\/reports/)` or `ctx.waitVisible(...)`.
- Wrap anything worth quoting in `ctx.time(label, fn)` so the closing card can show real numbers.
- Prefer role and placeholder locators; use `ctx.section(title)` for panels and `ctx.button(/^Tab name/)` for tabs.
- Point at the smallest element that tells the story; the callout is clipped to the viewport either way.

## Checklist before you call it done

- [ ] Every segment probed read-only, then recorded without errors; `--list` shows all recorded.
- [ ] Stills reviewed: opening slides, each caption against its picture, callouts on target, joins, closing card.
- [ ] No caption claims something the video doesn't show; waits are badged; the closing card shows measured numbers.
- [ ] Simulated systems and synthetic data are labelled where the audience could mistake them for real.
- [ ] The app's data is reset afterwards; services you didn't start are still running.
- [ ] The MP4 plays from start to end with chapters (`ffprobe -show_chapters <file>`).
