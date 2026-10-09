// SPDX-License-Identifier: MIT
// SPDX-FileCopyrightText: __YEAR__ the __SERVER_NAME__ authors
import { spawn } from "node:child_process";
import { cpSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { createServer as createHttpServer } from "node:http";
import { createServer } from "node:net";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const ROOT = join(fileURLToPath(import.meta.url), "..", "..");
const SERVER = join(ROOT, "dist", "server.js");
const SECRET = "__SERVER_ENV___TOKEN";

function minimalEnv(extra: Record<string, string> = {}): NodeJS.ProcessEnv {
  return { PATH: process.env.PATH ?? "", HOME: process.env.HOME ?? "", ...extra };
}

/** Send frames over stdio; resolve with every reply by id once `want` ids answered. */
function converse(env: NodeJS.ProcessEnv, frames: object[], want: number[], server: string = SERVER): Promise<Map<number, any>> {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [server], { env, stdio: ["pipe", "pipe", "pipe"] });
    const replies = new Map<number, any>();
    let buf = "";
    // Generous: loading fastmcp + the OpenTelemetry SDK takes seconds on a loaded host.
    const timer = setTimeout(() => { child.kill(); reject(new Error(`timed out; got ${[...replies.keys()]}`)); }, 60_000);
    let stderr = "";
    child.stderr.on("data", (c: Buffer) => (stderr += c.toString("utf8")));
    // A server that dies before answering fails fast, naming why (not a 60 s timeout).
    child.on("exit", (code) => {
      if (!want.every((id) => replies.has(id))) {
        clearTimeout(timer);
        reject(new Error(`server exited (${code}) before answering: ${stderr.slice(0, 500)}`));
      }
    });
    child.stdout.on("data", (chunk: Buffer) => {
      buf += chunk.toString("utf8");
      let nl: number;
      while ((nl = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, nl).trim();
        buf = buf.slice(nl + 1);
        if (!line) continue;
        const msg = JSON.parse(line); // a non-JSON line on stdout fails the test: stdout is frames only
        if (typeof msg.id === "number" && ("result" in msg || "error" in msg)) replies.set(msg.id, msg);
        if (want.every((id) => replies.has(id))) {
          clearTimeout(timer);
          child.kill();
          resolve(replies);
        }
      }
    });
    child.on("error", reject);
    for (const f of frames) child.stdin.write(`${JSON.stringify({ jsonrpc: "2.0", ...f })}\n`);
  });
}

function runToExit(env: NodeJS.ProcessEnv): Promise<{ code: number | null; stderr: string }> {
  return new Promise((resolve) => {
    const child = spawn(process.execPath, [SERVER], { env, stdio: ["pipe", "ignore", "pipe"] });
    let stderr = "";
    child.stderr.on("data", (c: Buffer) => (stderr += c.toString("utf8")));
    child.on("exit", (code) => resolve({ code, stderr }));
  });
}

function freePort(): Promise<number> {
  return new Promise((resolve) => {
    const s = createServer();
    s.listen(0, "127.0.0.1", () => {
      const port = (s.address() as { port: number }).port;
      s.close(() => resolve(port));
    });
  });
}

describe("stdio conformance", () => {
  it("answers initialize, tools/list and tools/call", async () => {
    const replies = await converse(minimalEnv({ [SECRET]: "dummy" }), [
      { id: 1, method: "initialize", params: { protocolVersion: "2025-06-18", capabilities: {}, clientInfo: { name: "conformance", version: "0" } } },
      { method: "notifications/initialized" },
      { id: 2, method: "tools/list", params: {} },
      { id: 3, method: "tools/call", params: { name: "echo", arguments: { text: "hi" } } },
    ], [1, 2, 3]);
    expect(replies.get(1).result.serverInfo.name).toBe("__SERVER_NAME__");
    const tools = replies.get(2).result.tools as Array<{ name: string; annotations?: { readOnlyHint?: boolean } }>;
    expect(tools.find((t) => t.name === "echo")?.annotations?.readOnlyHint).toBe(true);
    expect(replies.get(3).result.content[0].text).toBe("hi");
  });

  it("refuses to start without the secret, naming the variable", async () => {
    const { code, stderr } = await runToExit(minimalEnv());
    expect(code).not.toBe(0);
    expect(stderr).toContain(SECRET);
  });
});

describe("generated tools (branch A)", () => {
  // A copy of the built server with a one-tool tools.json, beside node_modules so imports
  // resolve: proves the server STARTS with generated tools, lists exactly them, and calls one.
  it("starts with a non-empty tools.json, lists only the generated tools and calls one", async () => {
    const upstream = createHttpServer((req, res) => {
      if (req.url === "/v1/notes/n1") res.writeHead(200, { "content-type": "application/json" }).end(JSON.stringify({ id: "n1" }));
      else res.writeHead(404).end("not found");
    });
    await new Promise<void>((r) => upstream.listen(0, "127.0.0.1", r));
    const dir = mkdtempSync(join(ROOT, ".branch-a-"));
    try {
      cpSync(join(ROOT, "dist"), join(dir, "dist"), { recursive: true });
      const config = JSON.parse(readFileSync(join(ROOT, "mcp-server.config.json"), "utf8"));
      config.baseUrl = `http://127.0.0.1:${(upstream.address() as { port: number }).port}/v1`;
      writeFileSync(join(dir, "mcp-server.config.json"), JSON.stringify(config));
      writeFileSync(join(dir, "tools.json"), JSON.stringify({ tools: [{
        name: "get_note", description: "Read one note", class: "read",
        inputSchema: { type: "object", properties: { id: { type: "string" } }, required: ["id"] },
        rest: { method: "GET", pathTemplate: "/notes/{id}", pathMap: { id: "id" }, queryMap: {}, headerMap: {},
          bodyMap: null, bodyArg: null, argAllowlist: ["id"], timeoutMs: 5000 },
      }] }));
      const replies = await converse(minimalEnv({ [SECRET]: "dummy" }), [
        { id: 1, method: "initialize", params: { protocolVersion: "2025-06-18", capabilities: {}, clientInfo: { name: "conformance", version: "0" } } },
        { method: "notifications/initialized" },
        { id: 2, method: "tools/list", params: {} },
        { id: 3, method: "tools/call", params: { name: "get_note", arguments: { id: "n1" } } },
        { id: 4, method: "tools/call", params: { name: "get_note", arguments: {} } },
      ], [1, 2, 3, 4], join(dir, "dist", "server.js"));
      const tools = replies.get(2).result.tools as Array<{ name: string; inputSchema: { required?: string[] }; annotations?: { readOnlyHint?: boolean } }>;
      expect(tools.map((t) => t.name)).toEqual(["get_note"]);
      expect(tools[0]?.annotations?.readOnlyHint).toBe(true);
      expect(tools[0]?.inputSchema.required).toEqual(["id"]);
      expect(JSON.parse(replies.get(3).result.content[0].text)).toEqual({ id: "n1" });
      // The schema is enforced: a call missing a required argument never reaches the upstream.
      const bad = replies.get(4);
      expect(bad.error !== undefined || bad.result?.isError === true).toBe(true);
    } finally {
      rmSync(dir, { recursive: true, force: true });
      await new Promise<void>((r) => upstream.close(() => r()));
    }
  });
});

describe("httpStream", () => {
  it("refuses a request without the bearer with 401", async () => {
    const port = await freePort();
    const child = spawn(process.execPath, [SERVER], {
      env: minimalEnv({ [SECRET]: "dummy", MCP_TRANSPORT: "httpStream", MCP_PORT: String(port), MCP_SERVER_BEARER: "conformance-bearer" }),
      stdio: ["ignore", "ignore", "ignore"],
    });
    try {
      let status = 0;
      for (let i = 0; i < 240 && status === 0; i++) {
        try {
          const res = await fetch(`http://127.0.0.1:${port}/mcp`, {
            method: "POST",
            headers: { "content-type": "application/json", accept: "application/json, text/event-stream" },
            body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "initialize", params: { protocolVersion: "2025-06-18", capabilities: {}, clientInfo: { name: "c", version: "0" } } }),
          });
          status = res.status;
        } catch {
          await new Promise((r) => setTimeout(r, 250));
        }
      }
      expect(status).toBe(401);
    } finally {
      child.kill();
    }
  });
});
