// SPDX-License-Identifier: MIT
// SPDX-FileCopyrightText: __YEAR__ the __SERVER_NAME__ authors
import { SpanKind, SpanStatusCode } from "@opentelemetry/api";
import { tracer } from "./telemetry.js";

/** One tools.json entry's request mapping, as wicked-crew's conversion service writes it. */
export interface RestMapping {
  method: "GET" | "HEAD" | "OPTIONS" | "POST" | "PUT" | "PATCH" | "DELETE";
  pathTemplate: string;
  pathMap: Record<string, string>;
  queryMap: Record<string, string>;
  headerMap: Record<string, string>;
  bodyMap: Record<string, string> | null;
  bodyArg: string | null;
  argAllowlist: string[];
  timeoutMs: number;
}

/** Every credential a request carries: header(s) and/or query parameter(s). */
export interface Credentials {
  headers: Record<string, string>;
  query: Record<string, string>;
}

export interface RestContext {
  baseUrl: string;
  /** The upstream credentials — their header and query names are also forbidden to arguments. */
  credentials: () => Promise<Credentials>;
  /** Read tools are retried on 429/5xx; write and destructive tools never are. */
  readOnly: boolean;
  fetchImpl?: typeof fetch;
}

export interface RestResult {
  status: number;
  body: unknown;
  /** The exact credentials this request carried — what an error scrub must remove. */
  sent: Credentials;
}

/**
 * `text` with every credential in `sent` (header and query values; raw, after a `Bearer `-style
 * scheme, and URL-encoded) replaced by `[redacted]`. The ONE scrub: upstream error bodies and
 * transport errors (whose message may carry the request URL, query key included) both use it.
 */
export function scrubCredentials(text: string, sent: Credentials): string {
  let out = text;
  for (const value of [...Object.values(sent.headers), ...Object.values(sent.query)]) {
    const bare = value.includes(" ") ? value.slice(value.indexOf(" ") + 1) : "";
    const spellings = (v: string) => [
      v,
      encodeURIComponent(v),
      new URLSearchParams({ v }).toString().slice(2),
      JSON.stringify(v).slice(1, -1), // as an echoed JSON body serializes it
    ];
    const parts = [...spellings(value), ...(bare ? spellings(bare) : [])];
    // Longest first, so a scrubbed prefix never leaves the rest of a longer spelling behind.
    // Every non-empty spelling: a short key is still a key.
    for (const part of [...new Set(parts)].sort((a, b) => b.length - a.length)) {
      if (part.length > 0) out = out.split(part).join("[redacted]");
    }
  }
  return out;
}

/** Headers an argument can never set: routing, auth and the hop-by-hop set. */
const DENY_HEADERS = new Set([
  "authorization", "proxy-authorization", "cookie", "host", "content-length", "content-type",
  "transfer-encoding", "connection", "keep-alive", "upgrade", "te", "trailer", "expect",
  "forwarded", "x-forwarded-for", "x-forwarded-host", "x-forwarded-proto",
]);

const RETRIES = 2;

/** A request that would leave the pinned base URL. */
export class BoundaryError extends Error {}

function scalar(v: unknown, what: string): string {
  if (typeof v === "string") return v;
  if (typeof v === "number" || typeof v === "boolean") return String(v);
  throw new Error(`${what} must be a string, number or boolean`);
}

function basePath(base: URL): string {
  return base.pathname.replace(/\/+$/, "");
}

function escapes(base: URL, url: URL): string | null {
  if (url.origin !== base.origin) return `the request to ${url.origin} leaves the pinned host ${base.origin}`;
  const prefix = basePath(base);
  if (prefix !== "" && url.pathname !== prefix && !url.pathname.startsWith(`${prefix}/`)) {
    return `the request path ${url.pathname} leaves the pinned base path ${prefix}`;
  }
  return null;
}

/** Build the one request a call makes from the ALLOWLISTED arguments, pinned to the base URL. */
export function buildRequest(
  baseUrl: string,
  mapping: RestMapping,
  args: Record<string, unknown>,
  creds: Credentials = { headers: {}, query: {} },
): { url: URL; init: RequestInit } {
  const authHeaders = creds.headers;
  const base = new URL(baseUrl);
  const allowed = new Set(mapping.argAllowlist);
  const sent = Object.fromEntries(Object.entries(args).filter(([k]) => allowed.has(k)));
  const filled = mapping.pathTemplate.replace(/\{([^{}]+)\}/g, (_m, name: string) => {
    const arg = Object.keys(mapping.pathMap).find((a) => mapping.pathMap[a] === name);
    const v = arg === undefined ? undefined : sent[arg];
    if (v === undefined) throw new Error(`the path variable {${name}} has no value`);
    const text = scalar(v, `the path argument ${arg}`);
    if (text === "" || text === "." || text === "..") throw new BoundaryError(`the path value for {${name}} would move the request off its path`);
    return encodeURIComponent(text);
  });
  if (!filled.startsWith("/")) throw new BoundaryError(`the path ${JSON.stringify(mapping.pathTemplate)} does not start with /`);
  const url = new URL(base.href);
  url.pathname = `${basePath(base)}${filled}`;
  const escape = escapes(base, url);
  if (escape !== null) throw new BoundaryError(escape);
  const authQuery = new Set(Object.keys(creds.query));
  for (const [arg, q] of Object.entries(mapping.queryMap)) {
    const v = sent[arg];
    // An argument never sets (or doubles) the credential's query parameter.
    if (v === undefined || v === null || authQuery.has(q)) continue;
    for (const item of Array.isArray(v) ? v : [v]) url.searchParams.append(q, scalar(item, `the query argument ${arg}`));
  }
  const deny = new Set(DENY_HEADERS);
  for (const h of Object.keys(authHeaders)) deny.add(h.toLowerCase());
  const headers: Record<string, string> = { accept: "application/json, */*;q=0.5" };
  for (const [arg, h] of Object.entries(mapping.headerMap)) {
    const v = sent[arg];
    if (v === undefined || v === null || deny.has(h.toLowerCase())) continue;
    const text = scalar(v, `the header argument ${arg}`);
    if (/[\r\n\0]/.test(text)) throw new Error(`the header argument ${arg} must be one line`);
    headers[h] = text;
  }
  let body: string | undefined;
  if (mapping.bodyArg !== null && sent[mapping.bodyArg] !== undefined) {
    body = JSON.stringify(sent[mapping.bodyArg]);
  } else if (mapping.bodyMap !== null) {
    const obj: Record<string, unknown> = {};
    for (const [arg, key] of Object.entries(mapping.bodyMap)) if (sent[arg] !== undefined) obj[key] = sent[arg];
    if (Object.keys(obj).length > 0 || ["POST", "PUT", "PATCH"].includes(mapping.method)) body = JSON.stringify(obj);
  }
  if (body !== undefined) headers["content-type"] = "application/json";
  Object.assign(headers, authHeaders);
  // After the boundary check (a query never moves the origin or path): the credential last.
  for (const [q, value] of Object.entries(creds.query)) url.searchParams.set(q, value);
  return { url, init: { method: mapping.method, headers, ...(body !== undefined ? { body } : {}) } };
}

async function readBody(res: Response): Promise<unknown> {
  const text = await res.text();
  if (/json/i.test(res.headers.get("content-type") ?? "")) {
    try {
      return JSON.parse(text);
    } catch {
      return text;
    }
  }
  return text;
}

/**
 * Call one REST tool: never follows a redirect, bounded by the mapping's timeoutMs, retries
 * 429/5xx twice for read tools only. One child span `http.client.request` per call.
 */
export async function callRest(mapping: RestMapping, args: Record<string, unknown>, ctx: RestContext): Promise<RestResult> {
  const sent = await ctx.credentials();
  const { url, init } = buildRequest(ctx.baseUrl, mapping, args, sent);
  const fetchImpl = ctx.fetchImpl ?? fetch;
  return tracer.startActiveSpan(
    "http.client.request",
    { kind: SpanKind.CLIENT, attributes: { "http.request.method": mapping.method, "url.template": mapping.pathTemplate, "server.address": url.hostname } },
    async (span) => {
      try {
        for (let attempt = 0; ; attempt++) {
          const res = await fetchImpl(url, { ...init, redirect: "error", signal: AbortSignal.timeout(mapping.timeoutMs) });
          span.setAttribute("http.response.status_code", res.status);
          const retryable = res.status === 429 || res.status >= 500;
          if (retryable && ctx.readOnly && attempt < RETRIES) {
            await res.body?.cancel().catch(() => undefined);
            await new Promise((r) => setTimeout(r, 200 * 2 ** attempt));
            continue;
          }
          if (res.status >= 400) span.setStatus({ code: SpanStatusCode.ERROR });
          return { status: res.status, body: await readBody(res), sent };
        }
      } catch (err) {
        // A transport error can name the request URL — a query-parameter key with it. Neither
        // the span nor the caller ever sees the raw message.
        const e = err instanceof Error ? err : new Error(String(err));
        const safe = new Error(scrubCredentials(e.message, sent));
        safe.name = e.name;
        span.recordException(safe);
        span.setStatus({ code: SpanStatusCode.ERROR });
        throw safe;
      } finally {
        span.end();
      }
    },
  );
}
