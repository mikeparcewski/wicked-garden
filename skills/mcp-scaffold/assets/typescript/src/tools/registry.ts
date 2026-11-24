// SPDX-License-Identifier: MIT
// SPDX-FileCopyrightText: __YEAR__ the __SERVER_NAME__ authors
import { SpanStatusCode } from "@opentelemetry/api";
import { UserError, type FastMCP, type Tool, type ToolParameters } from "fastmcp";
import { z } from "zod";
import { requireSession, type Session } from "../auth.js";
import type { ServerConfig } from "../config.js";
import { getLogger, rootLogger, runWithLogger } from "../logging.js";
import { instruments, tracer } from "../telemetry.js";

/** A per-tool token bucket: `rateLimitPerMin` calls, refilled continuously. */
export class TokenBucket {
  private tokens: number;
  private last: number;
  constructor(private readonly perMin: number, private readonly now: () => number = Date.now) {
    this.tokens = perMin;
    this.last = now();
  }
  take(): boolean {
    const t = this.now();
    this.tokens = Math.min(this.perMin, this.tokens + ((t - this.last) * this.perMin) / 60_000);
    this.last = t;
    if (this.tokens < 1) return false;
    this.tokens -= 1;
    return true;
  }
}

/** The rate-limit refusal: a tool error over MCP, HTTP 429 over REST. */
export class RateLimited extends UserError {
  constructor() {
    super("rate limit");
  }
}

/** The surface a call came in on, stamped on its span. */
export type Surface = "mcp" | "rest";

/** A Standard Schema validation result (fastmcp's tool parameters are Standard Schemas). */
export type Validated =
  | { value: unknown; issues?: undefined }
  | { issues: ReadonlyArray<{ message: string; path?: ReadonlyArray<PropertyKey | { key: PropertyKey }> }> };

/**
 * One registered tool, as the REST surface (`src/http-api.ts`) sees it: the same definition and
 * the SAME wrapped call MCP uses (span, logger, instruments, rate limit), so the two surfaces
 * cannot drift apart.
 */
export interface CatalogEntry {
  name: string;
  description: string;
  annotations: Record<string, unknown> | undefined;
  /** The JSON Schema of the arguments (the OpenAPI request body). */
  inputSchema: Record<string, unknown>;
  validate: (args: unknown) => Promise<Validated>;
  canAccess: (session: Session | undefined) => boolean;
  invoke: (args: unknown, requestId: string) => Promise<unknown>;
}

const catalog: CatalogEntry[] = [];

/** Every tool defineTool registered, in registration order. */
export function toolCatalog(): readonly CatalogEntry[] {
  return catalog;
}

/** Forget the catalog (tests that build more than one server in a process). */
export function resetCatalog(): void {
  catalog.length = 0;
}

type StandardSchema = { "~standard": { validate: (value: unknown) => Validated | Promise<Validated> } };

function jsonSchemaOf(parameters: unknown): Record<string, unknown> {
  if (parameters instanceof z.ZodType) return z.toJSONSchema(parameters) as Record<string, unknown>;
  return { type: "object" };
}

/** The principal of a REST call: the same bearer the httpStream MCP endpoint takes. */
export const REST_SESSION: Session = { principal: "bearer" };

/** The context a REST call hands the tool: fastmcp's fields, with no MCP session behind them. */
function restContext(requestId: string) {
  const log = {
    debug: (message: string) => getLogger().debug(message),
    error: (message: string) => getLogger().error(message),
    info: (message: string) => getLogger().info(message),
    warn: (message: string) => getLogger().warn(message),
  };
  return {
    client: { version: undefined },
    log,
    reportProgress: async () => undefined,
    requestId,
    session: REST_SESSION,
    sessionId: undefined,
    streamContent: async () => undefined,
  };
}

/**
 * Register one tool with the server's contract: a `mcp.tool.call` span, a request-scoped child
 * logger, the three instruments, the per-tool rate limit, and `canAccess: requireSession`.
 * A UserError reaches the caller as a tool error; anything else is logged and rethrown.
 * The tool also joins the catalog the REST surface serves (garden#1339); `jsonSchema` is its
 * argument schema when `parameters` is not a zod schema (a generated tool's tools.json entry).
 */
export function defineTool<P extends ToolParameters>(
  server: FastMCP<Session>,
  config: ServerConfig,
  tool: Tool<Session, P>,
  jsonSchema?: Record<string, unknown>,
): void {
  const bucket = new TokenBucket(config.rateLimitPerMin);
  const execute = tool.execute;
  const own = tool.canAccess;
  // The session check always holds; a tool's own canAccess can only narrow it.
  const canAccess = (session: Session | undefined) => requireSession(session) && (own === undefined || own(session as Session));
  type Args = Parameters<typeof execute>[0];
  type Ctx = Parameters<typeof execute>[1];
  const call = async (args: Args, context: Ctx, surface: Surface) => {
    const attrs = { "mcp.server.name": config.key, "mcp.tool.name": tool.name };
    const requestId = context.requestId === undefined ? "" : String(context.requestId);
    const sessionId = context.sessionId ?? "";
    return tracer.startActiveSpan("mcp.tool.call", { attributes: { ...attrs, "mcp.request.id": requestId, "mcp.surface": surface } }, async (span) => {
      const started = performance.now();
      const child = rootLogger().child().withContext({ tool: tool.name, requestId, sessionId, surface });
      instruments.calls.add(1, attrs);
      let outcome = "ok";
      try {
        if (!bucket.take()) {
          outcome = "rate_limited";
          throw new RateLimited();
        }
        return await runWithLogger(child, () => execute(args, context));
      } catch (err) {
        if (outcome === "ok") outcome = err instanceof UserError ? "user_error" : "error";
        instruments.errors.add(1, { ...attrs, outcome });
        span.setStatus({ code: SpanStatusCode.ERROR });
        if (!(err instanceof UserError)) {
          child.withError(err as Error).error("tool call failed");
        }
        throw err;
      } finally {
        span.setAttribute("outcome", outcome);
        instruments.duration.record(performance.now() - started, attrs);
        span.end();
      }
    });
  };
  server.addTool({
    ...tool,
    canAccess,
    execute: (args, context) => call(args, context, "mcp"),
  });
  const parameters = tool.parameters as unknown as StandardSchema | undefined;
  catalog.push({
    name: tool.name,
    description: tool.description ?? tool.name,
    annotations: tool.annotations as unknown as Record<string, unknown> | undefined,
    inputSchema: jsonSchema ?? jsonSchemaOf(tool.parameters),
    validate: async (args) => (parameters === undefined ? { value: args } : await parameters["~standard"].validate(args)),
    canAccess,
    invoke: (args, requestId) => call(args as Args, restContext(requestId) as unknown as Ctx, "rest"),
  });
}
