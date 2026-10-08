// SPDX-License-Identifier: MIT
// SPDX-FileCopyrightText: __YEAR__ the __SERVER_NAME__ authors
import type { FastMCP } from "fastmcp";
import { z } from "zod";
import type { Session } from "../auth.js";
import type { ServerConfig } from "../config.js";
import { getLogger } from "../logging.js";
import { defineTool } from "./registry.js";

/** A hand-written tool (replace me): zod-validated input, honest annotations. */
export function registerExampleTools(server: FastMCP<Session>, config: ServerConfig): void {
  defineTool(server, config, {
    name: "echo",
    description: "Echo the given text back. Changes nothing anywhere.",
    parameters: z.object({ text: z.string().min(1).max(4096).describe("the text to echo") }),
    annotations: { title: "Echo", readOnlyHint: true, idempotentHint: true, openWorldHint: false },
    execute: async ({ text }) => {
      getLogger().withMetadata({ length: text.length }).debug("echo");
      return text;
    },
  });
}
