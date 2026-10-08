# __SERVER_NAME__

An MCP server on [fastmcp](https://github.com/punkpeye/fastmcp) (TypeScript, Node >= 22),
logging through loglayer, tracing and metering through OpenTelemetry, authenticated on every
tool. Scaffolded by `wicked-garden-mcp-scaffold`.

## Run

```
npm install
npm run build
node dist/server.js        # with __SERVER_ENV___TOKEN exported in your environment
```

stdout carries MCP protocol frames only; every log line goes to stderr.

## Probe

```
wicked-garden run scripts/mcp/probe.py --env __SERVER_ENV___TOKEN -- node dist/server.js
```

The probe starts the server with a minimal environment plus only the variables named with
`--env`, runs `initialize` and `tools/list`, and prints every tool with its class
(read / write / destructive) as wicked-crew's broker derives it.

## The one secret

The server reads exactly ONE secret: `__SERVER_ENV___TOKEN` — the bearer token, the API key, the
basic-auth password or the OAuth2 client secret, as `auth.scheme` in `mcp-server.config.json`
says. Everything else about auth (header name, basic user, token URL, scopes, client id) is
committed, non-secret configuration in `mcp-server.config.json`. A missing secret fails at
startup naming the variable. One variable is the contract because wicked-crew's broker and
registry inject exactly one environment variable into a stdio server. See `.env.example`.

Optional overrides: `MCP_TRANSPORT` (`stdio` | `httpStream`), `MCP_HOST` (default
`127.0.0.1`), `MCP_PORT`,
`__SERVER_ENV___BASE_URL`. httpStream requires `MCP_SERVER_BEARER`: every request must carry
`Authorization: Bearer <it>` or is refused with 401.

## Telemetry

Off by default: the OpenTelemetry SDK runs with no exporter unless
`OTEL_EXPORTER_OTLP_ENDPOINT` is set, so nothing leaves the process. With it set, traces
(`mcp.tool.call`, `http.client.request`), metrics (`mcp.tool.calls`, `mcp.tool.duration`,
`mcp.tool.errors`) and log records are exported over OTLP/HTTP.

## Tools

- **Generated (branch A):** `tools.json` holds the tools wicked-crew's conversion service
  derived from an OpenAPI 3 document — run
  `wicked-garden run scripts/mcp/openapi.py --name __SERVER_NAME__ --base-url <url> --spec-url <url> --out .`
  `src/tools/generated.ts` registers each one; calls go through `src/rest.ts`, pinned to
  `baseUrl`, allowlisted arguments only, no redirects.
- **Hand-written (branch B):** add a file like `src/tools/example.ts`: a zod schema, honest
  annotations, registered through `defineTool` (span, child logger, metrics, rate limit and
  `canAccess` come with it).

Every tool gets a contract test (copy `test/contract/example.test.ts`); `npm test` also
runs the stdio conformance smoke (`test/conformance.test.ts`).

## Install

```
wicked-garden run scripts/mcp/install.py --dir .
```

builds and stages the server under `~/.wicked/mcp-servers/__SERVER_NAME__/current/`, probes
it, registers it in wicked-crew's MCP registry (`auth.ref: env:__SERVER_ENV___TOKEN` — no value
is ever sent), writes it into your CLI MCP configs through `wicked-installer mcp upsert` and
records `installed.json`. Re-running it updates the installed copy in place, by key.
