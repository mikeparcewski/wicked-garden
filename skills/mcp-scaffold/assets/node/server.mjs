#!/usr/bin/env node
// __SERVER_NAME__ — an MCP server over stdio (newline-delimited JSON-RPC 2.0).
// Scaffolded by wicked-garden-mcp-scaffold. Zero dependencies; Node >= 20.
//
// Rules this file keeps (the broker that registers it relies on them):
//   - stdout carries protocol frames only; every log line goes to stderr.
//   - every tool declares annotations honestly; a tool with none is treated as a WRITE.
//   - a secret arrives in the environment (the broker injects it at call time);
//     never log it, never return it, never take it as a tool argument.
import { createInterface } from 'node:readline';

const SERVER = { name: '__SERVER_NAME__', version: '0.1.0' };
// Newest first. An unsupported client version is answered with SUPPORTED[0].
const SUPPORTED = ['2025-11-25', '2025-06-18', '2025-03-26', '2024-11-05'];

// In-process state for the example write tool; replace with your own backend.
let counter = 0;

// Each tool: its MCP description plus a handler(args) returning text.
// A handler throws ToolError for a bad call (returned as isError, the turn continues).
class ToolError extends Error {}

const TOOLS = {
  echo: {
    description: 'Return the given text unchanged.',
    inputSchema: {
      type: 'object',
      properties: { text: { type: 'string', description: 'Text to return.' } },
      required: ['text'],
      additionalProperties: false,
    },
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
    handler: ({ text }) => {
      if (typeof text !== 'string') throw new ToolError('text must be a string');
      return text;
    },
  },
  counter_increment: {
    description: 'Add to an in-memory counter and return the new value.',
    inputSchema: {
      type: 'object',
      properties: { by: { type: 'integer', minimum: 1, description: 'Amount to add (default 1).' } },
      additionalProperties: false,
    },
    annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: false },
    handler: ({ by = 1 }) => {
      if (!Number.isInteger(by) || by < 1) throw new ToolError('by must be a positive integer');
      counter += by;
      return String(counter);
    },
  },
};

const log = (msg) => process.stderr.write(`[${SERVER.name}] ${msg}\n`);
const send = (frame) => process.stdout.write(`${JSON.stringify({ jsonrpc: '2.0', ...frame })}\n`);

class RpcError extends Error {
  constructor(code, message) {
    super(message);
    this.code = code;
  }
}

const isObject = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);

function initialize(params) {
  const asked = params.protocolVersion;
  return {
    protocolVersion: SUPPORTED.includes(asked) ? asked : SUPPORTED[0],
    capabilities: { tools: { listChanged: false } },
    serverInfo: SERVER,
  };
}

function listTools() {
  return {
    tools: Object.entries(TOOLS).map(([name, { description, inputSchema, annotations }]) => ({
      name, description, inputSchema, annotations,
    })),
  };
}

function callTool(params) {
  const tool = Object.hasOwn(TOOLS, params.name) ? TOOLS[params.name] : undefined;
  if (!tool) throw new RpcError(-32602, `unknown tool: ${params.name}`);
  const args = params.arguments ?? {};
  if (!isObject(args)) throw new RpcError(-32602, 'arguments must be an object');
  try {
    return { content: [{ type: 'text', text: tool.handler(args) }] };
  } catch (err) {
    if (!(err instanceof ToolError)) throw err;
    return { content: [{ type: 'text', text: err.message }], isError: true };
  }
}

const METHODS = {
  initialize,
  ping: () => ({}),
  'tools/list': listTools,
  'tools/call': callTool,
};

function handle(line) {
  let msg;
  try {
    msg = JSON.parse(line);
  } catch {
    send({ id: null, error: { code: -32700, message: 'parse error' } });
    return;
  }
  const isRequest = msg !== null && typeof msg === 'object' && 'id' in msg;
  if (!isRequest) return; // notifications (e.g. notifications/initialized) get no reply
  const method = Object.hasOwn(METHODS, msg.method) ? METHODS[msg.method] : undefined;
  try {
    if (!method) throw new RpcError(-32601, `method not found: ${msg.method}`);
    const params = msg.params ?? {};
    if (!isObject(params)) throw new RpcError(-32602, 'params must be an object');
    send({ id: msg.id, result: method(params) });
  } catch (err) {
    if (err instanceof RpcError) {
      send({ id: msg.id, error: { code: err.code, message: err.message } });
      return;
    }
    log(`internal error in ${msg.method}: ${err.message}`);
    send({ id: msg.id, error: { code: -32603, message: 'internal error' } });
  }
}

createInterface({ input: process.stdin }).on('line', (line) => {
  if (line.trim()) handle(line);
});
