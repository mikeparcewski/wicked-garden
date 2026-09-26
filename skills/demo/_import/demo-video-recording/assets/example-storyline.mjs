// Example storyline for the demo-video-recording skill (see references/storyline-api.md).
//
// A hypothetical app "Acme Console" at http://localhost:3000 with a dashboard, search, a long-running report job and an
// assistant chat. Copy this file next to your project, then replace the segments with your own chapters.
//
//   node <skill>/scripts/record.mjs demo/storyline.mjs --list
//   node <skill>/scripts/record.mjs demo/storyline.mjs 01-dashboard     # record one segment first, review its stills
//   node <skill>/scripts/record.mjs demo/storyline.mjs --all            # then everything
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
  brand: { name: "Acme Console", logo: "./brand/logo.svg", accent: "#e4002b" },
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
<p>Acme Console reads every request, checks it against your records and prepares the next step. People approve every change.</p>
<div class="meta"><b>Recorded live</b><b>Synthetic data</b></div>`, 6000);
      },
    },

    {
      key: "01-dashboard",
      title: "Start of the day",
      blurb: "The day starts ranked: what needs a decision, what's stuck, and what's new.",
      tags: ["Dashboard", "Next actions"],
      persona: "Sam Rivera",
      async run(ctx) {
        await ctx.caption("Start of the day", "The day starts ranked, not read",
          "Sam doesn't open two hundred emails. The console has already sorted <em>what needs a decision and what's stuck</em>.");
        // Point at a KPI row: find one label, then its grid container.
        await ctx.point(ctx.app.getByText("Needs a decision", { exact: true }).locator("xpath=ancestor::*[contains(@class,'grid')][1]"),
          "Live counts, one click to each list", { below: true, hold: 3800 });
        await ctx.unpoint();
        await ctx.point(ctx.section("Your next actions"), "Ranked by urgency", { hold: 4000 });
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
        await ctx.caption("Search", "Find anything in one box", "Customers, requests and policy, ranked together.", 900);
        const box = ctx.app.getByPlaceholder(/Search/);
        await ctx.type(box, "renewal policy for expired units");
        await box.press("Enter");
        await ctx.point(ctx.section("Best match"), "The policy section, not just the page", { hold: 4200 });
        await ctx.unpoint();
        await ctx.click(ctx.button(/^Knowledge\s*\d*/)); // a filter tab: role may be radio, so match by visible text
        await ctx.hold(2500);
      },
    },

    {
      key: "03-report",
      title: "A report in a minute",
      blurb: "A month-end report that used to take an afternoon, built while you watch, with every number traceable.",
      tags: ["Long-running job", "Traceable numbers"],
      resets: ["REPORT-SEPT"],
      async run(ctx) {
        await ctx.go("/reports/REPORT-SEPT");
        await ctx.caption("Reports", "Month-end, one click", "The job reads the ledger, reconciles it and drafts the summary.", 2600);
        // Register the wait before the click that triggers the POST, so a fast response can't be missed.
        const done = ctx.waitForPost(/\/api\/reports\/[^/]+\/build/);
        await ctx.click(ctx.app.getByRole("button", { name: "Build report" }), { after: 200 });
        // Real wait: badge on screen, span compressed 8x in post, real seconds measured for the closing card.
        await ctx.time("Build report", () => ctx.fast("Building the report", 8, () => done));
        await ctx.hold(1500);
        await ctx.caption("Result", "Every figure links to its source", "Open any number to see the ledger rows behind it.");
        await ctx.point(ctx.section("Summary"), "Drafted, with sources", { hold: 4500 });
        await ctx.unpoint();
      },
    },

    {
      key: "04-assistant",
      title: "Ask the assistant",
      blurb: "Plain-language answers about this record, with the sources they came from and suggested next questions.",
      tags: ["Assistant", "Cited sources", "Suggestions"],
      resets: ["REQ-1042"],
      async run(ctx) {
        await ctx.go("/requests/REQ-1042");
        await ctx.caption("Assistant", "Ask in plain language", "Suggested questions are tailored to the record.", 2400);
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
<li><b>01</b>A ranked day instead of an inbox</li>
<li><b>02</b>One search across records and policy</li>
<li><b>03</b>Month-end reports built in minutes</li>
<li><b>04</b>Answers with their sources</li>
</ol><div class="meta">${chips}</div>`;
  },
};
