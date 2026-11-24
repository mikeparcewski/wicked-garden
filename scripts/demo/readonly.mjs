// Part of the wicked-garden-demo skill: the recorder's write guard.
//
// A demo recording must never do work on an app someone else uses: no run launched, no gate approved, no
// record created or deleted as a by-product of making a video (wicked-crew#565). So while it records, the
// browser sends no writes — every request whose method is not GET, HEAD or OPTIONS is aborted, whatever its
// origin, and so is every WebSocket frame the page sends (what the server pushes still arrives, so a live
// view keeps updating). The segment then fails `side_effect_blocked`, naming each.
//
// The one door is the fixture origin: a disposable app you (or the walkthrough tool) started on a loopback
// port for this recording, named with `record.mjs --fixture-origin <origin>`. Writes and page WebSocket
// frames to exactly that origin (scheme, host and port) pass; everything else stays blocked and listed.
// With no fixture origin the recording is fully read-only. There is no environment switch.

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);
const LOOPBACK_HOST = /^(localhost|[a-z0-9-]+\.localhost|127(?:\.\d{1,3}){3}|\[::1\])$/i;

/**
 * The fixture origin a recording may write to, normalised to `scheme://host[:port]`; null when none is given.
 * Throws unless it is an http(s) URL on a loopback host: the door is for an app started on this machine.
 */
export function fixtureOrigin(url) {
  if (url === undefined || url === null || url === "") return null;
  let u;
  try {
    u = new URL(String(url));
  } catch {
    throw new Error(`the fixture origin must be a loopback http(s) origin, e.g. http://127.0.0.1:4310 (got ${url})`);
  }
  if (!/^https?:$/.test(u.protocol) || !LOOPBACK_HOST.test(u.hostname)) {
    throw new Error(`the fixture origin must be a loopback http(s) origin, e.g. http://127.0.0.1:4310 (got ${url})`);
  }
  return u.origin;
}

/** The http(s) origin of a URL (a ws:/wss: URL maps to http:/https:), or null when it has none. */
function originOf(url) {
  try {
    const u = new URL(String(url));
    if (u.protocol === "ws:") u.protocol = "http:";
    else if (u.protocol === "wss:") u.protocol = "https:";
    return /^https?:$/.test(u.protocol) ? u.origin : null;
  } catch {
    return null;
  }
}

/** Whether the guard aborts a request: a write-class method on http(s), unless it goes to the fixture origin. */
export function blocks(method, url, writableOrigin = null) {
  if (SAFE_METHODS.has(String(method).toUpperCase())) return false;
  if (!/^https?:/i.test(String(url))) return false;
  return !(writableOrigin && originOf(url) === writableOrigin);
}

/** Whether the guard drops a WebSocket frame the page sends on `wsUrl`: always, unless it goes to the fixture origin. */
export function blocksFrame(wsUrl, writableOrigin = null) {
  return !(writableOrigin && originOf(wsUrl) === writableOrigin);
}

/**
 * Arm the guard on a Playwright browser context; returns the list it appends every blocked request to.
 * `writableOrigin` is the value fixtureOrigin() returned (null = fully read-only).
 */
export async function armGuard(context, { writableOrigin = null } = {}) {
  const blocked = [];
  await context.route("**/*", (route) => {
    const req = route.request();
    if (blocks(req.method(), req.url(), writableOrigin)) {
      blocked.push(`${req.method()} ${req.url()}`);
      return route.abort("blockedbyclient");
    }
    return route.fallback();
  });
  // An app can launch or approve over a WebSocket as well as over HTTP: fail closed on the page's frames.
  if (typeof context.routeWebSocket !== "function") {
    throw new Error("the recorder's write guard needs Playwright 1.48 or newer (BrowserContext.routeWebSocket)");
  }
  await context.routeWebSocket(/.*/, (ws) => {
    ws.connectToServer();
    // Without a page-side handler, the page's frames are forwarded to the server (the fixture's socket).
    if (!blocksFrame(ws.url(), writableOrigin)) return;
    // With a page-side handler set, the page's frames are no longer forwarded; the server's still are.
    ws.onMessage(() => {
      blocked.push(`WS send ${ws.url()}`);
    });
  });
  return blocked;
}

/** The typed failure a segment ends with when the guard blocked anything. */
export function sideEffectError(segmentKey, blocked) {
  const list = blocked.slice(0, 5).join("; ") + (blocked.length > 5 ? `; and ${blocked.length - 5} more` : "");
  const err = new Error(
    `side_effect_blocked: segment ${segmentKey} tried to write to the app (${list}). The recorder sends no writes: ` +
      `show the control without pressing it, or record against a disposable app you started on a loopback port ` +
      `and name it with --fixture-origin <origin>.`,
  );
  err.code = "side_effect_blocked";
  return err;
}

// ---- the engine-run recorder's request policy (DES-DEMO-RECORD-001 §3.4, wicked-core#1249) ---------------------
//
// The demo_record and demo_probe Tools run on the host, in the engine's jail, with ONE loopback port open: the app
// under demo, which may be the crew daemon itself (an Apps app at /apps/<id>). The jail stops every other port; this
// policy decides what the browser may do on that one:
//   - a document load of the frame the storyline drives (or any frame inside it) stays on the app origin, under the
//     launch path, whatever its method; the stage page itself never navigates; no popup or second page opens;
//   - the app's own requests: GET/HEAD on the app origin, OPTIONS for CORS preflights, and — on a crew app only —
//     the one POST crew classifies as a named read, the launched app's query (`/api/v1/apps/<id>/query`), which
//     must not redirect;
//   - a document's redirect chain is walked and every hop decided before the browser sees the first one;
//   - a WebSocket is decided BEFORE it connects: on a crew app exactly `/ws` (crew's event stream), else none; the
//     page's frames are dropped. Web workers are not allowed (their sockets would bypass the socket rule).
// Everything else is aborted and listed; the take fails `side_effect_blocked`. The policy never comes from the
// storyline: the engine hands in the origin, the launch path and the target crew named at launch.

const POLICY_SAFE = new Set(["GET", "HEAD", "OPTIONS"]);
const MAX_HOPS = 5;
/** A launch path as the engine hands it: a plain path, optionally with a query. */
export const LAUNCH_PATH_RE = /^\/[A-Za-z0-9._~%/?&=+-]*$/;

/**
 * A checked policy from the engine's values: `{appOrigin, launchPath, target: {kind: "crew_app", id, queryPath} |
 * {kind: "loopback_app"}}`. `launchUrl` is the exact path (and query) the person launched; `launchPath` is its
 * pathname without a trailing slash, the base every navigation must stay under.
 */
export function demoPolicy({ appOrigin, launchPath, target }) {
  const origin = fixtureOrigin(appOrigin); // loopback http(s) origin, normalised; throws otherwise
  if (!origin) throw new Error("the demo policy needs the app origin");
  const exact = String(launchPath || "/");
  if (!LAUNCH_PATH_RE.test(exact) || exact.startsWith("//")) throw new Error(`the launch path is not a plain path: ${exact}`);
  const pathname = new URL(exact, origin).pathname;
  const base = pathname.length > 1 ? pathname.replace(/\/+$/, "") || "/" : "/";
  let t = { kind: "loopback_app" };
  if (target && target.kind === "crew_app") {
    const id = String(target.id ?? "");
    if (!/^[A-Za-z0-9._-]{1,128}$/.test(id)) throw new Error(`the crew app id is not a plain name: ${id}`);
    const queryPath = `/api/v1/apps/${id}/query`;
    if (target.queryPath !== undefined && target.queryPath !== queryPath) throw new Error(`the query path must be ${queryPath}`);
    t = { kind: "crew_app", id, queryPath };
  } else if (target && target.kind !== "loopback_app") {
    throw new Error(`unknown demo target kind: ${target.kind}`);
  }
  return Object.freeze({ appOrigin: origin, launchUrl: exact, launchPath: base, target: Object.freeze(t) });
}

/** Whether `pathname` is the policy's launch path or below it (segment boundary). */
export function underPath(pathname, base) {
  return base === "/" ? String(pathname).startsWith("/") : pathname === base || String(pathname).startsWith(base + "/");
}

/**
 * The decision for one request: `{allow, reason}`. `nav` is what the request loads: `"app"` = a document of the
 * frame the storyline drives (or a frame inside it), `"stage"` = the stage page's own frame, `null` = a subresource.
 */
export function decide(policy, { method, url, nav = null }) {
  const m = String(method).toUpperCase();
  let u;
  try { u = new URL(String(url)); } catch { return { allow: false, reason: "unparseable URL" }; }
  if (nav === "stage") return { allow: false, reason: "the stage page never navigates" };
  if (!/^https?:$/.test(u.protocol)) {
    // A document from data:, blob: or about: would replace the app with something it never served.
    if (nav === "app") return { allow: false, reason: `a ${u.protocol} document in the app frame` };
    // As a subresource they never leave the browser.
    return { allow: ["data:", "blob:"].includes(u.protocol), reason: `scheme ${u.protocol}` };
  }
  if (u.origin !== policy.appOrigin) return { allow: false, reason: "not the app's origin" };
  if (nav === "app") {
    if (!underPath(u.pathname, policy.launchPath)) return { allow: false, reason: `the app frame left ${policy.launchPath}` };
    return m === "GET" || m === "HEAD" ? { allow: true, reason: "a page of the app" } : { allow: false, reason: "a form that writes" };
  }
  if (POLICY_SAFE.has(m)) return { allow: true, reason: "read" };
  if (m === "POST" && policy.target.kind === "crew_app" && u.pathname === policy.target.queryPath && !u.search) {
    return { allow: true, reason: "the launched app's query (a named read)" };
  }
  return { allow: false, reason: "a write" };
}

/** Whether a WebSocket may connect: on a crew app exactly the app origin's `/ws`, else never. */
export function wsAllowed(policy, wsUrl) {
  if (policy.target.kind !== "crew_app") return false;
  try {
    const u = new URL(String(wsUrl));
    const http = u.protocol === "ws:" ? "http:" : u.protocol === "wss:" ? "https:" : null;
    return http !== null && `${http}//${u.host}` === policy.appOrigin && u.pathname === "/ws" && !u.search;
  } catch {
    return false;
  }
}

/** Runs in every frame before the app's own scripts: no web workers (their sockets bypass routeWebSocket). */
export const NO_WORKERS_SCRIPT = `(() => {
  for (const k of ["Worker", "SharedWorker"]) {
    try { Object.defineProperty(globalThis, k, { value: undefined, configurable: false, writable: false }); } catch {}
  }
})();`;

/**
 * Arm the policy on a Playwright context. `navOf(frame)` says what a frame is: "app" (the frame the storyline drives
 * or one inside it), "stage" (the stage page's main frame) or null. Returns `{blocked, diagnostics}`: `blocked` fails
 * the take; `diagnostics` (refused sockets, dropped page frames) do not.
 */
export async function armPolicy(context, policy, { navOf = () => "app", onBlocked = () => {} } = {}) {
  const blocked = [];
  const push = blocked.push.bind(blocked);
  // Every refusal is also reported as it happens (the recorder notes WHEN, for the failure's moment in the video).
  blocked.push = (...items) => { onBlocked(); return push(...items); };
  const diagnostics = { ws_refused: [], ws_frames_dropped: 0 };
  await context.addInitScript({ content: NO_WORKERS_SCRIPT });
  // A worker that started anyway (a frame the init script missed) or a second page is a refusal, never ignored.
  context.on("page", (page) => {
    page.on("worker", (w) => blocked.push(`a web worker started (${w.url()}): workers are not allowed while recording`));
  });
  await context.route("**/*", async (route) => {
    const req = route.request();
    let nav = null;
    try { nav = req.isNavigationRequest() ? navOf(req.frame()) : null; } catch { /* a request with no frame */ }
    const d = decide(policy, { method: req.method(), url: req.url(), nav });
    if (!d.allow) {
      blocked.push(`${req.method()} ${req.url()} (${d.reason})`);
      return route.abort("blockedbyclient");
    }
    if (!/^https?:/i.test(req.url())) return route.fallback();
    const m = req.method().toUpperCase();
    if (nav === null && (m === "GET" || m === "HEAD" || m === "OPTIONS")) {
      // The app's own reads stream as usual (an event stream must not be buffered). A redirect off the app's port
      // meets the jail; a redirect on it is still a read of the app.
      return route.fallback();
    }
    // Documents and the query POST: Playwright routes only a request's FIRST url and the browser follows a redirect
    // without asking again, so the chain is walked here and every hop decided before the browser sees any of it.
    try {
      let url = req.url();
      for (let hop = 0; ; hop++) {
        const r = await route.fetch({ url, maxRedirects: 0 });
        const status = r.status();
        const location = r.headers()["location"];
        if (status < 300 || status >= 400 || !location) {
          // The query POST is answered with what was fetched (a read must not run twice). A document is let
          // through to the browser's own request instead: a document the route fulfilled has no network address
          // in Chromium's eyes, and its loopback requests (its socket) would then be refused as a public page's.
          // A checked redirect chain is followed by the browser the same way.
          return m === "POST" ? route.fulfill({ response: r }) : route.fallback();
        }
        if (m !== "GET" && m !== "HEAD") {
          blocked.push(`${m} ${url} (a redirected ${m}: the recorder follows none)`);
          return route.abort("blockedbyclient");
        }
        if (hop >= MAX_HOPS) {
          blocked.push(`${m} ${req.url()} (more than ${MAX_HOPS} redirects)`);
          return route.abort("blockedbyclient");
        }
        const next = new URL(location, url).href;
        const hd = decide(policy, { method: m, url: next, nav });
        if (!hd.allow) {
          blocked.push(`${m} ${next} (a redirect from ${url}: ${hd.reason})`);
          return route.abort("blockedbyclient");
        }
        url = next;
      }
    } catch {
      return route.abort("failed");
    }
  });
  if (typeof context.routeWebSocket !== "function") {
    throw Object.assign(new Error("the recorder's request policy needs Playwright 1.48 or newer (BrowserContext.routeWebSocket)"), { code: "recorder_deps_missing" });
  }
  await context.routeWebSocket(/.*/, (ws) => {
    if (!wsAllowed(policy, ws.url())) {
      diagnostics.ws_refused.push(ws.url());
      ws.close();
      return;
    }
    ws.connectToServer();
    // A page-side handler stops the page's frames from being forwarded; the server's still arrive.
    ws.onMessage(() => { diagnostics.ws_frames_dropped += 1; });
  });
  return { blocked, diagnostics };
}
