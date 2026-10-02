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
