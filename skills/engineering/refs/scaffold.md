# scaffold — start a new CLI, service or library

The `scaffold` action of `wicked-garden-engineering`, and the build step of wicked-crew's `scaffold`
workflow (the **Start something new** card, kinds CLI, service and library). An MCP server is not
this ref: use `wicked-garden-mcp-scaffold`, which has its own templates, probe and install.

The kind comes from the brief's `Kind: CLI.`, `Kind: service.` or `Kind: library.` line; for a
service, the design says whether it serves HTTP or is a worker. The stack,
the layout and the interfaces come from the design step's blueprint
(`wicked-garden-engineering-solution-architect`). The stack is the person's and the design's choice,
never yours.

## Before you write anything

1. **The stack.** Use what the design names. With no design, use what the repository already uses
   (language, package manager, test runner). In a near-empty repository with no stack named, do not
   pick one: report it as a blocker in your output.
2. **The target directory.** The repository root of a near-empty repository, or the subdirectory
   the design names. Every file you would write must be absent. If one exists, name the first
   collision and write nothing: a scaffold never overwrites.
3. **Built-ins first.** Check what the stack's standard library and chosen framework already give
   at the version the repository pins (argument parsing, HTTP serving, logging, test runner). Use
   them. Custom code that duplicates a built-in needs a stated reason, and the review step flags it.

## Steps

1. **Generate** with the stack's own generator when it has one that writes only into the target
   directory (`cargo new`, `cargo init`, `npm init -y`, `uv init`, `go mod init`, `dotnet new`).
   Record the command and its version. Hand-write only what the generator does not give.
2. **The first slice.** The skeleton plus the behaviour the intent names. When the intent names
   only the skeleton, one small example behaviour the tests exercise.
3. **Dependencies:** only what the design names, recorded in the ecosystem's lockfile. No framework
   the design did not choose.
4. **Tests** under the stack's standard runner: at least one test per public behaviour, plus a
   smoke that starts the thing (per kind, below). They run green with one command.
5. **Formatting and lint** config only when the stack has a standard default (rustfmt, gofmt, the
   framework's recommended lint set) or the repository already has one.
6. **README:** what it is, then one command each to build, test and run, and every configuration
   variable by NAME.
7. **Secrets** never enter the tree. Read them from the environment, list their names in an
   `.env.example` with no values, and ignore env files and build output in `.gitignore`.
8. **Licence and CI:** add neither unless the repository already has one (then extend it in its
   own style) or the brief names one. Choosing a licence is a person's decision.
9. **Run** the build and the test command, and put their exit codes in the record.

## Per kind

| Kind | Must have | Smoke test |
|---|---|---|
| CLI | the stack's standard argument parser; `--help` and `--version`; exit 0 on success, 1 on failure, 2 on a usage error; results on stdout, diagnostics on stderr; no prompt when stdin is not a terminal; `--json` output when the intent names scripting | `--help` exits 0 and names every subcommand |
| Service: HTTP | configuration from the environment with safe defaults (bind to localhost unless the design says otherwise; port from the environment); a health endpoint that touches no dependency; graceful shutdown on SIGTERM; input validated before the handler; a timeout on every outbound call; logs on stderr | the service starts, the health endpoint answers 200, and it stops on SIGTERM |
| Service: worker | configuration from the environment; the input the design names (a queue, a schedule, a stream) behind one interface a test can replace; idempotent handling of a message seen twice; graceful shutdown on SIGTERM that finishes or returns the message in hand; a timeout on every outbound call; logs on stderr. No HTTP interface unless the design names one | the worker starts, handles one message from a test double, and stops on SIGTERM |
| Library | a small public API at the package root; nothing runs at import; no global state; silent unless the caller configures logging; package metadata (name, version `0.1.0`, description, repository) and exported types; a README usage example that a test runs (a doctest where the ecosystem has one) | import the package and make one public call |

A container file, a deployment manifest or a release workflow is added only when the design names
one.

## The scaffold record (your output)

The test and review steps read it. Write it in this shape:

```
SCAFFOLD service at services/quotes (kind from the brief)
STACK: TypeScript, Node 22, fastify 5 (from: design step)
GENERATOR: npm init -y (npm 10.9); hand-written: src/server.ts, src/health.ts, test/health.test.ts
BUILT-INS CHECKED: fastify 5 logger and schema validation used; no extra logger added
COMMANDS: build `npm run build` · test `npm test` · run `npm start`
RESULT: build exit 0; test exit 0 (6 passed)
CONFIG: QUOTES_PORT, QUOTES_UPSTREAM_URL, QUOTES_TOKEN (names only)
NOT DONE: licence (not in the brief), CI (the repository has none)
```

Never report a command you did not run. A failing test is a finding to fix before the step ends,
not a result to hand on.
