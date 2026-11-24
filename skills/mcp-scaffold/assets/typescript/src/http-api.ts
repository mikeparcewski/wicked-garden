// SPDX-License-Identifier: MIT
// SPDX-FileCopyrightText: __YEAR__ the __SERVER_NAME__ authors
//
// The REST surface (garden#1339): every registered tool also as `POST <basePath>/tools/<name>`,
// and `GET <basePath>/openapi.json`, an OpenAPI 3.1 document generated from the same tool
// definitions. Routes mount on fastmcp's own HTTP app (`server.getApp()`, a Hono app fastmcp
// consults for every request its MCP endpoint does not handle), so REST shares the httpStream
// server, its port and its host. fastmcp's custom routes are public by default: every route here
// checks the same bearer the MCP endpoint takes. A call runs the SAME wrapped execute MCP runs
// (span, request logger, instruments, rate limit), so the two surfaces give the same results.
import { randomUUID } from "node:crypto";
import { UserError, type FastMCP } from "fastmcp";
import { bearerMatches, type Session } from "./auth.js";
import type { ServerConfig } from "./config.js";
import { RateLimited, REST_SESSION, type CatalogEntry } from "./tools/registry.js";

type App = ReturnType<FastMCP<Session>["getApp"]>;

/** The largest request body a REST call accepts. */
export const REST_BODY_MAX = 1_048_576;

/** An MCP `tools/call` result: what both surfaces return for a call. */
export interface CallToolResult {
  content: unknown[];
  isError: boolean;
  [key: string]: unknown;
}

/** A tool's return value as MCP `tools/call` carries it (fastmcp's own conversion of a string). */
export function toCallToolResult(value: unknown): CallToolResult {
  if (value === undefined || value === null) return { content: [], isError: false };
  if (typeof value === "string") return { content: [{ type: "text", text: value }], isError: false };
  if (typeof value === "object" && Array.isArray((value as { content?: unknown }).content)) {
    return { isError: false, ...(value as { content: unknown[] }) };
  }
  return { content: [value], isError: false };
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
        requestBody: { required: true, content: { "application/json": { schema: t.inputSchema } } },
        responses: {
          "200": response("The tool's result, exactly as MCP tools/call returns it", "CallToolResult"),
          "400": response("The body is not JSON, or the arguments fail the tool's schema", "Error"),
          "401": response("No valid bearer", "Error"),
          "404": response("No such tool", "Error"),
          "413": response(`The body is over ${REST_BODY_MAX} bytes`, "Error"),
          "422": response("The tool refused the call (an MCP tool error, isError: true)", "CallToolResult"),
          "429": response("The tool's rate limit (shared with MCP calls)", "CallToolResult"),
          "500": response("The tool failed; the server logged why", "Error"),
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

function issuePath(path: ReadonlyArray<PropertyKey | { key: PropertyKey }> | undefined): string {
  return (path ?? []).map((p) => String(typeof p === "object" ? p.key : p)).join(".");
}

/** Mount the REST surface on fastmcp's HTTP app. `tools` is read per request (the catalog). */
export function mountRestApi(app: App, config: ServerConfig, tools: () => readonly CatalogEntry[]): void {
  const base = config.rest.basePath;

  app.get(`${base}/openapi.json`, (c) => {
    if (!bearerMatches(c.req.header("authorization"))) {
      c.header("WWW-Authenticate", "Bearer");
      return c.json({ error: "unauthorized" }, 401);
    }
    return c.json(openApiDocument(config, tools()), 200);
  });

  app.post(`${base}/tools/:name`, async (c) => {
    if (!bearerMatches(c.req.header("authorization"))) {
      c.header("WWW-Authenticate", "Bearer");
      return c.json({ error: "unauthorized" }, 401);
    }
    const tool = tools().find((t) => t.name === c.req.param("name"));
    if (tool === undefined || !tool.canAccess(REST_SESSION)) return c.json({ error: "no such tool" }, 404);
    if (Number(c.req.header("content-length") ?? "0") > REST_BODY_MAX) return c.json({ error: "body too large" }, 413);
    const raw = await c.req.text();
    if (Buffer.byteLength(raw) > REST_BODY_MAX) return c.json({ error: "body too large" }, 413);
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
      return c.json(toCallToolResult(await tool.invoke(checked.value, `rest-${randomUUID()}`)), 200);
    } catch (err) {
      if (err instanceof UserError) {
        const refused = { content: [{ type: "text", text: err.message }], isError: true };
        return c.json(refused, err instanceof RateLimited ? 429 : 422);
      }
      return c.json({ error: "internal error" }, 500); // the wrapped execute logged it
    }
  });
}
