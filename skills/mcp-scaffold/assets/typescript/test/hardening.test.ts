// SPDX-License-Identifier: MIT
// SPDX-FileCopyrightText: __YEAR__ the __SERVER_NAME__ authors
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { createServer, type Server } from "node:http";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { UserError } from "fastmcp";
import { upstreamCredentials } from "../src/auth.js";
import { loadConfig, SERVER_ROOT, type ServerConfig } from "../src/config.js";
import { buildRequest, type RestMapping } from "../src/rest.js";
import { ERROR_BODY_MAX, registerGeneratedTools, upstreamError } from "../src/tools/generated.js";

const BASE_VAR = "__SERVER_ENV___BASE_URL";

describe("upstream error text", () => {
  it("scrubs every credential the server sent, whole or after its scheme", () => {
    const text = upstreamError(401, "bad header: Bearer tok-1234 (tok-1234)", {
      headers: { Authorization: "Bearer tok-1234" },
      query: {},
    });
    expect(text).toBe("HTTP 401: bad header: [redacted] ([redacted])");
  });

  it("scrubs a query-parameter key too, raw and URL-encoded (garden#1261)", () => {
    const sent = { headers: {}, query: { api_key: "k3y/with+chars" } };
    const text = upstreamError(403, "bad key k3y/with+chars in /x?api_key=k3y%2Fwith%2Bchars", sent);
    expect(text).not.toContain("k3y");
    expect(text).toBe("HTTP 403: bad key [redacted] in /x?api_key=[redacted]");
  });

  it("bounds the body a caller sees", () => {
    const text = upstreamError(500, "x".repeat(ERROR_BODY_MAX * 3), { headers: {}, query: {} });
    expect(text.length).toBeLessThan(ERROR_BODY_MAX + 40);
    expect(text).toContain("(truncated)");
  });
});

describe("base URL override", () => {
  const committed = new URL(loadConfig({}).baseUrl);

  it("may move the path on the committed origin", () => {
    const moved = `${committed.origin}/v2`;
    expect(loadConfig({ [BASE_VAR]: moved }).baseUrl).toBe(moved);
  });

  it("refuses another origin: the credential would follow it", () => {
    expect(() => loadConfig({ [BASE_VAR]: "https://elsewhere.invalid/v1" })).toThrow(/committed baseUrl origin/);
  });
});

describe("query-parameter API key (garden#1261)", () => {
  const queryConfig = (base: string): ServerConfig => {
    const c = loadConfig({});
    return { ...c, baseUrl: base, auth: { ...c.auth, scheme: "api-key", queryParam: "api_key" } };
  };
  const search: RestMapping = {
    method: "GET", pathTemplate: "/search", pathMap: {}, queryMap: { q: "q", key: "api_key" }, headerMap: {},
    bodyMap: null, bodyArg: null, argAllowlist: ["q", "key"], timeoutMs: 5000,
  };

  it("sends the key as the query parameter, never a header, and no argument can set it", async () => {
    const creds = await upstreamCredentials(queryConfig("https://api.example.com/v1"), "s3cret-key");
    expect(creds).toEqual({ headers: {}, query: { api_key: "s3cret-key" } });
    const { url, init } = buildRequest("https://api.example.com/v1", search, { q: "cats", key: "attacker" }, creds);
    expect(url.searchParams.getAll("api_key")).toEqual(["s3cret-key"]);
    expect(url.searchParams.get("q")).toBe("cats");
    expect(Object.values(init.headers as Record<string, string>)).not.toContain("s3cret-key");
  });

  it("refuses a query key on any scheme but api-key", () => {
    const dir = mkdtempSync(join(tmpdir(), "mcp-cfg-"));
    const committed = JSON.parse(readFileSync(join(SERVER_ROOT, "mcp-server.config.json"), "utf8"));
    writeFileSync(join(dir, "mcp-server.config.json"),
      JSON.stringify({ ...committed, auth: { ...committed.auth, scheme: "bearer", queryParam: "api_key" } }));
    expect(() => loadConfig({}, dir)).toThrow(/auth\.queryParam/);
    writeFileSync(join(dir, "mcp-server.config.json"),
      JSON.stringify({ ...committed, auth: { ...committed.auth, scheme: "api-key", queryParam: "api_key" } }));
    expect(loadConfig({}, dir).auth.queryParam).toBe("api_key");
  });

  describe("an upstream that echoes the request URL in its error", () => {
    let stub: Server;
    let base = "";
    beforeAll(async () => {
      stub = createServer((req, res) => {
        res.writeHead(401, { "content-type": "text/plain" }).end(`invalid key for ${req.url}`);
      });
      await new Promise<void>((r) => stub.listen(0, "127.0.0.1", r));
      base = `http://127.0.0.1:${(stub.address() as { port: number }).port}/v1`;
    });
    afterAll(() => new Promise<void>((r) => stub.close(() => r())));

    it("a transport error naming the URL is scrubbed before the span or the caller sees it", async () => {
      const { callRest } = await import("../src/rest.js");
      const creds = { headers: {}, query: { api_key: "s3cret-key" } };
      const err = await callRest(search, { q: "x" }, {
        baseUrl: base,
        credentials: async () => creds,
        readOnly: false,
        fetchImpl: (async (u: URL) => {
          throw new TypeError(`fetch failed for ${u.href}`);
        }) as unknown as typeof fetch,
      }).catch((e: unknown) => e);
      expect((err as Error).message).toContain("api_key=[redacted]");
      expect((err as Error).message).not.toContain("s3cret-key");
    });

    it("comes back scrubbed", async () => {
      const config = queryConfig(base);
      const added: any[] = [];
      const fake = { addTool: (t: unknown) => added.push(t) } as any;
      registerGeneratedTools(fake, config, () => upstreamCredentials(config, "s3cret-key"), [
        { name: "search", inputSchema: { type: "object", properties: { q: { type: "string" } } }, class: "read", rest: search },
      ]);
      const ctx = { requestId: "r1", sessionId: "s1", log: {} } as any;
      const err = await added[0].execute({ q: "cats" }, ctx).catch((e: unknown) => e);
      expect(err).toBeInstanceOf(UserError);
      expect((err as Error).message).toContain("HTTP 401: invalid key for /v1/search?q=cats&api_key=[redacted]");
      expect((err as Error).message).not.toContain("s3cret-key");
    });
  });
});
