// SPDX-License-Identifier: MIT
// SPDX-FileCopyrightText: __YEAR__ the __SERVER_NAME__ authors
//
// The REST surface in-process (garden#1339): routes on fastmcp's own app, the OpenAPI document,
// auth, validation, the shared rate limit and tool errors. test/conformance.test.ts boots the
// built server and checks that REST and MCP give the same result for the same call.
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { FastMCP, UserError } from "fastmcp";
import { afterAll, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { z } from "zod";
import type { Session } from "../src/auth.js";
import { loadConfig, SERVER_ROOT, type ServerConfig } from "../src/config.js";
import { mountRestApi, openApiDocument, REST_BODY_MAX } from "../src/http-api.js";
import { registerExampleTools } from "../src/tools/example.js";
import { defineTool, resetCatalog, toolCatalog } from "../src/tools/registry.js";

const BEARER = "rest-api-test-bearer";
const AUTH = { authorization: `Bearer ${BEARER}` };
let saved: string | undefined;

function restConfig(overrides: Partial<ServerConfig> = {}): ServerConfig {
  const config = loadConfig({ PATH: process.env.PATH ?? "", MCP_TRANSPORT: "httpStream" });
  return { ...config, rest: { enabled: true, basePath: "/api" }, ...overrides };
}

function serve(config: ServerConfig, extra?: (server: FastMCP<Session>) => void) {
  const server = new FastMCP<Session>({ name: config.key, version: "0.1.0" });
  registerExampleTools(server, config);
  extra?.(server);
  const app = server.getApp();
  mountRestApi(app, config, toolCatalog);
  return app;
}

function post(app: ReturnType<typeof serve>, path: string, body: string, headers: Record<string, string> = AUTH) {
  return app.request(path, { method: "POST", headers: { "content-type": "application/json", ...headers }, body });
}

beforeAll(() => {
  saved = process.env.MCP_SERVER_BEARER;
  process.env.MCP_SERVER_BEARER = BEARER;
});
afterAll(() => {
  if (saved === undefined) delete process.env.MCP_SERVER_BEARER;
  else process.env.MCP_SERVER_BEARER = saved;
});
beforeEach(() => resetCatalog());

describe("REST surface", () => {
  it("calls a tool and answers what MCP tools/call answers", async () => {
    const res = await post(serve(restConfig()), "/api/tools/echo", JSON.stringify({ text: "hi" }));
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ content: [{ type: "text", text: "hi" }], isError: false });
  });

  it("serves an OpenAPI 3.1 document with one POST per tool, from the tool's own schema", async () => {
    const app = serve(restConfig());
    const res = await app.request("/api/openapi.json", { headers: AUTH });
    expect(res.status).toBe(200);
    const doc = (await res.json()) as { openapi: string; paths: Record<string, { post: Record<string, any> }> };
    expect(doc.openapi).toBe("3.1.0");
    expect(Object.keys(doc.paths)).toEqual(["/tools/echo"]);
    const op = doc.paths["/tools/echo"]!.post;
    expect(op.operationId).toBe("echo");
    expect(op.requestBody.content["application/json"].schema.properties.text.type).toBe("string");
    expect(op["x-mcp-annotations"].readOnlyHint).toBe(true);
    expect(doc).toEqual(openApiDocument(restConfig(), toolCatalog()));
  });

  it("refuses every route without the bearer, and with a wrong one", async () => {
    const app = serve(restConfig());
    expect((await app.request("/api/openapi.json")).status).toBe(401);
    expect((await post(app, "/api/tools/echo", '{"text":"hi"}', {})).status).toBe(401);
    expect((await post(app, "/api/tools/echo", '{"text":"hi"}', { authorization: "Bearer nope" })).status).toBe(401);
  });

  it("refuses an unknown tool, a non-JSON body, bad arguments and an oversized body", async () => {
    const app = serve(restConfig());
    expect((await post(app, "/api/tools/nope", "{}")).status).toBe(404);
    expect((await post(app, "/api/tools/echo", "{not json")).status).toBe(400);
    const bad = await post(app, "/api/tools/echo", JSON.stringify({ text: "" }));
    expect(bad.status).toBe(400);
    expect(((await bad.json()) as { issues: Array<{ path: string }> }).issues[0]?.path).toBe("text");
    const big = await post(app, "/api/tools/echo", JSON.stringify({ text: "x".repeat(REST_BODY_MAX) }));
    expect(big.status).toBe(413);
  });

  it("shares the tool's rate limit with MCP and answers 429 as a tool error", async () => {
    const app = serve(restConfig({ rateLimitPerMin: 1 }));
    expect((await post(app, "/api/tools/echo", '{"text":"a"}')).status).toBe(200);
    const limited = await post(app, "/api/tools/echo", '{"text":"b"}');
    expect(limited.status).toBe(429);
    expect(await limited.json()).toEqual({ content: [{ type: "text", text: "rate limit" }], isError: true });
  });

  it("answers a UserError as 422 with the MCP tool-error result", async () => {
    const config = restConfig();
    const app = serve(config, (server) =>
      defineTool(server, config, {
        name: "refuse",
        description: "Always refuses.",
        parameters: z.object({}),
        execute: async () => {
          throw new UserError("not today");
        },
      }),
    );
    const res = await post(app, "/api/tools/refuse", "{}");
    expect(res.status).toBe(422);
    expect(await res.json()).toEqual({ content: [{ type: "text", text: "not today" }], isError: true });
  });
});

describe("REST config", () => {
  it("is off by default, loads on stdio (served on httpStream only), and keeps off the MCP endpoint", () => {
    expect(loadConfig({ PATH: process.env.PATH ?? "" }).rest).toEqual({ enabled: false, basePath: "/api" });
    const dir = mkdtempSync(join(tmpdir(), "rest-config-"));
    try {
      const raw = JSON.parse(readFileSync(join(SERVER_ROOT, "mcp-server.config.json"), "utf8"));
      writeFileSync(join(dir, "mcp-server.config.json"), JSON.stringify({ ...raw, transport: "stdio", rest: { enabled: true, basePath: "/api" } }));
      expect(loadConfig({ PATH: process.env.PATH ?? "" }, dir).rest.enabled).toBe(true);
      writeFileSync(join(dir, "mcp-server.config.json"), JSON.stringify({ ...raw, transport: "httpStream", rest: { enabled: true, basePath: "/mcp" } }));
      expect(() => loadConfig({ PATH: process.env.PATH ?? "" }, dir)).toThrow(/rest\.basePath/);
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });
});
