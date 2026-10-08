// SPDX-License-Identifier: MIT
// SPDX-FileCopyrightText: __YEAR__ the __SERVER_NAME__ authors
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { UserError, type FastMCP, type ToolParameters } from "fastmcp";
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
      // A plain JSON Schema, exactly as the conversion service derived it from the OpenAPI document.
      parameters: t.inputSchema as unknown as ToolParameters,
      annotations: annotationsFor(t.class),
      execute: async (args) => {
        const result = await callRest(t.rest, (args ?? {}) as Record<string, unknown>, {
          baseUrl: config.baseUrl,
          headers,
          readOnly: t.class === "read",
        });
        const text = typeof result.body === "string" ? result.body : JSON.stringify(result.body);
        if (result.status >= 400) throw new UserError(`HTTP ${result.status}: ${text}`);
        return text;
      },
    });
  }
  return tools.length;
}
