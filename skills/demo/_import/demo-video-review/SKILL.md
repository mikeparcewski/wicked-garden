---
name: demo-video-review
description: Reviews a recorded product demo or screen-recording video before it is shared. Builds labelled contact sheets of stills (at chosen timestamps, evenly spaced, one per MP4 chapter, around chapter joins, and at the very end), then checks caption-to-picture sync, callout placement, dead air versus time-lapse badges, chapter joins and transition slides, the closing card, address-bar tidiness, data or persona leaking between segments, and on-screen numbers against measured timings. Ends with a verdict per issue - re-encode, re-record one segment, or fix the app. Use when asked to review, QA, check or proof a demo video, walkthrough video, screen recording or stitched chapter video, or after recording with the demo-video-recording skill.
license: MIT
compatibility: Python 3.9+ and ffmpeg/ffprobe on PATH (or FFMPEG=/path/to/ffmpeg). Pillow is optional (labels tiles when ffmpeg lacks drawtext).
metadata:
  version: "1.0"
---

# Demo video review

A recorded demo is judged by what a viewer sees, so review it by **looking at stills**, not by reading the recording
script. Watching a 14-minute video end to end misses things; a few targeted contact sheets catch almost every defect
in minutes and give you exact timestamps to report.

## Tool

`scripts/contact_sheet.py` tiles one still per moment into a single labelled PNG (timestamp and chapter title under
each tile). On Windows run it with `python` if `python3` is not on PATH.

```sh
python3 scripts/contact_sheet.py demo.mp4 --chapters               # ~2 s into every chapter: the chapter slides
python3 scripts/contact_sheet.py demo.mp4 --chapters --offset 8    # ~8 s in: the first content of each chapter
python3 scripts/contact_sheet.py demo.mp4 --joins                  # just before + just after every chapter boundary
python3 scripts/contact_sheet.py demo.mp4 --end                    # last seconds: closing card present and held?
python3 scripts/contact_sheet.py demo.mp4 --every 20 --cols 4      # evenly spaced survey
python3 scripts/contact_sheet.py demo.mp4 --at 1:02,1:05,1:08      # zoom in on a moment
python3 scripts/contact_sheet.py segments/05/segment.mp4 --every 8 # one segment on its own
```

Options: `--offset` (seconds into each chapter, default 2), `--join-gap` (default 0.6), `--end-span` (default 6),
`--cols`, `--width` (tile px), `--out` (default: a PNG next to the video; pass `--out` to keep sheets together). Open the PNG it prints (any image viewer, or have your agent read the image).
Also check format quickly: `ffprobe -v error -show_entries format=duration:stream=codec_name,width,height,r_frame_rate -show_chapters demo.mp4`.

## Review passes (in this order)

1. **Structure** (`--chapters`, `ffprobe -show_chapters`): every chapter present, in order, titled and numbered
   ("Chapter N of M" matches the real count), intro first, duration plausible, 1920x1080 H.264 at a constant frame rate.
2. **Joins** (`--joins`): each boundary goes plain background → next chapter slide (the intro instead ends on its
   title card, so intro → chapter 1 is a card-to-card cut, which is expected). No half-faded app frame, no
   flash of setup (persona switching, login, a menu opening) before the slide covers it.
3. **The end** (`--end`): the closing card is present and **held** for its full duration. A capture that only emits
   frames on screen change can silently drop a static final hold; if the last seconds are missing, it is a
   post-processing bug, fix it and re-encode.
4. **Survey** (`--every 20`, then `--at` around anything odd): for each still ask the checklist questions below.
5. **Numbers**: every number the video claims (timings on the closing card, counts in captions) matches the recording's
   measured timings file and what the app shows on screen. Estimates must never appear as measurements.

## What to look for in each still

- **Caption sync**: does the caption describe *this* picture? A caption left over from the previous step while a new
  page is on screen means the caption was set after the navigation (move it before, with a short read time).
- **Callouts**: the box surrounds the element named in its label, fits inside the app window, and its label is
  readable (not clipped at the top, not covering the thing it points at).
- **Cursor**: visible where a click happens; hidden on title and closing cards.
- **Waits**: long waits show a time-lapse badge with the factor and real elapsed time. Frozen pictures with no badge
  are dead air; progress spinners at 1× are wasted time.
- **State and persona**: the header shows the right user for the chapter; data from another chapter (approvals,
  created records, filters, open menus, a toast) does not leak in; case IDs and names in captions match the screen.
- **Chrome**: the window's address bar is tidy (path only, one line); no dev-mode badges, cookie banners, scrollbar
  junk, or error pages ("This page couldn't load" means an app bug, not a recording bug).
- **Legibility**: text is sharp at 100%, captions fit on two lines, nothing important is under the caption band.

Full checklist with causes and fixes: [references/checklist.md](references/checklist.md).

## Verdicts

Classify every finding before fixing anything, because the fix cost differs by orders of magnitude:

| Verdict | When | Fix |
|---|---|---|
| **Re-encode** | Timing, trimming, speed-up, frame rate, chapter metadata, missing end hold, stitch order | Rebuild from the saved raw capture; no re-recording (e.g. `record.mjs <storyline> --reencode`). |
| **Re-record one segment** | Wrong caption text or timing, callout target, a flaky click, stale data, a wrong persona, a long unannotated wait | Fix the storyline for that segment, reset its data, record only it, restitch. |
| **Fix the app** | Errors, crashes, stale UI that never refreshes, wrong numbers, confusing copy, cluttered panels | Fix and rebuild the app, then re-record the segments that show it. Report these to the product owner too: a demo is often the first real test of a flow. |

Report findings as a short table: `timestamp · chapter · what's wrong · verdict`. Re-review only the changed segments
plus the joins on either side, then run `--end` again on the final file.
