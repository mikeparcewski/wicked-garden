# Kind `mcp-server`: an MCP inspector editor

Loaded on demand by the `wicked-garden-editor-scaffold` skill (its `SKILL.md` points here). An editor
that claims kind `mcp-server` tests and debugs an MCP server: it lists the server's tools, resources
and prompts, calls them with arguments, and shows the results and the raw JSON-RPC log
(DES-MCP-INSPECTOR-001).

## Who does what

The frame still has no network. **The host makes the calls, and wicked-crew holds the connection.**

- The **host** draws the target picker (a server registered in crew's MCP tools, a stdio command, or
  an HTTP/SSE URL), the confirm that names the exact command and its args or the URL, and Connect,
  Restart, Disconnect and Copy log. It also draws a call line ("12 calls · last: tools/call echo ·
  8 ms"), so no call is quiet. None of these are the editor's; never draw a look-alike.
- The **editor** sees the server's traffic and nothing else: never the session id, the command line,
  its args, cwd, env, headers or the URL.
- The bridge owns `initialize` and declares no client capabilities, so a server's request for
  sampling, elicitation or roots is answered `-32601` and shows in the log.

## Permission: `mcp.session`

"to start and talk to the MCP servers you connect it to". Declare it with `artifact.read`, plus
`ui.fullscreen` if the editor goes full screen.

- **The install consent is the grant.** The install plan lists "This plugin can start and talk to MCP
  servers" with this build's token, `editor:<id>@<version>#<sha256>/mcp.session`. When the operator
  approves, crew writes that token into the `EDITOR-GRANTS` steering rule.
- **There is no global allow.** No steering rule grants `mcp.session`, however broad; only the exact
  per-build token does. An editor that doesn't declare it never gets it.
- **A new version or hash asks again.** An update replaces the token (and drops it if the update no
  longer declares it). An uninstall withdraws it first. The operator revokes it in Steering, and a
  `deny` on `editor-perm:mcp.session` beats the grant.
- **It is not a write grant.** Write and destructive tools of a registered server start disabled.
  Only a human enables one, on the MCP tools page. `mcp.session` never stands in for that.

## Request: `mcp.request` `{method, params?}` → `{response, ms, truncated}`

- `method` is one of `tools/list`, `tools/call`, `resources/list`, `resources/templates/list`,
  `resources/read`, `prompts/list`, `prompts/get`, `completion/complete`, `logging/setLevel`, `ping`.
- `response` is the server's `{result}` or `{error: {code, message, data?}}` with secrets scrubbed.
  A JSON-RPC `error` is a successful reply: show it as the server's error.
- `truncated` is true when the answer was over the cap and was cut. The log entry carries the cut
  text.
- The reply limit is **60 s**, not the usual 10 s. A `timeout` may still land later: it shows in the
  log.
- **`tools/call` only from a click.** Send it inside a real user activation (a click or Enter on the
  editor's own control). A call nobody clicked for is refused `refused`, and three refusals tear the
  editor down. Never call tools on load, on a timer or in a loop.

| Error `code` on the reply | Means | Show |
|---|---|---|
| `not_granted` | this build holds no `mcp.session` grant | "Not allowed to talk to MCP servers" |
| `unavailable` | no server connected (the conformance host never has one) | "Not connected": the host's Connect is the way in |
| `write_not_granted` | the bridge's **403**: a write or destructive tool on a registered server that no human has enabled, or whose schema changed since | the message, plus "enable it on the MCP tools page". Never retry |
| `server_changed` | the bridge's **409**: the registered server was re-saved with another command or URL after this session connected | the message, plus "Restart to reconnect" (the host's button). Never retry |
| `bad_request` | an older studio that has no `mcp.request` | "This studio can't inspect MCP servers" |

A read tool stays callable whether it is enabled or not. A typed command or URL has no registry grant:
the host's confirm names exactly what runs.

## Events (host → editor)

- `mcp.state` `{state, server, protocolVersion, capabilities, instructions, error}`, where `state` is
  `none`, `connecting`, `ready`, `closed` or `failed`. On `ready`, list again. On `closed` or
  `failed`, keep what is shown, mark it stale, and point at the host's Restart.
- `mcp.log` `{entries}`, the bridge's log as it is polled. Each entry is `{seq, at, dir: out|in|host,
  kind: request|response|notification|stderr|state, method?, rpcId?, ms?, error?, text,
  truncated?}`. `text` is JSON or stderr text, at most 64 KB. A jump in `seq` is a gap: the ring
  evicted those entries. Show it as a gap and don't guess what was in it.

Render every `text`, result and schema as text (`textContent`), never as markup. It is the server's
content, the same way a page's HTML is.

## Building one

- Scaffold with `--kinds mcp-server --permissions artifact.read,mcp.session,ui.fullscreen`.
- The arguments form is built from the tool's `inputSchema`. A value the form can't express falls back
  to a raw JSON box, which is checked before sending.
- **Conformance:** the conformance host has no session, so every `mcp.request` answers `unavailable`.
  The editor must still pass every case: show "Not connected", and keep answering pings.
- **Older services:** a crew without the MCP inspector refuses to install an editor that declares
  `mcp.session` (an unknown permission), and an older studio answers `mcp.request` with
  `bad_request`. Report either one as it is. Never drop the permission to get past it.
