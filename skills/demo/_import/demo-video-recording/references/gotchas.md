# Gotchas

Hard-won lessons from recording real demos, as **symptom → cause → fix**. Most of them cost a full re-record the first
time; read this before the first long run.

## Capture and encoding

**The last seconds of a segment are missing (closing card cut off).**
Cause: the Chrome screencast only emits a frame when the picture changes, so a static hold at the end has no frame.
Fix: end each clip at the moment recording stopped, not at the last captured frame (the engine does this).

**The video runs longer than the recording, or plays in jerks.**
Cause: bursts of frames with near-identical timestamps each padded to a minimum duration.
Fix: resample to a constant frame rate: for each output tick, show the newest frame captured at or before it.

**Text is soft or smeared.**
Cause: Playwright's built-in `recordVideo` encodes VP8 at a low fixed bitrate.
Fix: capture DevTools screencast frames (JPEG q95) and encode H.264 yourself (CRF ~17, `yuv420p`, `+faststart`).

**The time-lapse compressed the wrong part.**
Cause: speed marks and frame timestamps on different clocks.
Fix: record both as wall-clock seconds; wrap only the wait itself in `ctx.fast`, not the clicks around it.

## Clicking and locating

**Click times out: "<element> intercepts pointer events".**
Cause: a stage overlay (badge, card, callout) sits over the target, even while invisible (opacity 0 still receives
events). Fix: every overlay gets `pointer-events: none`; keep badges out of the app area (title bar), not over controls.

**The wrong record opened (asked for ITEM-01, got ITEM-01C).**
Cause: a substring or prefix match on a list that contains variants.
Fix: match exact keys with a boundary: `new RegExp(\`${key}(?![A-Z0-9])\`)`, or click by stable id.

**A heading can't be found by its exact text.**
Cause: the heading includes a count badge ("Needs attention 2"), so its accessible name differs.
Fix: match headings by role with an optional count: `/^Needs attention(\s*\d+)?$/` (that is what `ctx.section` does).

**Tabs or filters "don't exist".**
Cause: segmented controls are often `role=radio` or `role=tab`, not `button`.
Fix: select by tag and visible text (`ctx.button(/^Awaiting/)`), or check roles in a read-only probe first.

**An item isn't in the list.**
Cause: the list is paginated or virtualised ("Showing 24 of 99").
Fix: type into the page's own filter or search box first, then click.

**A menu crashes the page ("This page couldn't load").**
Cause: a real app bug only reached by clicking (for example a UI-library component used outside its required parent).
Fix: probe every interaction read-only before recording; fix the app, don't script around it.

## Scrolling and callouts

**The callout box runs off the window, or the section title is off-screen.**
Cause: the section is taller than the viewport and was centred.
Fix: scroll tall elements so their top sits under the sticky header, and clip callouts to the visible viewport.

**The first callout slides in from the top-left corner.**
Cause: position transitions animate from the default (0, 0).
Fix: on first show, set geometry with only opacity transitioning, then restore the transitions.

## Timing and state

**The caption describes the previous screen.**
Cause: the caption changed after the navigation plus its reading time.
Fix: caption first (short `readMs`), then navigate; hold on the new screen after.

**Buttons stay disabled, or the page shows stale results after background work.**
Cause: the app doesn't refresh when a worker finishes; the recording waited on UI text that never changes.
Fix: wait on the network (`ctx.waitForResponse` / `ctx.waitForPost`) and poll for the enabled state, reloading once or twice as a fallback.
Better: fix the app so it refreshes itself (users hit the same bug).

**The window flashes white between pages.**
Cause: `ctx.go(path)` reloads the app frame; the new page paints from blank.
Fix: navigate by clicking the app's own links or menu (`ctx.click`), which uses client-side routing. Keep `ctx.go`
for the first page of a segment (it runs behind the chapter slide).

**A probe or step reads the previous page after a click.**
Cause: client-side routing changes the URL without a page load, so "network idle" returns while the old page is
still on screen.
Fix: after the click, `await ctx.waitForPath(/\/articles\//)` or `await ctx.waitVisible(<element on the new page>)`.

**The response arrived but the screen still shows loading placeholders.**
Cause: the app fires more than one request, or renders after the response; waiting on the first response is not
enough (search pages often do this).
Fix: create `ctx.waitForResponse(re, { method: "GET" })` before the action, then `ctx.waitVisible(<first result>)`,
and time the whole thing with `ctx.time`.

**The closing card shows an old number after re-recording one segment.**
Cause: the closing card is baked into the last segment's frames when it is recorded.
Fix: the runner now re-records the last segment automatically whenever another segment is re-recorded (keep that
segment short); `--keep-closing` opts out. Check the end of the video after every partial re-record.

**A long silent stretch while the model or a job runs.**
Cause: a real wait with nothing on screen.
Fix: wrap it in `ctx.fast(label, factor, …)`: badge on screen, span compressed in post. Never cut it silently.

**A retake shows different data, or a step is already done.**
Cause: the previous take consumed the state (analysed, approved, validated).
Fix: reset exactly the records each segment uses in `beforeSegment`, keep fresh alternates, and make every segment
independent of the others.

**A late failure costs the whole run.**
Cause: one long monolithic recording.
Fix: record per segment; re-record only the one that failed. Test risky segments on their own first.

## Environment

**Fonts differ between machines or render as a fallback offline.**
Cause: the stage loads a web font from a CDN.
Fix: record with network access, or vendor the font files next to the stage and reference them locally. The
finished video is offline-safe either way: the fonts are baked into the frames.

**Local storage or cookies behave oddly inside the frame.**
Cause: a stage page on a different origin partitions the app's storage.
Fix: serve the stage from the app's own origin via request interception (the engine fulfils a reserved path on
`baseUrl`), so the iframe is same-origin.

**File uploads don't happen.**
Cause: a native file dialog can't be clicked in headless mode.
Fix: wait for the page's `filechooser` event while clicking the attach control, then `setFiles(path)`.

**`ctx.section("Requests")` highlights a sidebar link, or finds nothing.**
Cause: the same words appear outside the panel (navigation, breadcrumbs, tab labels).
Fix: `ctx.section` only matches inside a `<section>` and prefers the innermost section with that heading. If the app
doesn't use `<section>` elements, target the panel directly (`ctx.app.getByRole("region", { name })`, a test id, or a
locator scoped to `main`).

**A probe script can't import Playwright.**
Cause: Playwright is installed in the skill's `scripts/node_modules`, not in your project.
Fix: use `node <skill>/scripts/probe.mjs`, or import it by path: `import { chromium } from
"<skill>/scripts/node_modules/playwright/index.mjs"`.

**Shell loops mangle arguments (for example stills at timestamps).**
Cause: shells differ (zsh doesn't word-split variables; PowerShell quoting differs from bash).
Fix: drive ffmpeg and helpers from a Node or Python script, not shell loops, so the same steps run on every OS.

**Another project's server answers on the expected port.**
Cause: a port you assumed was free is in use; the recording shows the wrong app.
Fix: check the page title before recording; pick another port. Never stop or kill services you didn't start.
