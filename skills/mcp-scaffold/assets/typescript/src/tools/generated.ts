// SPDX-License-Identifier: MIT
// SPDX-FileCopyrightText: __YEAR__ the __SERVER_NAME__ authors
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { UserError, jsonSchemaAdapter, type FastMCP, type JsonSchemaObject, type ToolParameters } from "fastmcp";
import type { Session } from "../auth.js";
import { SERVER_ROOT, type ServerConfig } from "../config.js";
import { callRest, type RestMapping } from "../rest.js";
import { defineTool } from "./registry.js";

/** One tools.json entry, as wicked-crew's conversion service (`openapi` action) writes it. */
export interface GeneratedTool {
  name: string;
  description?: string;
  inputSchema: Record<string, unknown>;
  class: "read" | "write" | "destructive";
  rest: RestMapping;
}

/** The MCP annotations a class implies; every REST tool reaches a system outside the server. */
export function annotationsFor(cls: GeneratedTool["class"]) {
  switch (cls) {
    case "read":
      return { readOnlyHint: true, openWorldHint: true };
    case "write":
      return { readOnlyHint: false, destructiveHint: false, openWorldHint: true };
    case "destructive":
      return { readOnlyHint: false, destructiveHint: true, openWorldHint: true };
  }
}

export function readToolsJson(root: string = SERVER_ROOT): GeneratedTool[] {
  const doc = JSON.parse(readFileSync(join(root, "tools.json"), "utf8")) as { tools?: GeneratedTool[] };
  return Array.isArray(doc.tools) ? doc.tools : [];
}

/** The most of an upstream error body a caller sees. */
export const ERROR_BODY_MAX = 300;

/**
 * The tool error for an upstream 4xx/5xx: the status plus a bounded excerpt of the body with
 * every credential this server sent scrubbed out, so an upstream that echoes its auth header
 * back cannot hand the secret to the caller.
 */
export function upstreamError(status: number, body: string, sent: Record<string, string>): string {
  let text = body;
  for (const value of Object.values(sent)) {
    const parts = [value, value.includes(" ") ? value.slice(value.indexOf(" ") + 1) : ""];
    for (const part of parts) if (part.length >= 4) text = text.split(part).join("[redacted]");
  }
  if (text.length > ERROR_BODY_MAX) text = `${text.slice(0, ERROR_BODY_MAX)}… (truncated)`;
  return text ? `HTTP ${status}: ${text}` : `HTTP ${status}`;
}

/** Register every tools.json entry; each call goes through callRest, pinned to the base URL. */
export function registerGeneratedTools(
  server: FastMCP<Session>,
  config: ServerConfig,
  headers: () => Promise<Record<string, string>>,
  tools: GeneratedTool[] = readToolsJson(),
): number {
  for (const t of tools) {
    defineTool(server, config, {
      name: t.name,
      description: t.description ?? t.name,
      // fastmcp takes a Standard Schema, not a plain JSON Schema: a raw schema here makes the
      // server refuse to start. jsonSchemaAdapter validates the conversion service's schema
      // with ajv (a direct dependency of this server).
      parameters: jsonSchemaAdapter(t.inputSchema as JsonSchemaObject) as unknown as ToolParameters,
      annotations: annotationsFor(t.class),
      execute: async (args) => {
        const result = await callRest(t.rest, (args ?? {}) as Record<string, unknown>, {
          baseUrl: config.baseUrl,
          headers,
          readOnly: t.class === "read",
        });
        const text = typeof result.body === "string" ? result.body : JSON.stringify(result.body);
        if (result.status >= 400) throw new UserError(upstreamError(result.status, text, await headers()));
        return text;
      },
    });
  }
  return tools.length;
}
