// SPDX-License-Identifier: MIT
// SPDX-FileCopyrightText: __YEAR__ the __SERVER_NAME__ authors
//
// The per-tool contract test shape: a local stub answers the OpenAPI example response, the
// tool returns the mapped result, and a 4xx comes back as a tool error (isError). Copy this
// file once per tool in tools.json.
import { createServer, type Server } from "node:http";
import { UserError } from "fastmcp";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { loadConfig } from "../../src/config.js";
import { BoundaryError, buildRequest } from "../../src/rest.js";
import { annotationsFor, registerGeneratedTools, type GeneratedTool } from "../../src/tools/generated.js";

const EXAMPLE = { id: "n1", title: "first note" };

const getNote: GeneratedTool = {
  name: "get_note",
  description: "Read one note",
  inputSchema: { type: "object", properties: { id: { type: "string" } }, required: ["id"] },
  class: "read",
  rest: {
    method: "GET", pathTemplate: "/notes/{id}", pathMap: { id: "id" }, queryMap: {}, headerMap: {},
    bodyMap: null, bodyArg: null, argAllowlist: ["id"], timeoutMs: 5000,
  },
};

let stub: Server;
let baseUrl = "";
const seen: Array<{ url: string; auth: string | undefined }> = [];

beforeAll(async () => {
  stub = createServer((req, res) => {
    seen.push({ url: req.url ?? "", auth: req.headers.authorization });
    if (req.url === "/v1/notes/n1") {
      res.writeHead(200, { "content-type": "application/json" }).end(JSON.stringify(EXAMPLE));
    } else {
      res.writeHead(404, { "content-type": "application/json" }).end(JSON.stringify({ error: "not found" }));
    }
  });
  await new Promise<void>((r) => stub.listen(0, "127.0.0.1", r));
  baseUrl = `http://127.0.0.1:${(stub.address() as { port: number }).port}/v1`;
});

afterAll(() => new Promise<void>((r) => stub.close(() => r())));

/** Register the tool on a recording fake server and hand back its wrapped execute. */
function toolUnderTest(tool: GeneratedTool) {
  const config = { ...loadConfig({}), baseUrl };
  const added: any[] = [];
  const fake = { addTool: (t: unknown) => added.push(t) } as any;
  registerGeneratedTools(fake, config, async () => ({ Authorization: "Bearer test-token" }), [tool]);
  return added[0];
}

const ctx = { requestId: "r1", sessionId: "s1", log: {} } as any;

describe("get_note contract", () => {
  it("is annotated read", () => {
    expect(toolUnderTest(getNote).annotations).toEqual(annotationsFor("read"));
  });

  it("returns the mapped example response", async () => {
    const out = await toolUnderTest(getNote).execute({ id: "n1", extra: "dropped" }, ctx);
    expect(JSON.parse(out)).toEqual(EXAMPLE);
    expect(seen.at(-1)).toEqual({ url: "/v1/notes/n1", auth: "Bearer test-token" });
  });

  it("answers a 4xx as a tool error", async () => {
    await expect(toolUnderTest(getNote).execute({ id: "missing" }, ctx)).rejects.toBeInstanceOf(UserError);
  });

  it("never leaves the base URL", () => {
    expect(() => buildRequest(baseUrl, getNote.rest, { id: ".." }, {})).toThrow(BoundaryError);
  });
});
