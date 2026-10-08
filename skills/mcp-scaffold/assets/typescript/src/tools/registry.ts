// SPDX-License-Identifier: MIT
// SPDX-FileCopyrightText: __YEAR__ the __SERVER_NAME__ authors
import { SpanStatusCode } from "@opentelemetry/api";
import { UserError, type FastMCP, type Tool, type ToolParameters } from "fastmcp";
import { requireSession, type Session } from "../auth.js";
import type { ServerConfig } from "../config.js";
import { rootLogger, runWithLogger } from "../logging.js";
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

/**
 * Register one tool with the server's contract: a `mcp.tool.call` span, a request-scoped child
 * logger, the three instruments, the per-tool rate limit, and `canAccess: requireSession`.
 * A UserError reaches the caller as a tool error; anything else is logged and rethrown.
 */
export function defineTool<P extends ToolParameters>(
  server: FastMCP<Session>,
  config: ServerConfig,
  tool: Tool<Session, P>,
): void {
  const bucket = new TokenBucket(config.rateLimitPerMin);
  const execute = tool.execute;
  const own = tool.canAccess;
  server.addTool({
    ...tool,
    // The session check always holds; a tool's own canAccess can only narrow it.
    canAccess: (session) => requireSession(session) && (own === undefined || own(session)),
    execute: async (args, context) => {
      const attrs = { "mcp.server.name": config.key, "mcp.tool.name": tool.name };
      const requestId = context.requestId === undefined ? "" : String(context.requestId);
      const sessionId = context.sessionId ?? "";
      return tracer.startActiveSpan("mcp.tool.call", { attributes: { ...attrs, "mcp.request.id": requestId } }, async (span) => {
        const started = performance.now();
        const child = rootLogger().child().withContext({ tool: tool.name, requestId, sessionId });
        instruments.calls.add(1, attrs);
        let outcome = "ok";
        try {
          if (!bucket.take()) {
            outcome = "rate_limited";
            throw new UserError("rate limit");
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
    },
  });
}
