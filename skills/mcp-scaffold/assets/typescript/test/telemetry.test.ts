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
    const env = { ...process.env, OTEL_EXPORTER_OTLP_ENDPOINT: endpoint };
    const saved = process.env.OTEL_EXPORTER_OTLP_ENDPOINT;
    process.env.OTEL_EXPORTER_OTLP_ENDPOINT = endpoint; // the OTLP exporters read it themselves
    try {
      await startTelemetry("__SERVER_NAME__", env);
      initLogging([]).info("loglayer-export-marker");
      await stopTelemetry(); // shutdown flushes the batch processor
    } finally {
      if (saved === undefined) delete process.env.OTEL_EXPORTER_OTLP_ENDPOINT;
      else process.env.OTEL_EXPORTER_OTLP_ENDPOINT = saved;
    }
    const logs = received.filter((r) => r.path === "/v1/logs");
    expect(logs.some((r) => r.body.includes("loglayer-export-marker"))).toBe(true);
  });
});
