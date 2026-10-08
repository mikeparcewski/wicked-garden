# Walkthrough author: the `walkthrough_plan` contract

A governed run whose plan holds `walkthrough_plan` + `walkthrough_review` proves the builder's work by
recording it. The `walkthrough_plan` seat (an evaluator: it writes the checks for someone else's work)
writes the storyline; the engine-run record tool films it against a fixture started from the tree under
review and judges every check through the vault. No model judges a check.

## Where the storyline goes

- Exactly one file: `<evidence root>/author/<your step id>/storyline.mjs`. The step prompt names the full
  path. The author dir is your only write root; the worktree is not yours to write.
- The step's pinned validator runs
  `wicked-garden run scripts/demo/walkthrough.mjs lint --root <author dir>`. It denies the step until the
  lint exits 0.
- The record step reads the same file through `WICKED_WALKTHROUGH_AUTHOR` (the author dir the engine hands
  it). Outside a run, pass `--storyline <path>` to `record` and `lint`.

## Lint rules

`lint` prints `{ok, storyline, chapters, checks, findings: [{rule, where, detail}]}` and exits 0 with no
finding, 1 with any, 2 on a usage error. Each rule id below is what a finding carries.

| Rule | What it requires |
|---|---|
| `storyline_missing` / `storyline_unloadable` | `<author dir>/storyline.mjs` exists and imports, default export an object |
| `base_url` | `baseUrl: "fixture"` — the tool films the fixture it starts, never a live system |
| `fixture_start` | `fixture.start` is an argv of strings; no inline code (`-e`, `-c`, `--eval`, `-p`, `--print`, `--command`); no absolute path or `..`; with `--tree <dir>`, every script-like argument exists in the tree |
| `secret_env` | no `fixture.env` name looks like a credential (`TOKEN`, `SECRET`, `PASSWORD`, `API_KEY`, `PRIVATE_KEY`, `CREDENTIAL`, `AUTH`, ...) |
| `segments` | at least one chapter (a non-`intro` segment): an empty plan proves nothing |
| `segment_key` / `segment_run` | keys match `^[a-z0-9][a-z0-9-]*$` and are unique; `run(ctx)` is a function |
| `proves` | every chapter names plan step ids in `proves[]`; with `--steps a,b`, each id is one of them |
| `check_id` / `check_kind` | ids are plain and unique per chapter; `kind` is a collector: `locator`, `probe`, `artifact`, `guard`, `join` |
| `check_selector` / `check_probe` / `check_artifact` / `check_join` | a locator has a `selector`; a probe's `name` is a key of `fixture.probes`; an artifact `path` stays under `DATA_DIR`; a join names two or more earlier checks of its chapter in `sources` |
| `chapter_on_screen` / `chapter_state` / `chapter_cross_check` | each chapter has a `locator` (on_screen), a `probe` or `artifact` (saved state, events, side effects, output) and a `join` whose sources include one of each |
| `must_not_happen` | the walkthrough has at least one `guard` check (no foreign writes, no console errors) |
| `check_verify` | `verify`, when given, is `{kind: "jq_pred", params: {expr}}` and `jq` accepts the expression |
| `negative_missing` / `negative_passes` / `negative_unverified` | every check carries `negative: [...]`, capture-shaped samples its verifier must FAIL on; a verifier that passes a sample is a tautology. Without `jq` the lint fails closed |

A check without `verify` uses the record tool's default: locator `.inner_text != null`, probe
`.raw.exit_code == 0`, artifact `.sha256 != null`, guard no foreign writes and no console errors, join every
source non-null. The verifier reads the capture the tool records: a locator `{inner_text, frame}`, a probe
`{raw: {argv, exit_code, stdout, stderr}, parsed}`, an artifact `{path, sha256}`, a guard
`{foreign_writes, console_errors}`, a join `{joined: {<source id>: value}}`.

## A storyline that passes

```js
export default {
  title: "Orders",
  baseUrl: "fixture",
  fixture: {
    start: ["node", "scripts/fixture-server.mjs"],      // a script the tree declares
    ready: "/ready",
    probes: { orders: ["sqlite3", "-json", "data/app.db", "select status, amount from orders"] },
  },
  segments: [
    {
      key: "01-pay", title: "Paying an order", proves: ["build"],
      checks: [
        { id: "paid_badge", kind: "locator", selector: "#order-1 .status",
          verify: { kind: "jq_pred", params: { expr: ".inner_text == \"Paid\"" } },
          negative: [{ inner_text: "Pending" }] },
        { id: "paid_row", kind: "probe", name: "orders", parse: "sqlite-json",
          verify: { kind: "jq_pred", params: { expr: "[.parsed[] | select(.status == \"paid\")] | length == 1" } },
          negative: [{ parsed: [{ status: "paid" }, { status: "paid" }] }] },
        { id: "screen_matches_db", kind: "join", sources: ["paid_badge", "paid_row"],
          negative: [{ joined: { paid_badge: "Paid", paid_row: null } }] },
        { id: "nothing_else", kind: "guard",
          negative: [{ foreign_writes: ["POST https://api.example.com/charge"], console_errors: [] }] },
      ],
      async run(ctx) {
        await ctx.click(ctx.app.getByRole("button", { name: "Pay" }));
        await ctx.check("paid_badge");
        await ctx.check("paid_row");
        await ctx.check("screen_matches_db");
        await ctx.check("nothing_else");
      },
    },
  ],
};
```

Every check id must be reached by a `ctx.check(id)` in `run`: a check never reached is a FAIL at record time.
