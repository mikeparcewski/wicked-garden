---
name: wicked-garden-mcp-scaffold
description: |
  Build a new MCP server that wicked-crew's broker can register and govern:
  scaffold a zero-dependency stdio server (Node or Python template), add
  tools with honest annotations, keep secrets in the environment the broker
  injects, then probe it — initialize + tools/list, with each tool's class
  (read / write / destructive) derived exactly as the broker derives it.

  Use when: "build an MCP server", "scaffold an MCP server", "wrap this
  service as MCP tools", "new MCP tool server", "check my MCP server
  answers", "probe an MCP server", or the studio MCP tools "Build a server"
  run. NOT for registering or approving a server (studio MCP tools does
  that) or for wrapping a plain REST API (studio MCP tools, Wrap an API).
metadata:
  role: router
  phases: "*"
  archetypes: "build"
---

# MCP scaffold

Scaffold → add tools → probe → hand over for registration. The server you build is an
**upstream** of the wicked-crew broker: the broker holds its connection and its secrets,
judges every call through steering policy, and records every call. Your server only has
to speak MCP over stdio and describe its tools honestly.

## Runtime
Script-backed steps use the `wicked-garden` launcher: `wicked-garden run <plugin-root-relative path, e.g. scripts/…> [args]`. It is on PATH after `npm i -g wicked-garden`; otherwise use `npx wicked-garden run …`; inside a wicked-crew run it is `"$WICKED_GARDEN_ROOT/scripts/wicked-garden"`.
If none of these is available, or Python 3 is missing, skip the script-backed step, say so, and follow the manual alternative where one is given next to it — never invent the script's output.
Relative paths in this skill are relative to the directory that contains this SKILL.md.

## 1. Scaffold

Pick the language the service's client library lives in; both templates have no
dependencies and behave identically.

```
wicked-garden run scripts/mcp/scaffold.py --name <server-name> --lang node|python --out <dir>
```

- `--name` becomes the registry key and the `mcp:<server>/<tool>` subject segment:
  lowercase letters, digits and `-`, starting with a letter, at most 64 characters.
- It writes `<dir>/server.mjs` or `<dir>/server.py`, **never overwrites** an existing file,
  and prints JSON with the run command and the probe command.
- **Manual alternative:** copy `assets/node/server.mjs` or `assets/python/server.py` into
  `<dir>` and replace every `__SERVER_NAME__` with the server name.

The template answers `initialize` (negotiating the protocol version), `ping`, `tools/list`
and `tools/call`, ignores notifications, and ships two example tools: `echo` (read) and
`counter_increment` (write). Replace them with your own.

## 2. Add tools: the rules the broker relies on

Each tool is one entry in the `TOOLS` table: `description`, `inputSchema` (JSON Schema,
`type: object`), `annotations` and a `handler`. A handler returns text; a bad call raises
`ToolError`, which comes back as `isError` so the caller's turn continues.

**The broker derives each tool's class from its annotations** (an operator override in the
registry wins), and the class decides its posture:

| Annotations | Class |
|---|---|
| `readOnlyHint: true` | read |
| an `annotations` object with `readOnlyHint` false or absent and `destructiveHint` true or absent | destructive |
| an `annotations` object with `readOnlyHint: false` and `destructiveHint: false` | write |
| no `annotations` object at all | **write** |

- Set `readOnlyHint: true` only when the tool changes nothing anywhere: no files, no
  remote state, no sent messages. The operator sees these annotations in the preview and
  can override a class; a false read claim is found at review, not hidden by it.
- Set `destructiveHint: false` only when the tool cannot delete or overwrite anything.
- Set `idempotentHint: true` only when repeating a call is harmless, and
  `openWorldHint: true` when the tool reaches a system outside the server.
- Tool names: letters, digits, `_` and `-`. No `/` (it splits the subject) and no `__`.
- Keep schemas stable. **A changed tool schema puts that tool back to unregistered** until
  the operator previews and approves it again; a renamed tool is a new tool.

**Secrets.** Read a credential from an environment variable (for example
`ACME_API_TOKEN`). At registration the operator stores the value in the broker, which injects
it into the server's environment at call time and nowhere else. Never log a secret, never
return it in a result, never accept it as a tool argument, and never write it into the repo
or a config file.

**stdout carries protocol frames only.** Log to stderr (the template's `log()`); one stray
`print` on stdout breaks the session.

## 3. Probe

```
wicked-garden run scripts/mcp/probe.py -- node <dir>/server.mjs
wicked-garden run scripts/mcp/probe.py -- python3 <dir>/server.py
```

The probe starts the server with a minimal environment (PATH, HOME and the OS system and
temp variables only, so no ambient tokens), runs `initialize` then `tools/list` (following
`nextCursor`), and prints JSON: `ok`, `protocolVersion`, `serverInfo`, every tool with its
derived `class`, and `warnings` (an unannotated tool, a schema that is not an object, a `/`
in a name). It exits 1 with an `error` when the server fails to answer; the server's stderr
is discarded, never echoed. `--timeout <s>` (default 10) bounds the whole probe.

Do not stop at `ok: true`: check every tool's `class` is the one you meant, and clear
every warning.

**Manual alternative:** run the server command, paste these two lines on its stdin and
check that two replies come back, with `tools` in the second:

```
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"manual","version":"1"}}}
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
```

Then derive each tool's class by hand from the table in step 2.

## 4. Hand over for registration

You do not register the server; the operator does, in studio **MCP tools**, **Add
existing**: paste the run command and the secret. The preview lists every tool with its
class and what each phase role and seat would be allowed, asked or denied. Tell the
operator the command, the tool list with classes, and the name of the environment variable
that holds the secret (never its value).

What happens after registration is policy, not your server's code:

- **The first time any run uses the server, and again when a tool's schema changes, the
  call waits for the operator's approval**, in every run mode. An approval is an audited
  policy edit that adds the server or tool to the approved set.
- After approval the run mode decides: *Gate every step* asks on every write call; *Gate
  by risk* runs reads and asks on writes; *Auto* runs reads and writes.
- In every mode: evaluator phases never call write or destructive tools; an unannotated
  tool counts as write; secrets stay in the broker; unregistered servers and tools are
  denied; every call is recorded, or refused if it cannot be.
- A denied call is blocked and disclosed to the worker; the unit continues.

## In a governed run

You are in one when a wicked-crew phase directive or the `wicked-garden-governed-worker`
skill was handed to you (`WICKED_RUN_ID` is set). This is the studio **Build a server**
run. Follow `wicked-garden-governed-worker`, and:

- Write the server into the run's deliverable directory with step 1. Implement the tools
  the intent names, annotated per step 2.
- Probe it (step 3) and put the probe's JSON in your output as the evidence that it
  answers. A probe failure is a finding to fix, not to report as done.
- Do not register the server, add it to any CLI's MCP configuration, or start it outside
  the probe. Do not put a secret anywhere: name the environment variable instead. On
  deliver, studio offers the operator **Register**.
