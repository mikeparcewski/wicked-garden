// SPDX-License-Identifier: MIT
// SPDX-FileCopyrightText: __YEAR__ the __SERVER_NAME__ authors
import { FastMCP } from "fastmcp";
import { authenticate, configureAuth, loadSecret, upstreamHeaders, type Session } from "./auth.js";
import { loadConfig, secretVar } from "./config.js";
import { fastmcpLogger, initLogging } from "./logging.js";
import { startTelemetry, stopTelemetry } from "./telemetry.js";
import { registerExampleTools } from "./tools/example.js";
import { registerGeneratedTools } from "./tools/generated.js";

async function main(): Promise<void> {
  const config = loadConfig();
  await startTelemetry(config.key);
  const root = initLogging([secretVar(config.key)]);
  const secret = loadSecret(config);
  if (config.transport === "httpStream" && !process.env.MCP_SERVER_BEARER) {
    throw new Error("MCP_SERVER_BEARER is not set: httpStream refuses to start without the bearer clients must present");
  }
  configureAuth(config);

  const server = new FastMCP<Session>({
    name: config.key,
    version: config.version as `${number}.${number}.${number}`,
    instructions: `${config.key}: tools over ${new URL(config.baseUrl).host}. Every call is authenticated, rate limited and traced.`,
    logger: fastmcpLogger(root),
    authenticate: config.transport === "httpStream" ? authenticate : undefined,
  });

  const generated = registerGeneratedTools(server, config, () => upstreamHeaders(config, secret));
  // The example `echo` tool only stands in while tools.json is empty: a server with generated
  // tools exposes exactly those (plus whatever you register by hand).
  if (generated === 0) registerExampleTools(server, config);
  root.withMetadata({ generated, transport: config.transport }).info("starting");

  const stop = async () => {
    await server.stop().catch(() => undefined);
    await stopTelemetry();
    process.exit(0);
  };
  process.once("SIGTERM", stop);
  process.once("SIGINT", stop);

  if (config.transport === "httpStream") {
    await server.start({ transportType: "httpStream", httpStream: { host: config.host, port: config.port, endpoint: config.endpoint as `/${string}` } });
  } else {
    await server.start({ transportType: "stdio" });
  }
}

main().catch((err: unknown) => {
  // stderr only: stdout carries protocol frames.
  process.stderr.write(`__SERVER_NAME__: ${err instanceof Error ? err.message : String(err)}\n`);
  process.exit(1);
});
