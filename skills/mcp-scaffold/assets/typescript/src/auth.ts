// SPDX-License-Identifier: MIT
// SPDX-FileCopyrightText: __YEAR__ the __SERVER_NAME__ authors
import { timingSafeEqual } from "node:crypto";
import type { IncomingMessage } from "node:http";
import { secretVar, type ServerConfig } from "./config.js";
import type { Credentials } from "./rest.js";

/** The authenticated MCP client of an httpStream session. */
export type Session = { principal: string };

/**
 * Read the ONE secret this server holds: `<SERVER>_TOKEN` — the bearer token, API key, basic
 * password or OAuth2 client secret, as `auth.scheme` says. Missing → fail at startup naming
 * the VARIABLE, never a value.
 */
export function loadSecret(config: ServerConfig, env: NodeJS.ProcessEnv = process.env): string {
  const name = secretVar(config.key);
  const value = env[name];
  if (!value) {
    throw new Error(`${name} is not set: export the ${config.auth.scheme} secret for ${config.key} as ${name}`);
  }
  return value;
}

type FetchLike = typeof fetch;
let cached: { key: string; token: string; expiresAt: number } | undefined;

/**
 * Every credential the upstream API expects — header(s), or a query parameter for an api-key
 * with `auth.queryParam` — built from the secret plus the committed config. ONE carrier: the
 * request builder sends exactly these, and the error scrub removes exactly these.
 */
export async function upstreamCredentials(
  config: ServerConfig,
  secret: string,
  fetchImpl: FetchLike = fetch,
): Promise<Credentials> {
  const { auth } = config;
  const header = (value: string): Credentials => ({ headers: { [auth.header]: value }, query: {} });
  switch (auth.scheme) {
    case "bearer":
      return header(`Bearer ${secret}`);
    case "api-key":
      return auth.queryParam !== null ? { headers: {}, query: { [auth.queryParam]: secret } } : header(secret);
    case "basic":
      return header(`Basic ${Buffer.from(`${auth.user}:${secret}`).toString("base64")}`);
    case "oauth2-client-credentials": {
      const key = `${auth.tokenUrl} ${auth.clientId} ${auth.scopes.join(" ")}`;
      if (!cached || cached.key !== key || cached.expiresAt <= Date.now()) {
        cached = { key, ...(await exchange(config, secret, fetchImpl)) };
      }
      return header(`Bearer ${cached.token}`);
    }
  }
}

async function exchange(config: ServerConfig, secret: string, fetchImpl: FetchLike) {
  const { tokenUrl, clientId, scopes } = config.auth;
  const form = new URLSearchParams({ grant_type: "client_credentials", client_id: clientId ?? "", client_secret: secret });
  if (scopes.length > 0) form.set("scope", scopes.join(" "));
  const res = await fetchImpl(tokenUrl ?? "", {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded", accept: "application/json" },
    body: form,
    redirect: "error",
    signal: AbortSignal.timeout(10_000),
  });
  if (!res.ok) throw new Error(`the token endpoint answered HTTP ${res.status}`);
  const body = (await res.json()) as { access_token?: string; expires_in?: number };
  if (!body.access_token) throw new Error("the token endpoint answered no access_token");
  // Refresh 30 s early.
  const ttl = Math.max(0, (body.expires_in ?? 300) - 30) * 1000;
  return { token: body.access_token, expiresAt: Date.now() + ttl };
}

/** Forget a cached OAuth2 access token (tests, or after the upstream answers 401). */
export function resetTokenCache(): void {
  cached = undefined;
}

let stdioTrusted = false;

/** stdio: the parent process that spawned the server is the client (the process boundary authenticates). */
export function configureAuth(config: ServerConfig): void {
  stdioTrusted = config.transport === "stdio";
}

/** httpStream: every request must carry `Authorization: Bearer <MCP_SERVER_BEARER>`. */
export async function authenticate(request: IncomingMessage): Promise<Session> {
  const expected = process.env.MCP_SERVER_BEARER ?? "";
  const header = request.headers.authorization ?? "";
  const presented = header.startsWith("Bearer ") ? header.slice("Bearer ".length) : "";
  const a = Buffer.from(presented);
  const b = Buffer.from(expected);
  if (expected === "" || a.length !== b.length || !timingSafeEqual(a, b)) {
    throw new Response(null, { status: 401, statusText: "Unauthorized" });
  }
  return { principal: "bearer" };
}

/** `canAccess` for every tool and resource: an authenticated session (or the trusted stdio parent). */
export function requireSession(session: Session | undefined): boolean {
  return stdioTrusted || (session !== undefined && typeof session.principal === "string");
}
