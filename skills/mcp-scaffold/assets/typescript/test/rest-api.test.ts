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
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { z } from "zod";
import type { Session } from "../src/auth.js";
import { loadConfig, SERVER_ROOT, type ServerConfig } from "../src/config.js";
import { mountRestApi, openApiDocument, REST_BODY_MAX } from "../src/http-api.js";
import { registerExampleTools } from "../src/tools/example.js";
import { defineTool, RateLimited, toolCatalog } from "../src/tools/registry.js";

const BEARER = "rest-api-test-bearer";
const AUTH = { authorization: `Bearer ${BEARER}` };
let saved: string | undefined;

function restConfig(overrides: Partial<ServerConfig> = {}): ServerConfig {
  const config = loadConfig({ PATH: process.env.PATH ?? "", MCP_TRANSPORT: "httpStream" });
  return { ...config, rest: { enabled: true, basePath: "/api" }, ...overrides };
}

type McpTool = { name: string; execute: (args: unknown, context: unknown) => Promise<unknown> };

/** A server with REST mounted; `mcp` holds the tools exactly as fastmcp's addTool received them. */
function boot(config: ServerConfig, extra?: (server: FastMCP<Session>) => void) {
  const server = new FastMCP<Session>({ name: config.key, version: "0.1.0" });
  const mcp: McpTool[] = [];
  const addTool = server.addTool.bind(server);
  (server as unknown as { addTool: (tool: McpTool) => void }).addTool = (tool) => {
    mcp.push(tool);
    addTool(tool as any);
  };
  registerExampleTools(server, config);
  extra?.(server);
  const app = server.getApp();
  mountRestApi(app, config, () => toolCatalog(server));
  return { app, server, mcp };
}

function serve(config: ServerConfig, extra?: (server: FastMCP<Session>) => void) {
  return boot(config, extra).app;
}

/** A tools/call context as fastmcp builds one (the fields a tool may use). */
function mcpContext() {
  return {
    client: { version: undefined },
    elicit: async () => ({ action: "cancel" }),
    log: { debug() {}, error() {}, info() {}, warn() {} },
    reportProgress: async () => undefined,
    requestId: "mcp-1",
    session: { principal: "bearer" },
    signal: new AbortController().signal,
    streamContent: async () => undefined,
  };
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

describe("REST surface", () => {
  it("calls a tool and answers what MCP tools/call answers", async () => {
    const res = await post(serve(restConfig()), "/api/tools/echo", JSON.stringify({ text: "hi" }));
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ content: [{ type: "text", text: "hi" }] });
  });

  it("serves an OpenAPI 3.1 document with one POST per tool, from the tool's own schema", async () => {
    const { app, server } = boot(restConfig());
    const res = await app.request("/api/openapi.json", { headers: AUTH });
    expect(res.status).toBe(200);
    const doc = (await res.json()) as { openapi: string; paths: Record<string, { post: Record<string, any> }> };
    expect(doc.openapi).toBe("3.1.0");
    expect(Object.keys(doc.paths)).toEqual(["/tools/echo"]);
    const op = doc.paths["/tools/echo"]!.post;
    expect(op.operationId).toBe("echo");
    expect(op.requestBody.content["application/json"].schema.properties.text.type).toBe("string");
    expect(op.requestBody.content["application/json"].schema.$id).toBe(`urn:mcp:${restConfig().key}:tool:echo:input`);
    expect(op["x-mcp-annotations"].readOnlyHint).toBe(true);
    expect(doc).toEqual(openApiDocument(restConfig(), toolCatalog(server)));
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

  it("stops reading a chunked body with no content-length at the limit", async () => {
    let sent = 0;
    const endless = new ReadableStream<Uint8Array>({
      pull(controller) {
        sent += 65_536;
        controller.enqueue(new Uint8Array(65_536).fill(0x20));
      },
    });
    const res = await serve(restConfig()).request("/api/tools/echo", {
      method: "POST",
      headers: { "content-type": "application/json", ...AUTH },
      body: endless,
      duplex: "half",
    } as RequestInit);
    expect(res.status).toBe(413);
    expect(sent).toBeLessThan(REST_BODY_MAX + 4 * 65_536);
  });

  it("shares ONE rate limit between a tool's MCP and REST calls, and answers 429 as a tool error", async () => {
    // MCP first: the MCP call takes the only token, so REST is refused.
    const first = boot(restConfig({ rateLimitPerMin: 1 }));
    expect(await first.mcp.find((t) => t.name === "echo")!.execute({ text: "a" }, mcpContext())).toBe("a");
    const limited = await post(first.app, "/api/tools/echo", '{"text":"b"}');
    expect(limited.status).toBe(429);
    expect(await limited.json()).toEqual({ content: [{ type: "text", text: "rate limit" }], isError: true });
    // REST first: the REST call takes it, so MCP is refused.
    const second = boot(restConfig({ rateLimitPerMin: 1 }));
    expect((await post(second.app, "/api/tools/echo", '{"text":"a"}')).status).toBe(200);
    await expect(second.mcp.find((t) => t.name === "echo")!.execute({ text: "b" }, mcpContext())).rejects.toBeInstanceOf(RateLimited);
  });

  it("keeps each server's tools to itself, and a re-registered name runs its new definition", async () => {
    const config = restConfig();
    const a = boot(config);
    const b = boot(config, (server) =>
      defineTool(server, config, { name: "only_b", description: "B's.", parameters: z.object({}), execute: async () => "b" }),
    );
    expect((await post(a.app, "/api/tools/only_b", "{}")).status).toBe(404);
    expect((await post(b.app, "/api/tools/only_b", "{}")).status).toBe(200);
    defineTool(b.server, config, { name: "only_b", description: "B's, again.", parameters: z.object({}), execute: async () => "b2" });
    expect(await (await post(b.app, "/api/tools/only_b", "{}")).json()).toEqual({ content: [{ type: "text", text: "b2" }] });
    expect(toolCatalog(b.server).filter((t) => t.name === "only_b")).toHaveLength(1);
  });

  it("converts results as fastmcp does: structured output, a content item, nothing", async () => {
    const config = restConfig();
    const app = serve(config, (server) => {
      defineTool(server, config, {
        name: "answer",
        description: "Structured.",
        parameters: z.object({}),
        outputSchema: z.object({ answer: z.number() }),
        execute: async () => ({ answer: 42 }) as any,
      });
      defineTool(server, config, { name: "item", description: "An item.", parameters: z.object({}), execute: async () => ({ type: "text", text: "t" }) });
      defineTool(server, config, { name: "nothing", description: "Void.", parameters: z.object({}), execute: async () => undefined });
    });
    expect(await (await post(app, "/api/tools/answer", "{}")).json()).toEqual({
      content: [{ type: "text", text: '{"answer":42}' }],
      structuredContent: { answer: 42 },
    });
    expect(await (await post(app, "/api/tools/item", "{}")).json()).toEqual({ content: [{ type: "text", text: "t" }] });
    expect(await (await post(app, "/api/tools/nothing", "{}")).json()).toEqual({ content: [] });
  });

  it("passes no arguments to a tool without parameters, as MCP does", async () => {
    const config = restConfig();
    const app = serve(config, (server) =>
      defineTool(server, config, {
        name: "defaults",
        description: "No parameters.",
        execute: async (args: unknown = "default") => JSON.stringify(args),
      } as any),
    );
    expect(await (await post(app, "/api/tools/defaults", '{"injected":true}')).json()).toEqual({ content: [{ type: "text", text: '"default"' }] });
  });

  it("advertises the input side of a transform, survives a schema JSON Schema cannot hold, and keeps local refs", async () => {
    const config = restConfig();
    type Node = { name: string; children: Node[] };
    const tree: z.ZodType<Node> = z.lazy(() => z.object({ name: z.string(), children: z.array(tree) }));
    const { app, server } = boot(config, (s) => {
      defineTool(s, config, { name: "parse", description: "Transform.", parameters: z.object({ n: z.string().transform(Number) }), execute: async ({ n }) => String(n + 1) });
      defineTool(s, config, { name: "odd", description: "Unrepresentable.", parameters: z.object({ when: z.date() }), execute: async () => "ok" });
      defineTool(s, config, { name: "tree", description: "Recursive.", parameters: z.object({ root: tree }), execute: async () => "ok" });
    });
    expect(toolCatalog(server).map((t) => t.name)).toEqual(["echo", "parse", "odd", "tree"]);
    const doc = (await (await app.request("/api/openapi.json", { headers: AUTH })).json()) as any;
    const schema = (name: string) => doc.paths[`/tools/${name}`].post.requestBody.content["application/json"].schema;
    expect(schema("parse").properties.n.type).toBe("string");
    expect(schema("odd").type).toBe("object");
    expect(schema("tree").$id).toBe(`urn:mcp:${config.key}:tool:tree:input`);
    const refs = JSON.stringify(schema("tree")).match(/"\$ref":"([^"]*)"/g) ?? [];
    expect(refs.length).toBeGreaterThan(0);
    for (const ref of refs) expect(ref).toMatch(/"\$ref":"#(\/\$defs\/[^"]+)?"/);
    expect(await (await post(app, "/api/tools/parse", '{"n":"41"}')).json()).toEqual({ content: [{ type: "text", text: "42" }] });
  });

  it("answers a thrown error as fastmcp's tool error, a UserError's extras as structuredContent, a timeout as 504", async () => {
    const config = restConfig();
    const app = serve(config, (server) => {
      defineTool(server, config, {
        name: "conflict",
        description: "Refuses with details.",
        parameters: z.object({}),
        execute: async () => {
          throw new UserError("conflict", { currentVersion: 2 });
        },
      });
      defineTool(server, config, {
        name: "boom",
        description: "Fails.",
        parameters: z.object({}),
        execute: async () => {
          throw new Error("disk full");
        },
      });
      defineTool(server, config, {
        name: "slow",
        description: "Too slow.",
        parameters: z.object({}),
        timeoutMs: 50,
        execute: async (_args, context) => {
          await new Promise((resolve) => setTimeout(resolve, 2_000));
          return context.signal.aborted ? "aborted" : "late";
        },
      });
    });
    const conflict = await post(app, "/api/tools/conflict", "{}");
    expect(conflict.status).toBe(422);
    expect(await conflict.json()).toEqual({ content: [{ type: "text", text: "conflict" }], isError: true, structuredContent: { currentVersion: 2 } });
    const boom = await post(app, "/api/tools/boom", "{}");
    expect(boom.status).toBe(500);
    expect(await boom.json()).toEqual({ content: [{ type: "text", text: "Tool 'boom' execution failed: disk full" }], isError: true });
    const slow = await post(app, "/api/tools/slow", "{}");
    expect(slow.status).toBe(504);
    expect(((await slow.json()) as { isError: boolean }).isError).toBe(true);
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
    const dir = mkdtempSync(join(tmpdir(), "rest-config-"));
    try {
      // From an isolated config with no `rest` key: the committed one is the project's own
      // (`scaffold.py --rest` turns it on), so the default is not read from it.
      const raw = JSON.parse(readFileSync(join(SERVER_ROOT, "mcp-server.config.json"), "utf8"));
      const bare = { ...raw };
      delete bare.rest;
      writeFileSync(join(dir, "mcp-server.config.json"), JSON.stringify(bare));
      expect(loadConfig({ PATH: process.env.PATH ?? "" }, dir).rest).toEqual({ enabled: false, basePath: "/api" });
      writeFileSync(join(dir, "mcp-server.config.json"), JSON.stringify({ ...raw, transport: "stdio", rest: { enabled: true, basePath: "/api" } }));
      expect(loadConfig({ PATH: process.env.PATH ?? "" }, dir).rest.enabled).toBe(true);
      writeFileSync(join(dir, "mcp-server.config.json"), JSON.stringify({ ...raw, transport: "httpStream", rest: { enabled: true, basePath: "/mcp" } }));
      expect(() => loadConfig({ PATH: process.env.PATH ?? "" }, dir)).toThrow(/rest\.basePath/);
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });
});
