/**
 * src/wire-capture.mjs — wireCapture: fetch/XHR/WebSocket/console capture
 * (TH-4 item 2, the idiom the 2026-08 campaign proved — s1.js:16-34).
 *
 * Attaches page listeners ONCE per run:
 *  - every declared wire capture (`spec.capture.wire[]`) records matching
 *    responses (url, status, headers when asked, JSON/text body when asked)
 *  - websocket connections + the first received frame (bounded)
 *  - the console-message ledger — ALWAYS on, non-configurable (TH-4 item 3)
 *  - pageerror exceptions land in the ledger as type "pageerror"
 *
 * Captured values are RAW here — assertions must evaluate against real
 * content. Redaction happens exactly once, in the evidence writer, before
 * anything is persisted (TH-19).
 */

const MAX_BODY_BYTES = 64 * 1024;
const MAX_CONSOLE_ENTRY = 500;
const MAX_FRAME = 500;

function matches(url, match) {
  if (match.url_suffix !== undefined) return url.endsWith(match.url_suffix);
  if (match.url_contains !== undefined) return url.includes(match.url_contains);
  if (match.url_matches !== undefined) return new RegExp(match.url_matches).test(url);
  return false;
}

/**
 * @param {import('playwright').Page} page
 * @param {object} spec parsed + linted spec
 * @returns captures — a live object the runner keeps appending to
 */
export function wireCapture(page, spec) {
  const captures = {
    wire: {},          // capture id -> { responses: [...] }
    websockets: [],    // { url, opened_at }
    wsFirstFrame: undefined,
    readbacks: {},     // readBack step id -> record (filled by the runner)
    console: [],       // { type, text, at, location? }
  };
  const wireDefs = spec.capture?.wire ?? [];
  for (const def of wireDefs) captures.wire[def.id] = { responses: [] };

  page.on("response", async (r) => {
    const url = r.url();
    for (const def of wireDefs) {
      if (!matches(url, def.match ?? def)) continue;
      const entry = { url, status: r.status(), at: new Date().toISOString() };
      if (def.headers) {
        try { entry.headers = await r.allHeaders(); } catch { entry.headers = null; }
      }
      if (def.body !== false) {
        try {
          const text = (await r.text()).slice(0, MAX_BODY_BYTES);
          try { entry.body = JSON.parse(text); } catch { entry.body = text; }
        } catch { entry.body = null; }
      }
      captures.wire[def.id].responses.push(entry);
    }
  });

  if (spec.capture?.websocket !== false) {
    page.on("websocket", (ws) => {
      captures.websockets.push({ url: ws.url(), opened_at: new Date().toISOString() });
      ws.on("framereceived", (f) => {
        if (captures.wsFirstFrame === undefined) {
          captures.wsFirstFrame = String(f.payload).slice(0, MAX_FRAME);
        }
      });
    });
  }

  // Console ledger: ALWAYS on. Every message type, not just errors — a
  // warning ledger is how selector drift and deprecations get caught early.
  page.on("console", (m) => {
    captures.console.push({
      type: m.type(),
      text: m.text().slice(0, MAX_CONSOLE_ENTRY),
      at: new Date().toISOString(),
    });
  });
  page.on("pageerror", (e) => {
    captures.console.push({
      type: "pageerror",
      text: String(e?.message ?? e).slice(0, MAX_CONSOLE_ENTRY),
      at: new Date().toISOString(),
    });
  });

  return captures;
}
