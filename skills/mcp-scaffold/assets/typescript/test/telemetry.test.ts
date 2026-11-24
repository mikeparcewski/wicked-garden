// SPDX-License-Identifier: MIT
// SPDX-FileCopyrightText: __YEAR__ the __SERVER_NAME__ authors
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { createServer, type Server } from "node:http";
import type { AddressInfo } from "node:net";
import { initLogging } from "../src/logging.js";
import { startTelemetry, stopTelemetry } from "../src/telemetry.js";

// A local OTLP/HTTP collector: records each POST's path and raw body (JSON or protobuf both carry the text).
const received: { path: string; body: Buffer }[] = [];
let collector: Server;
let endpoint = "";

beforeAll(async () => {
  collector = createServer((req, res) => {
    const chunks: Buffer[] = [];
    req.on("data", (c: Buffer) => chunks.push(c));
    req.on("end", () => {
      received.push({ path: req.url ?? "", body: Buffer.concat(chunks) });
      res.writeHead(200, { "content-type": "application/json" }).end("{}");
    });
  });
  await new Promise<void>((resolve) => collector.listen(0, "127.0.0.1", resolve));
  endpoint = `http://127.0.0.1:${(collector.address() as AddressInfo).port}`;
});

afterAll(async () => {
  await new Promise<void>((resolve) => collector.close(() => resolve()));
});

describe("telemetry export", () => {
  it("a log written through the server's LogLayer logger reaches the OTLP collector", async () => {
    // Hermetic: the SDK and the OTLP exporters read OTEL_* from process.env themselves, so an
    // inherited signal endpoint, compression or OTEL_SDK_DISABLED would send the log elsewhere or
    // encode it. Clear every OTEL_* for the run, set only the local collector, then restore.
    const otel = (): string[] => Object.keys(process.env).filter((k) => k.startsWith("OTEL_"));
    const saved = Object.fromEntries(otel().map((k) => [k, process.env[k]]));
    for (const k of otel()) delete process.env[k];
    process.env.OTEL_EXPORTER_OTLP_ENDPOINT = endpoint;
    try {
      await startTelemetry("__SERVER_NAME__", { OTEL_EXPORTER_OTLP_ENDPOINT: endpoint });
      initLogging([]).info("loglayer-export-marker");
      await stopTelemetry(); // shutdown flushes the batch processor
    } finally {
      for (const k of otel()) delete process.env[k];
      Object.assign(process.env, saved);
    }
    const logs = received.filter((r) => r.path === "/v1/logs");
    expect(logs.some((r) => r.body.includes("loglayer-export-marker"))).toBe(true);
  });
});
