---
name: wicked-garden-mcp
description: |
  Use an MCP tool from a governed wicked-crew unit, on any seat: list the
  tools your unit may try, then call one through the wicked-crew broker, which
  holds the server connections and secrets, judges every call by steering
  policy and records it. One command on every CLI; no MCP configuration.

  Use when: a task needs an external tool the operator registered in studio
  MCP tools ("look up the Jira issue", "query Sentry", "call the <server>
  tool"), "what MCP tools can I use", or a phase directive names an
  `mcp:<server>/<tool>` subject. NOT for building an MCP server (use
  wicked-garden-mcp-scaffold) or for the estate code graph and memory (use
  wicked-garden-search and wicked-garden-mem).
metadata:
  role: router
  phases: "*"
  archetypes: "build,review,incident,explore"
---

# MCP tools through the broker

A governed unit reaches MCP tools in exactly one way: this shim, which sends your unit's
capability token and the request to the wicked-crew broker. The broker holds every
server connection and every secret, judges the call against the steering policies for
your unit (phase role, seat, run mode), runs it, scrubs the result and records the call.
You never see a secret, and you never configure an MCP server.

## Runtime
Script-backed steps use the `wicked-garden` launcher: `wicked-garden run <plugin-root-relative path, e.g. scripts/…> [args]`. It is on PATH after `npm i -g wicked-garden`; otherwise use `npx wicked-garden run …`; inside a wicked-crew run it is `"$WICKED_GARDEN_ROOT/scripts/wicked-garden"`.
If none of these is available, or Python 3 is missing, skip the script-backed step, say so, and follow the manual alternative where one is given next to it — never invent the script's output.
Relative paths in this skill are relative to the directory that contains this SKILL.md.

## 1. List what your unit may try

```
wicked-garden run scripts/mcp/shim.py list
```

It prints one JSON object: `unit` (run, phase, seat) and `tools`. Each tool has its
`subject` (`mcp:<server>/<tool>`), its `class` (`read`, `write` or `destructive`), its
`description`, its `inputSchema` and a `decision`:

- `allow`: a call runs now.
- `ask`: a call waits for the operator's approval (a server's first use, a new schema,
  or a write the run's mode gates). Calling it records the request for the operator; it
  does not run.

A tool your unit may never call is not listed: an evaluator or recon unit sees no write
or destructive tool, and a tool a policy denies is left out. An empty list means there is
nothing for this unit; continue without MCP tools.

## 2. Call one tool

```
wicked-garden run scripts/mcp/shim.py call mcp:<server>/<tool> --args '{"key": "value"}'
```

- Build the arguments from the tool's `inputSchema`. Put them in a file and pass
  `--args-file <path>` (or `--args-file -` for stdin) when quoting is awkward.
- The `mcp:` prefix may be omitted (`<server>/<tool>`).
- It prints one JSON object, the broker's answer, with an `outcome`. On `ok` the tool's
  result is in `result`. The result can itself be a tool error (`result.isError`): read it
  and fix your arguments, do not assume success.

## 3. Read the answer by its exit code

| Exit | Outcome | What to do |
|---|---|---|
| `0` | `ok` | Use `result`. Cite the call (`subject`, `callId`) where you rely on it. |
| `3` | `denied` or `withheld` | Blocked by policy (`ruleIds`, `reason`, `remedy`). Final: do not retry it with other arguments or another route. Continue without it and say so in your output. |
| `4` | `pending_approval` | The operator has not approved it yet. Do not retry in a loop. Do other work, and name the subject in your output so the operator can approve it. |
| `5` | `budget_exhausted`, `breaker_open`, `upstream_error` | The tool is unavailable for now. A write may or may not have applied after `upstream_error`: check before repeating it. |
| `2` | `no_mcp_channel`, `bad_request` | Not a governed unit (no `WICKED_MCP_TOKEN` or `WICKED_CREW_URL`), or bad arguments. Fix the arguments; without a channel, continue without MCP tools. |
| `1` | anything else | An invalid token, a guard error or an unreachable broker. Report it; do not work around it. |

A denied call never fails your unit; only you can make it look like it succeeded, so
report it honestly.

## Rules

- **Only through the broker.** Never add an MCP server to a CLI's configuration, never
  start an MCP server yourself, and never call an upstream API directly to get around a
  refusal. A native MCP tool your CLI happens to offer is judged the same way and an
  unregistered one is denied.
- **The token is a credential.** Never print `WICKED_MCP_TOKEN`, put it on a command line,
  or paste it into output, a file or a commit. The shim never prints it.
- **Evaluators read, creators write.** In a review, verify or recon unit only read tools
  are offered and a write is denied by the engine, whatever the run mode.
- **Say what you called.** List each MCP call you relied on (subject, outcome, `callId`)
  in your output; the evaluator and the run's Governance panel read the same record.

**Manual alternative** (no launcher or no Python): send the same request with `curl`,
passing the body on stdin so the token never appears on a command line:

```
curl -s -X POST "$WICKED_CREW_URL/api/v1/mcp/tools" -H 'Content-Type: application/json' --data-binary @- <<BODY
{"token": "$WICKED_MCP_TOKEN"}
BODY
curl -s -X POST "$WICKED_CREW_URL/api/v1/mcp/call" -H 'Content-Type: application/json' --data-binary @- <<BODY
{"token": "$WICKED_MCP_TOKEN", "subject": "mcp:<server>/<tool>", "args": {}}
BODY
```

The answers are the JSON objects described above; the HTTP status stands in for the exit
code (200 ok, 403 denied or withheld, 409 pending approval, 429, 502, 503 or 504
unavailable, 401 invalid token).
