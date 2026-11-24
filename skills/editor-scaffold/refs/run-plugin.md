# Third-party run plugins (`Kind: phase plugin.`, protocol 3)

A third-party **run plugin** ("phase plugin") renders ONE section in a job's **Details** panel from
the run's events on the topics the operator's install consent granted (DESIGN §2.b; CONTRACT-CS7).
It operates in the **observe tier only**: it asks only for `observe[]` topic patterns, never
`permissions[]`, never `doc.*`, and never `steer.*`.

## 1. Scaffold (`--kind run-plugin`)

```
wicked-garden run scripts/editor/scaffold.py --kind run-plugin --vendor <vendor> --id <vendor>-<name> --title "<plain words>" [--observe <topic[,topic]>] [--version 0.1.0] --out <dir>
```

Writes into `<dir>`:
- `wicked-pack.json` (spec 2) with one `plugins[]` entry (`protocol: [3]`, `inline: "run-thread"`,
  `observe[]`, `panels[]`, `samples: "samples/events.ndjson"`, and the pinned `sha256`);
- `plugins/<id>/index.html` — one self-contained HTML entry speaking protocol 3;
- `samples/events.ndjson` — sample `CoreEvent` rows carried by the conformance feed;
- `README.md`.

**Manual alternative:** copy `assets/run-plugin/` into `<dir>`, rename
`plugins/__PLUGIN_ID__` to `plugins/<id>`, replace `__PLUGIN_ID__`, `__PLUGIN_VERSION__`,
`__PLUGIN_TITLE__` and `__PLUGIN_TOPICS__`, and write `wicked-pack.json` with
one `plugins[]` entry and its `sha256`.

## 2. Manifest shape (`plugins[]` in `wicked-pack.json` spec 2)

A spec-2 pack may declare `plugins[]` (with or without `editors[]`). Editor and plugin `id`s share
one namespace across the pack (`wicked` and `wicked-*` are reserved and refused). A `permissions`
key on a plugin entry is refused.

| Field | Rule |
|---|---|
| `id` | required; `^(?!wicked($\|-))[a-z0-9]+(-[a-z0-9]+)*$`, max 64, unique across `editors[]` and `plugins[]` |
| `title` | required; 1–40 chars, has a non-space, no `<`, `>`, CR or LF |
| `version` | required; anchored SemVer (`0.1.0`) |
| `protocol` | required; integer array containing `3` (`[3]`) |
| `inline` | required; `"run-thread"` |
| `entry` | required; relative `.html` path inside the pack (<= 5 MiB or `limits.bundleBytes`, all resources embedded) |
| `sha256` | required; 64 lowercase hex sha256 of the entry file |
| `description` | optional; at most 160 chars |
| `observe` | required; 1–16 items `{topic, why}` (both required, `why` non-empty and <= 200 chars, topics unique) |
| `panels` | required; 1–4 items `{slot: "run.details", id, title, instances?, order, defaultOpen?, summary?}` |
| `visuals` | optional; `{color?: "#rrggbb", icon?: relative .svg inside the pack <= 32 KiB}` |
| `samples` | optional; relative `.ndjson` path inside the pack (<= 256 KiB, one `CoreEvent` JSON object per line) |
| `limits` | optional; `{bundleBytes}` (1..5242880) |

### Panel fields (`panels[]`)

- `slot`: const `"run.details"`
- `id`: `^[a-z][a-z0-9-]{0,31}$`, unique across `panels[]`
- `title`: 1–40 chars, no `<>`/CR/LF, may contain `{phase}`
- `instances`: `"single"` | `"per-phase"` (optional)
- `order`: integer `1`–`99` (required)
- `defaultOpen`: `"always"` | `"never"` | `"current"` | `"while-live"` (optional)
- `summary`: `"plugin"` | `"none"` (optional; when `"plugin"`, the frame may send `panel.summary`)

## 3. Observe topics and install consent

Every `observe[].topic` must match the run topic pattern grammar (§C2):
- at most 120 chars, dot-separated;
- starts with `wicked.run.` (first segment `wicked`, second `run`, at least one segment after `run`);
- every segment after `wicked` matches `^[a-z][a-z0-9_-]{0,40}$` or `*`, or `**` as the **last** segment only.

Valid examples: `wicked.run.session.*`, `wicked.run.unit.*`, `wicked.run.usage.reported`, `wicked.run.**`.
Invalid examples: `wicked.**`, `wicked.bus.x`, `wicked.run`, `Wicked.run.x`, `wicked.run.**.x`.

**Why the consent lists them:** run-plugin topic grants are ledger-only (`EDITOR-GRANTS`), keyed per
build as `plugin:<id>@<version>#<sha256>/observe:<topic>`. No policy allow/posture rule can grant a
plugin topic; the operator's install consent is the only way in, and a new version or changed entry
hash asks again. `install.py --plan` outputs `plugins: [{id, version, observe: [{topic, why}]}]` and
the `EDITOR-GRANTS` writes so the consent gate shows each topic and its reason.

## 4. Protocol 3 (`wicked.editor/3`)

1. **Handshake**: post ONE `plugin.ready` `{editor: PLUGIN, version: VERSION, protocol: [3], surfaces: {card: {interactive: false, aspect: "auto", actions: []}}}` to
   `parent` on startup. Wait for the first `host.hello` carrying a transferred `MessagePort`
   (`e.ports[0]`). `host.hello.payload` carries `protocol: 3` and
   `observe: {runId: string, topics: string[], scope?: {phase: string, label: string, ords: number[]}, panel?: {slot: 'run.details', id: string}}`.
   Read `observe.topics` for the granted patterns. The rows are the run's; a scoped panel filters them itself.
2. **`events.batch`**: the host delivers filtered run events on the port as
   `{p: 'wicked.editor', v: 1, type: 'events.batch', payload: {runId: string, replay: boolean, gap?: 'history-unavailable', rows: Array<{id: string, topic: string, runId: string, seq: number | null, at: number, ord: number | null, data: object}>}}`.
   - Deduplicate within a mount by `row.id`. Recorded rows use `s<seq>` and live rows use `l<n>`;
     after remount, an earlier live event replays with its recorded `s<seq>` id.
   - Render every field as **plain text** (`textContent` / DOM nodes) — **never** `innerHTML` or
     live markup.
3. **`panel.summary`**: when a panel sets `summary: "plugin"`, post
   `{p: 'wicked.editor', v: 1, type: 'panel.summary', payload: {text: "<short text>", tone?: "none" | "run" | "wait" | "ok" | "fail"}}`
   on the port to update the section header badge.
4. **`ui.height`**: the section is as tall as the plugin says (its card is `aspect: "auto"`). After every render,
   post `{p: 'wicked.editor', v: 1, type: 'ui.height', payload: {px: <content height>}}` on the port; without it the
   host keeps the frame at its minimum and the rows are cut off. Report right after `host.hello` too, and do not
   remember a height measured before it (a ResizeObserver fires before hello, when there is no port to send on).
5. **Liveness & resilience**: answer `host.ping` with `{p: 'wicked.editor', v: 1, re: d.id, ok: true, payload: {}}`;
   apply `host.theme` safely (reject `url(`, `;`, `{`, `}`); ignore unknown message types and
   malformed payloads without throwing; load nothing from outside the HTML file.

## 5. Conformance (`RUN_PLUGIN_CASES`: `r0`–`r5`)

`conformance.py` serves the pack's `samples` plus one `CoreEvent` of every `RUN_TOPICS` type on its
own origin and drives studio's `/editors/conformance?plugin=<id>&version=<v>&sha=<sha256>&observe=<granted>&samples=<path>`
(`window.__wickedRunPlugin`):

| Case | Passes when |
|---|---|
| `r0-manifest` | `pack check` passes for the pack |
| `r1-handshake` | `plugin.ready` once within 3 s; the host negotiated protocol `3` |
| `r2-no-network` | 0 requests from the frame beyond its own entry |
| `r3-topics` | the harness withholds the last independently testable pattern that leaves granted catalog coverage (otherwise grants all); every delivered row matches a granted pattern, >= 1 row arrived, and the current frame is alive |
| `r4-replay` | after live events, `remount()`; the new mount's replay delivers every granted event emitted so far once by id with no `gap`, and remaining live events arrive once each with no duplicate |
| `r5-hash-pinned` | a wrong pinned sha256 never starts the plugin (no handshake) |

The JSON report carries a top-level `plugins` array (`{id, version, protocol, sha256, ok, cases, gaps}`),
and `ok` at the top is `true` only when every editor and plugin in the pack passed.

Samples use actual CoreEvent types such as `sessionStarted`, `unitExecuting`, `unitDone`, and `cliUsage`,
with a non-empty `session`, a numeric `seq`, and a finite numeric epoch-ms `ts`. For example:

```json
{"type":"cliUsage","session":"conformance-run","seq":1,"ts":1767225601000,"ord":1,"attempt":1,"costUsd":0.02,"inputTokens":1200,"outputTokens":340}
```

The host maps these fields into `row.data` (for usage: `attempt`, `costUsd`, `inputTokens`, `outputTokens`).
The harness normalizes the run and sequence, supplies every type from studio's `RUN_TOPICS` in both feed
halves, and derives mount-2 replay and live expectations from those samples and its emission counts.
Overlapping declarations still authorize a row when any granted pattern covers its topic.
