// SPDX-License-Identifier: MIT
// SPDX-FileCopyrightText: __YEAR__ the __SERVER_NAME__ authors
import { metrics, trace, type Counter, type Histogram, type Meter, type Tracer } from "@opentelemetry/api";
import { OTLPLogExporter } from "@opentelemetry/exporter-logs-otlp-http";
import { OTLPMetricExporter } from "@opentelemetry/exporter-metrics-otlp-http";
import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-http";
import { BatchLogRecordProcessor } from "@opentelemetry/sdk-logs";
import { NodeSDK, metrics as sdkMetrics } from "@opentelemetry/sdk-node";

export interface ToolInstruments {
  calls: Counter;
  duration: Histogram;
  errors: Counter;
}

// Live bindings: reassigned by startTelemetry() once the SDK has registered its providers.
export let tracer: Tracer = trace.getTracer("__SERVER_NAME__");
export let meter: Meter = metrics.getMeter("__SERVER_NAME__");
export let instruments: ToolInstruments = makeInstruments(meter);

let sdk: NodeSDK | undefined;

function makeInstruments(m: Meter): ToolInstruments {
  return {
    calls: m.createCounter("mcp.tool.calls", { description: "MCP tool calls" }),
    duration: m.createHistogram("mcp.tool.duration", { description: "MCP tool call duration", unit: "ms" }),
    errors: m.createCounter("mcp.tool.errors", { description: "MCP tool calls that failed" }),
  };
}

/** True when the operator set an OTLP endpoint: the only way telemetry leaves the process. */
export function exportEnabled(env: NodeJS.ProcessEnv = process.env): boolean {
  return Boolean(env.OTEL_EXPORTER_OTLP_ENDPOINT);
}

/**
 * Start the OpenTelemetry SDK with resource service.name = the server key. The OTLP trace,
 * metric and log exporters are armed ONLY when OTEL_EXPORTER_OTLP_ENDPOINT is set; otherwise
 * the SDK runs with no exporter (spans and metrics stay in-process) and nothing leaves.
 */
export async function startTelemetry(serviceName: string, env: NodeJS.ProcessEnv = process.env): Promise<void> {
  if (sdk) return;
  const exporting = exportEnabled(env);
  sdk = new NodeSDK({
    serviceName,
    // Explicit, never env-derived: an empty list means no exporter at all.
    spanProcessors: exporting ? undefined : [],
    traceExporter: exporting ? new OTLPTraceExporter() : undefined,
    metricReaders: exporting
      ? [new sdkMetrics.PeriodicExportingMetricReader({ exporter: new OTLPMetricExporter() })]
      : [],
    logRecordProcessors: exporting ? [new BatchLogRecordProcessor({ exporter: new OTLPLogExporter() })] : [],
    instrumentations: [],
  });
  sdk.start();
  tracer = trace.getTracer(serviceName);
  meter = metrics.getMeter(serviceName);
  instruments = makeInstruments(meter);
}

export async function stopTelemetry(): Promise<void> {
  const running = sdk;
  sdk = undefined;
  await running?.shutdown().catch(() => undefined);
}
