// SPDX-License-Identifier: MIT
// SPDX-FileCopyrightText: __YEAR__ the __SERVER_NAME__ authors
import { AsyncLocalStorage } from "node:async_hooks";
import { Console } from "node:console";
import { format } from "node:util";
import { openTelemetryPlugin } from "@loglayer/plugin-opentelemetry";
import { redactionPlugin } from "@loglayer/plugin-redaction";
import { OpenTelemetryTransport } from "@loglayer/transport-opentelemetry";
import { ConsoleTransport, LogLayer, type ILogLayer } from "loglayer";

const REDACT_ALWAYS = ["authorization", "token", "secret", "password", "client_secret"];

/**
 * stdout carries MCP protocol frames only: the console transport writes to stderr.
 */
const stderrConsole = new Console({ stdout: process.stderr, stderr: process.stderr });

function build(secretNames: string[]): ILogLayer {
  return new LogLayer({
    plugins: [openTelemetryPlugin(), redactionPlugin({ paths: [...secretNames, ...REDACT_ALWAYS] })],
    transport: [new OpenTelemetryTransport({}), new ConsoleTransport({ logger: stderrConsole })],
  });
}

let root: ILogLayer = build([]);
const als = new AsyncLocalStorage<{ logger: ILogLayer }>();

/** Build the root logger once the secret variable's name is known (it is redacted by name). */
export function initLogging(secretNames: string[]): ILogLayer {
  root = build(secretNames);
  return root;
}

export function rootLogger(): ILogLayer {
  return root;
}

/** The request-scoped logger when inside a tool call, else the root. */
export function getLogger(): ILogLayer {
  return als.getStore()?.logger ?? root;
}

export function runWithLogger<T>(child: ILogLayer, fn: () => T): T {
  return als.run({ logger: child }, fn);
}

/** fastmcp's Logger (debug/error/info/log/warn) adapted onto the root logger. */
export function fastmcpLogger(logger: ILogLayer = root) {
  const line = (args: unknown[]) => format(...args);
  return {
    debug: (...args: unknown[]) => logger.debug(line(args)),
    error: (...args: unknown[]) => logger.error(line(args)),
    info: (...args: unknown[]) => logger.info(line(args)),
    log: (...args: unknown[]) => logger.info(line(args)),
    warn: (...args: unknown[]) => logger.warn(line(args)),
  };
}
