// Part of the wicked-garden-demo skill: the recorder's read-only guard.
//
// A demo recording must never do work on the app it films: no run launched, no gate approved, no
// record created or deleted as a by-product of making a video (wicked-crew#565). So while it records,
// the browser sends no writes — every request whose method is not GET, HEAD or OPTIONS is aborted,
// whatever its origin, and so is every WebSocket frame the page sends (what the server pushes still
// arrives, so a live view keeps updating). The segment then fails `side_effect_blocked`, naming each.
//
// DEMO_ALLOW_WRITES=1 lifts it, for a disposable target you started for the demo (a fixture server,
// a scratch database) — never for a live system someone else uses.

export const ALLOW_WRITES_ENV = "DEMO_ALLOW_WRITES";

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

/** Whether this recording may send writes: only an explicit DEMO_ALLOW_WRITES=1. */
export function writesAllowed(env = process.env) {
  return env[ALLOW_WRITES_ENV] === "1";
}

/** Whether the guard aborts a request: a write-class method on http(s), unless writes are allowed. */
export function blocks(method, url, allowWrites) {
  if (allowWrites) return false;
  if (SAFE_METHODS.has(String(method).toUpperCase())) return false;
  return /^https?:/i.test(String(url));
}

/** Arm the guard on a Playwright browser context; returns the list it appends every blocked request to. */
export async function armReadOnly(context, allowWrites = writesAllowed()) {
  const blocked = [];
  if (allowWrites) return blocked;
  await context.route("**/*", (route) => {
    const req = route.request();
    if (blocks(req.method(), req.url(), false)) {
      blocked.push(`${req.method()} ${req.url()}`);
      return route.abort("blockedbyclient");
    }
    return route.fallback();
  });
  // An app can launch or approve over a WebSocket as well as over HTTP: fail closed on the page's frames.
  if (typeof context.routeWebSocket !== "function") {
    throw new Error("the read-only recorder needs Playwright 1.48 or newer (BrowserContext.routeWebSocket)");
  }
  await context.routeWebSocket(/.*/, (ws) => {
    ws.connectToServer();
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
    `side_effect_blocked: segment ${segmentKey} tried to write to the app (${list}). The recorder is read-only: ` +
      `show the control without pressing it, or set ${ALLOW_WRITES_ENV}=1 only for a disposable target you started.`,
  );
  err.code = "side_effect_blocked";
  return err;
}
