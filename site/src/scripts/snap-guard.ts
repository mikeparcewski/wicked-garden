/* ============================================================================
   Fit guard for section snapping (site-local; the chrome's html{scroll-snap-type:
   y proximity} stays the base).
   html.snap-lock turns on `y mandatory` with `scroll-snap-stop: always` on every
   section ONLY when all of these hold:
   - the viewport is at least 1024x640,
   - prefers-reduced-motion is not set,
   - every section's content fits its frame (the hero fits the viewport; every
     other section fits the viewport minus the fixed topbar).
   Mandatory with an overflowing section would make its lower part unreachable, so
   if any section grows past its frame (a long font fallback, a zoom level) the
   whole page drops back to proximity. It re-checks on resize, after the fonts
   load, and whenever a section changes size.
   While locked, a discrete mouse-wheel notch steps exactly one section (trackpads
   and momentum scrolling are left to native snapping): proximity alone pulled slow
   notches back to the section top, so the wheel could never leave the hero.
============================================================================ */

const MIN_W = 1024;
const MIN_H = 640;
const COOLDOWN = 560;

const root = document.documentElement;
const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");

function topbarH(): number {
  const tb = document.querySelector(".topbar");
  return tb ? Math.ceil(tb.getBoundingClientRect().height) : 64;
}

function sections(): HTMLElement[] {
  return [...document.querySelectorAll<HTMLElement>("main > section")];
}

/** Every section fits its frame: the first (the hero) the viewport, the rest the viewport under the bar. */
export function allFit(): { ok: boolean; worst: string | null } {
  const vh = window.innerHeight;
  const frame = vh - topbarH();
  for (const [i, s] of sections().entries()) {
    const h = s.getBoundingClientRect().height;
    if (h > (i === 0 ? vh : frame) + 1) return { ok: false, worst: s.id || `section ${i}` };
  }
  return { ok: true, worst: null };
}

function evaluate() {
  const big = window.innerWidth >= MIN_W && window.innerHeight >= MIN_H;
  const fit = big && !reduce.matches ? allFit() : { ok: false, worst: null };
  const lock = big && !reduce.matches && fit.ok;
  root.classList.toggle("snap-lock", lock);
  root.dataset.snap = lock ? "locked" : big && !reduce.matches ? `proximity${fit.worst ? `:${fit.worst}` : ""}` : "none";
}

let queued = false;
function schedule() {
  if (queued) return;
  queued = true;
  window.requestAnimationFrame(() => {
    queued = false;
    evaluate();
  });
}

/* ── one wheel notch = one section, while locked ─────────────────────────── */
function snapTops(): number[] {
  const pad = topbarH();
  const max = root.scrollHeight - window.innerHeight;
  const els = [...sections(), ...document.querySelectorAll<HTMLElement>("footer")];
  const tops = els
    .filter((el) => getComputedStyle(el).scrollSnapAlign.split(" ")[0] !== "none")
    .map((el, i) => Math.round(Math.min(max, Math.max(0, el.getBoundingClientRect().top + window.scrollY - (i === 0 ? 0 : pad)))));
  return [...new Set(tops)].sort((a, b) => a - b);
}

function canScrollInside(target: EventTarget | null, dy: number): boolean {
  let el = target instanceof Element ? target : null;
  while (el && el !== document.body && el !== root) {
    const cs = getComputedStyle(el);
    if (/(auto|scroll)/.test(cs.overflowY) && el.scrollHeight > el.clientHeight + 1) {
      if (dy > 0 ? el.scrollTop + el.clientHeight < el.scrollHeight - 1 : el.scrollTop > 0) return true;
    }
    el = el.parentElement;
  }
  return false;
}

let last = -Infinity;
let busyUntil = -Infinity;
function onWheel(e: WheelEvent) {
  if (!root.classList.contains("snap-lock") || e.ctrlKey || e.defaultPrevented) return;
  const discrete = e.deltaMode !== 0 || Math.abs(e.deltaY) >= 50;
  if (!discrete || Math.abs(e.deltaY) <= Math.abs(e.deltaX)) return;
  if (canScrollInside(e.target, e.deltaY)) return;
  e.preventDefault();
  const now = performance.now();
  if (now < busyUntil || now - last < COOLDOWN) return;
  last = now;
  const tops = snapTops();
  const y = window.scrollY;
  const dir = e.deltaY > 0 ? 1 : -1;
  const target = dir > 0 ? tops.find((t) => t > y + 6) : [...tops].reverse().find((t) => t < y - 6);
  if (target === undefined) return;
  busyUntil = now + COOLDOWN;
  window.scrollTo({ top: target, behavior: "smooth" });
}

evaluate();
window.addEventListener("resize", schedule);
reduce.addEventListener?.("change", schedule);
document.fonts?.ready.then(schedule);
window.addEventListener("load", schedule);
window.addEventListener("gd:layout", schedule);
if (typeof ResizeObserver !== "undefined") {
  const ro = new ResizeObserver(schedule);
  sections().forEach((s) => ro.observe(s));
}
window.addEventListener("wheel", onWheel, { passive: false });
