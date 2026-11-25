// SPDX-License-Identifier: MIT
// SPDX-FileCopyrightText: __YEAR__ the __SERVER_NAME__ authors
//
// The REST surface (garden#1339): every registered tool also as `POST <basePath>/tools/<name>`,
// and `GET <basePath>/openapi.json`, an OpenAPI 3.1 document generated from the same tool
// definitions. Routes mount on fastmcp's own HTTP app (`server.getApp()`, a Hono app fastmcp
// consults for every request its MCP endpoint does not handle), so REST shares the httpStream
// server, its port and its host. fastmcp's custom routes are public by default: every route here
// checks the same bearer the MCP endpoint takes. A call runs the SAME wrapped execute MCP runs
// (span, request logger, instruments, rate limit) and turns its value and its errors into the
// result fastmcp's tools/call handler builds, so the two surfaces give the same results.
import { randomUUID } from "node:crypto";
import { UserError, type FastMCP } from "fastmcp";
import { bearerMatches, type Session } from "./auth.js";
import { getLogger } from "./logging.js";
import type { ServerConfig } from "./config.js";
import { RateLimited, REST_SESSION, TimedOut, type CatalogEntry, type StandardSchema } from "./tools/registry.js";

type App = ReturnType<FastMCP<Session>["getApp"]>;

/** The largest request body a REST call accepts. */
export const REST_BODY_MAX = 1_048_576;

/** An MCP `tools/call` result: what both surfaces return for a call. */
export interface CallToolResult {
  content: unknown[];
  isError?: boolean;
  structuredContent?: unknown;
  [key: string]: unknown;
}

function issuePath(path: ReadonlyArray<PropertyKey | { key: PropertyKey }> | undefined): string {
  return (path ?? []).map((p) => String(typeof p === "object" ? p.key : p)).join(".");
}

/** A content item MCP can carry: an object with a string `type`, and a string `text` on text. */
function isContentItem(item: unknown): boolean {
  if (typeof item !== "object" || item === null) return false;
  const { type, text } = item as { type?: unknown; text?: unknown };
  return typeof type === "string" && (type !== "text" || typeof text === "string");
}

/** fastmcp's structured-output check: a UserError naming each issue as `path: message`. */
async function structured(name: string, outputSchema: StandardSchema, value: unknown): Promise<unknown> {
  const checked = await outputSchema["~standard"].validate(value);
  if (checked.issues === undefined) return checked.value;
  const issues = checked.issues.map((i) => `${issuePath(i.path) || "root"}: ${i.message}`).join(", ");
  throw new UserError(`Tool '${name}' structured output validation failed: ${issues}. Please check the result matches the tool's outputSchema.`);
}

/**
 * A tool's return value as fastmcp's tools/call handler carries it: nothing is `content: []`, a
 * string one text item, a `{content}` result itself (with an `outputSchema`, only when every item
 * is a content item; its `structuredContent` is checked), a value with an `outputSchema` its JSON
 * as text plus `structuredContent`, a content item (`{type}`) one item. Anything else throws, as
 * it fails fastmcp's own result check (a tool error over both surfaces).
 */
export async function toCallToolResult(name: string, value: unknown, outputSchema?: StandardSchema): Promise<CallToolResult> {
  if (value === undefined || value === null) return { content: [] };
  if (typeof value === "string") return { content: [{ type: "text", text: value }] };
  const content = typeof value === "object" ? (value as { content?: unknown }).content : undefined;
  if (Array.isArray(content) && (outputSchema === undefined || content.every(isContentItem))) {
    if (!content.every(isContentItem)) throw new Error("the result holds an item that is not MCP content");
    const result = value as CallToolResult;
    if (outputSchema === undefined || result.structuredContent === undefined) return result;
    return { ...result, structuredContent: await structured(name, outputSchema, result.structuredContent) };
  }
  if (outputSchema !== undefined) {
    const checked = await structured(name, outputSchema, value);
    return { content: [{ type: "text", text: JSON.stringify(checked) }], structuredContent: checked };
  }
  if (isContentItem(value)) return { content: [value] };
  throw new Error("the result is not a string, a content result or a content item");
}

/** A tool error as fastmcp returns it: the message as text, a UserError's extras as structuredContent. */
export function toolError(text: string, extras?: Record<string, unknown>): CallToolResult {
  return { content: [{ type: "text", text }], isError: true, ...(extras === undefined ? {} : { structuredContent: extras }) };
}

/** Read a request body, stopping at `max` bytes: undefined past it (nothing more is read). */
async function readCapped(request: Request, max: number): Promise<string | undefined> {
  if (request.body === null) return "";
  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > max) {
      await reader.cancel();
      return undefined;
    }
    chunks.push(value);
  }
  return Buffer.concat(chunks).toString("utf8");
}

const CALL_TOOL_RESULT = {
  type: "object",
  required: ["content"],
  properties: {
    content: {
      type: "array",
      items: { type: "object", required: ["type"], properties: { type: { type: "string" }, text: { type: "string" } } },
    },
    isError: { type: "boolean" },
    structuredContent: {},
  },
};
const ERROR = { type: "object", required: ["error"], properties: { error: { type: "string" }, issues: { type: "array" } } };

function response(description: string, schema: "CallToolResult" | "Error") {
  return { description, content: { "application/json": { schema: { $ref: `#/components/schemas/${schema}` } } } };
}

/** The OpenAPI 3.1 document for `tools`: one POST operation per tool, its schema the tool's own. */
export function openApiDocument(config: ServerConfig, tools: readonly CatalogEntry[]): Record<string, unknown> {
  const paths: Record<string, unknown> = {};
  for (const t of tools) {
    paths[`/tools/${t.name}`] = {
      post: {
        operationId: t.name,
        summary: t.description.split("\n")[0],
        description: t.description,
        "x-mcp-annotations": t.annotations ?? {},
        // Each schema keeps its own identity ($id), so its local refs (#/$defs/..., a recursive
        // "#") resolve inside it, not against this document.
        requestBody: { required: true, content: { "application/json": { schema: { $id: `urn:mcp:${config.key}:tool:${t.name}:input`, ...t.inputSchema() } } } },
        responses: {
          "200": response("The tool's result, as MCP tools/call returns it", "CallToolResult"),
          "400": response("The body is not JSON, or the arguments fail the tool's schema", "Error"),
          "401": response("No valid bearer", "Error"),
          // fastmcp answers a 404 from these routes as an unmatched request: no body
          "404": { description: "No such tool (no body)" },
          "413": response(`The body is over ${REST_BODY_MAX} bytes`, "Error"),
          "422": response("The tool refused the call (an MCP tool error, isError: true)", "CallToolResult"),
          "429": response("The tool's rate limit (shared with MCP calls)", "CallToolResult"),
          "500": response("The tool failed (an MCP tool error, isError: true); the server logged why", "CallToolResult"),
          "504": response("The tool ran past its timeoutMs (an MCP tool error, isError: true)", "CallToolResult"),
        },
      },
    };
  }
  return {
    openapi: "3.1.0",
    info: { title: config.key, version: config.version, description: `${config.key}: its MCP tools as a REST API.` },
    servers: [{ url: config.rest.basePath }],
    security: [{ bearer: [] }],
    components: {
      securitySchemes: { bearer: { type: "http", scheme: "bearer" } },
      schemas: { CallToolResult: CALL_TOOL_RESULT, Error: ERROR },
    },
    paths,
  };
}

/** Mount the REST surface on fastmcp's HTTP app. `tools` is read per request (the catalog). */
export function mountRestApi(app: App, config: ServerConfig, tools: () => readonly CatalogEntry[]): void {
  const base = config.rest.basePath;

  app.get(`${base}/openapi.json`, (c) => {
    if (!bearerMatches(c.req.header("authorization"))) {
      c.header("WWW-Authenticate", "Bearer");
      return c.json({ error: "unauthorized" }, 401);
    }
    // the tools this caller may run, as fastmcp lists only those a session may access
    return c.json(openApiDocument(config, tools().filter((t) => t.canAccess(REST_SESSION))), 200);
  });

  app.post(`${base}/tools/:name`, async (c) => {
    if (!bearerMatches(c.req.header("authorization"))) {
      c.header("WWW-Authenticate", "Bearer");
      return c.json({ error: "unauthorized" }, 401);
    }
    const tool = tools().find((t) => t.name === c.req.param("name"));
    if (tool === undefined || !tool.canAccess(REST_SESSION)) return c.json({ error: "no such tool" }, 404);
    if (Number(c.req.header("content-length") ?? "0") > REST_BODY_MAX) return c.json({ error: "body too large" }, 413);
    const raw = await readCapped(c.req.raw, REST_BODY_MAX); // a chunked body is counted as it arrives
    if (raw === undefined) return c.json({ error: "body too large" }, 413);
    let body: unknown;
    try {
      body = raw.trim() === "" ? {} : JSON.parse(raw);
    } catch {
      return c.json({ error: "the body is not JSON" }, 400);
    }
    const checked = await tool.validate(body);
    if (checked.issues !== undefined) {
      const issues = checked.issues.map((i) => ({ path: issuePath(i.path), message: i.message }));
      return c.json({ error: "invalid arguments", issues }, 400);
    }
    try {
      const value = await tool.invoke(checked.value, `rest-${randomUUID()}`);
      return c.json(await toCallToolResult(tool.name, value, tool.outputSchema), 200);
    } catch (err) {
      if (err instanceof UserError) {
        const status = err instanceof RateLimited ? 429 : err instanceof TimedOut ? 504 : 422;
        return c.json(toolError(err.message, err.extras), status);
      }
      // fastmcp's text for a failed tool (a thrown tool error is logged by the wrapped execute;
      // a result that fails conversion is logged here)
      const message = err instanceof Error ? err.message : String(err);
      getLogger().withError(err as Error).error("REST tool call failed");
      return c.json(toolError(`Tool '${tool.name}' execution failed: ${message}`), 500);
    }
  });
}
