// Example storyline for the wicked-garden-demo skill (see refs/storyline-api.md).
//
// A hypothetical app "Acme Console" at http://localhost:3000 with a dashboard, search, a long-running report job and an
// assistant chat. Copy this file next to your project, then replace the segments with your own chapters.
//
//   wicked-garden run scripts/demo/record.mjs demo/storyline.mjs --list
//   wicked-garden run scripts/demo/record.mjs demo/storyline.mjs 01-dashboard     # record one segment first, review its stills
//   wicked-garden run scripts/demo/record.mjs demo/storyline.mjs --all            # then everything
//
// The recorder is READ-ONLY by default: every non-GET request and every WebSocket frame the page sends is blocked and
// fails the segment `side_effect_blocked`. Chapters 01-02 only read. Chapters 03-04 press buttons that POST (a report
// build, a chat message), so they record only against a disposable copy of the app you started on a loopback port,
// named with --fixture-origin (e.g. --fixture-origin http://127.0.0.1:4310): writes to that origin pass, any other is
// blocked. Against a live system, show such a control without pressing it (point at it, caption what it does).
import { spawnSync } from "node:child_process";

/** Resets the demo records a segment uses, via the app's own admin CLI (placeholder). Cross-platform: no shell tricks. */
function resetRecords(keys) {
  if (!keys?.length) return;
  // Replace with your project's reset command, e.g. ["python", "manage.py", "demo_reset", ...] or ["npm", "run", "demo:reset", "--", ...].
  const cmd = ["acme-admin", "demo", "reset", ...keys.flatMap((k) => ["--record", k])];
  const r = spawnSync(cmd[0], cmd.slice(1), { encoding: "utf8", shell: process.platform === "win32" });
  if (r.error || r.status !== 0) throw new Error(`reset failed for ${keys.join(", ")}: ${r.error?.message ?? r.stderr}`);
}

export default {
  title: "Acme Console demo",
  baseUrl: "http://localhost:3000",
  brand: { name: "Acme Console", accent: "#e4002b" }, // optional: logo: "./brand/logo.svg" (path relative to this file)
  startPath: "/",

  // Runs behind each segment's opening slide: reset what the segment uses and pick the persona it is told from.
  async beforeSegment(ctx, seg) {
    resetRecords(seg.resets);
    if (seg.persona) {
      await ctx.click(ctx.app.getByRole("button", { name: /Signed in as/ }));
      await ctx.click(ctx.app.getByRole("menuitem", { name: seg.persona }));
    }
  },

  segments: [
    {
      key: "00-intro",
      intro: true,
      async run(ctx) {
        await ctx.card(`<div data-logo></div><h1>From request<br>to <span>resolution</span>.</h1>
<p>Every request gets checked against your records, with the next step ready for you. You still approve every change.</p>
<div class="meta"><b>Recorded live</b><b>Synthetic data</b></div>`, 6000);
      },
    },

    {
      key: "01-dashboard",
      title: "Start of the day",
      blurb: "Sam's morning starts with what needs a decision, what's stuck and what's new.",
      tags: ["Dashboard", "Next actions"],
      persona: "Sam Rivera",
      async run(ctx) {
        await ctx.caption("Start of the day", "Here's what needs Sam first",
          "Before he opens a single email, he can see <em>what needs a decision and what's stuck</em>. It's already sorted.");
        // Point at a KPI row: find one label, then its grid container.
        await ctx.point(ctx.app.getByText("Needs a decision", { exact: true }).locator("xpath=ancestor::*[contains(@class,'grid')][1]"),
          "Click a count to open that list", { below: true, hold: 3800 });
        await ctx.unpoint();
        await ctx.point(ctx.section("Your next actions"), "Most urgent at the top", { hold: 4000 });
        await ctx.unpoint();
      },
    },

    {
      key: "02-search",
      title: "Find anything",
      blurb: "One box searches customers, requests and the knowledge base, and brings back the right section.",
      tags: ["Search", "Knowledge"],
      async run(ctx) {
        // Caption first, short read time: the words change as the new screen arrives.
        await ctx.caption("Search", "Let's look something up", "You don't need to know where it lives. One box covers customers, requests and policy.", 900);
        const box = ctx.app.getByPlaceholder(/Search/);
        await ctx.type(box, "renewal policy for expired units");
        await box.press("Enter");
        await ctx.point(ctx.section("Best match"), "Here's the exact section you need", { hold: 4200 });
        await ctx.unpoint();
        await ctx.click(ctx.button(/^Knowledge\s*\d*/)); // a filter tab: role may be radio, so match by visible text
        await ctx.hold(2500);
      },
    },

    {
      key: "03-report",
      title: "Build the month-end report",
      blurb: "We build the month-end report while you watch, and you can trace every number back to the ledger.",
      tags: ["Long-running job", "Traceable numbers"],
      resets: ["REPORT-SEPT"],
      async run(ctx) {
        await ctx.go("/reports/REPORT-SEPT");
        await ctx.caption("Reports", "Now let's build the month-end report",
          "It has to match the ledger, so the draft you get is already checked against it.", 2600);
        // Writes: needs --fixture-origin naming a disposable app you started (see the header).
        // Register the wait before the click that triggers the POST, so a fast response can't be missed.
        const done = ctx.waitForPost(/\/api\/reports\/[^/]+\/build/);
        await ctx.click(ctx.app.getByRole("button", { name: "Build report" }), { after: 200 });
        // Real wait: badge on screen, span compressed 8x in post, real seconds measured for the closing card.
        await ctx.time("Build report", () => ctx.fast("Building the report", 8, () => done));
        await ctx.hold(1500);
        await ctx.caption("Result", "You can check every number", "Click any figure and you'll see the ledger rows it came from.");
        await ctx.point(ctx.section("Summary"), "Each figure shows where it came from", { hold: 4500 });
        await ctx.unpoint();
      },
    },

    {
      key: "04-assistant",
      title: "Ask the assistant",
      blurb: "Ask about this request in plain words, and see where each part of the answer came from.",
      tags: ["Assistant", "Cited sources", "Suggestions"],
      resets: ["REQ-1042"],
      async run(ctx) {
        await ctx.go("/requests/REQ-1042");
        await ctx.caption("Assistant", "Just ask it", "Ask about this request the way you'd ask a colleague.", 2400);
        // Writes: needs --fixture-origin naming a disposable app you started (see the header).
        const answered = ctx.waitForPost(/\/chat$/);
        const starter = ctx.button(/^What is blocking this/);
        if (await starter.count()) {
          await ctx.click(starter.first(), { after: 200 });
        } else {
          const ask = ctx.app.getByPlaceholder(/^Ask /);
          await ctx.type(ask, "What is blocking this request?");
          await ask.press("Enter");
        }
        await ctx.time("Assistant answer", () => ctx.fast("The assistant is answering", 4, () => answered));
        await ctx.hold(5000);
      },
    },
  ],

  // Closing card from measured timings only ({ segmentKey: { label: seconds } }).
  closing(allTimings) {
    const t = Object.assign({}, ...Object.values(allTimings));
    const chips = [
      t["Build report"] && `<b>Report built in ${Math.round(t["Build report"])} s (measured)</b>`,
      t["Assistant answer"] && `<b>Assistant answered in ${Math.round(t["Assistant answer"])} s</b>`,
    ].filter(Boolean).join("");
    return `<div data-logo></div><h1>How Acme Console <span>saves the day</span></h1>
<ol>
<li><b>01</b>You see what needs you first</li>
<li><b>02</b>You search records and policy from one box</li>
<li><b>03</b>You can trace every number in the report</li>
<li><b>04</b>Answers show where they came from</li>
</ol><div class="meta">${chips}</div>`;
  },
};
