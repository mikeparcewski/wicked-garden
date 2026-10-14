// The demo video's colours come from the operator's studio skin by default (operator, 2026-10-14: "the video
// color scheme should take the lead from the wicked skin"). wicked-crew resolves the skin into a palette at
// GET /api/v1/appearance/video-palette; inside a governed unit WICKED_CREW_URL names that daemon. With no daemon,
// an error, a slow or malformed answer, the stage uses the NEUTRAL palette (greys and a slate accent, no brand
// colour). A storyline's own `brand.accent` still overrides the accent.

/** The neutral look: the stage's light greys with a slate accent. */
export const NEUTRAL_PALETTE = Object.freeze({
  canvas: "#f3f3f5", surface: "#ffffff", ink: "#0b0b0c", ink2: "#2b2b30", muted: "#62626b", line: "#e4e4e8",
  accent: "#3f4a5a", font: "Inter", scheme: "light",
});

const HEX = /^#[0-9a-f]{6}$/i;
const KEYS = ["canvas", "surface", "ink", "ink2", "muted", "line", "accent"];

/** A palette as crew sends it, checked (every colour `#rrggbb`, a plain font name), or null. */
export function checkedPalette(raw) {
  if (raw === null || typeof raw !== "object" || !KEYS.every((k) => typeof raw[k] === "string" && HEX.test(raw[k]))) return null;
  const font = typeof raw.font === "string" && /^[A-Za-z0-9 -]{1,40}$/.test(raw.font) ? raw.font : "Inter";
  return { ...Object.fromEntries(KEYS.map((k) => [k, raw[k].toLowerCase()])), font, scheme: raw.scheme === "dark" ? "dark" : "light" };
}

/** `{ palette, source }` for one recording: crew's ("studio-skin" / "studio-default") or "fallback". */
export async function fetchVideoPalette({ env = process.env, fetchImpl = globalThis.fetch, timeoutMs = 1500 } = {}) {
  const base = String(env.WICKED_CREW_URL || env.WICKED_CREW_API || "").trim().replace(/\/+$/, "");
  if (!base || typeof fetchImpl !== "function") return { palette: NEUTRAL_PALETTE, source: "fallback" };
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), timeoutMs);
  try {
    const r = await fetchImpl(`${base}/api/v1/appearance/video-palette`, { signal: ctl.signal });
    const body = r.ok ? await r.json() : null;
    const palette = checkedPalette(body?.palette);
    return palette ? { palette, source: body.source === "studio-default" ? "studio-default" : "studio-skin" } : { palette: NEUTRAL_PALETTE, source: "fallback" };
  } catch {
    return { palette: NEUTRAL_PALETTE, source: "fallback" };
  } finally {
    clearTimeout(timer);
  }
}
