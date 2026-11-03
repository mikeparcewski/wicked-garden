/* ============================================================================
   Fit guard for section snapping (site-local; site.css turns the chrome's
   html{scroll-snap-type: y proximity} off, so the page scrolls freely unless
   this guard locks it).
   html.snap-lock turns on `y mandatory` with `scroll-snap-stop: always` on every
   section ONLY when all of these hold:
   - the viewport is at least 1024x640,
   - prefers-reduced-motion is not set,
   - every section's content fits its frame. At >= 1024px every section snaps at
     y = 0 and is one viewport tall: the fixed bar sits over the section's own top
     padding, so the strip behind the bar is never the previous section.
   Mandatory with an overflowing section would make its lower part unreachable, so
   if any section grows past its frame (a long font fallback, a zoom level) the
   whole page drops back to free scrolling (proximity is no fallback: it pulls
   every small wheel step back to the section top). It re-checks on resize, after the fonts
   load, and whenever a section changes size.
   While locked, the wheel is driven here: every vertical wheel event is taken
   over, its deltas are summed, and once a burst has moved 40px one section is
   stepped; the rest of that burst (a trackpad's or a smooth wheel's momentum
   tail) is ignored until the wheel has been quiet for 180ms (and at least
   300ms since the step), unless a single wheel notch (50px or more after a
   90ms pause) arrives sooner. A new burst while the page is still gliding steps on
   from where the glide is going, so quick notches each move one more section.
   Native mandatory snapping pulled small high-resolution deltas back to the
   section top, so they could never leave the hero.
============================================================================ */

const MIN_W = 1024;
const MIN_H = 640;
/** the least time between two steps (ms); a burst's tail is held off by its quiet gap, not by this */
const COOLDOWN = 300;

const root = document.documentElement;
const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");

function sections(): HTMLElement[] {
  return [...document.querySelectorAll<HTMLElement>("main > section")];
}

/** Every section fits its frame: one viewport (the bar sits over each section's own top padding). */
export function allFit(): { ok: boolean; worst: string | null } {
  const vh = window.innerHeight;
  for (const [i, s] of sections().entries()) {
    const h = s.getBoundingClientRect().height;
    if (h > vh + 1) return { ok: false, worst: s.id || `section ${i}` };
  }
  return { ok: true, worst: null };
}

function evaluate() {
  const big = window.innerWidth >= MIN_W && window.innerHeight >= MIN_H;
  const fit = big && !reduce.matches ? allFit() : { ok: false, worst: null };
  const lock = big && !reduce.matches && fit.ok;
  root.classList.toggle("snap-lock", lock);
  root.dataset.snap = lock ? "locked" : big && !reduce.matches ? `free${fit.worst ? `:${fit.worst}` : ""}` : "none";
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

/* ── one wheel burst = one section, while locked ─────────────────────────── */
function snapTops(): number[] {
  const max = root.scrollHeight - window.innerHeight;
  const els = [...sections(), ...document.querySelectorAll<HTMLElement>("footer")];
  const tops = els
    .filter((el) => getComputedStyle(el).scrollSnapAlign.split(" ")[0] !== "none")
    .map((el) => Math.round(Math.min(max, Math.max(0, el.getBoundingClientRect().top + window.scrollY))));
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

/** How far a burst must travel before it steps (px), and how long the wheel must rest to end a burst (ms). */
const STEP_AT = 40;
const ACC_RESET = 160;
const TAIL_QUIET = 180;
/** one event this big after this long a pause is a deliberate wheel notch, not a momentum tail */
const NOTCH = 50;
const NOTCH_GAP = 90;

let acc = 0;
let lastEvt = -Infinity;
let stepAt = -Infinity;
let latched = false;
let goal: number | null = null;

function px(e: WheelEvent): number {
  if (e.deltaMode === 1) return e.deltaY * 40; // lines
  if (e.deltaMode === 2) return e.deltaY * window.innerHeight; // pages
  return e.deltaY;
}

function step(dir: number) {
  const tops = snapTops();
  // still gliding to the last step's stop: step on from there, not from wherever the glide is now
  const gliding = goal !== null && Math.abs(window.scrollY - goal) > 2 && performance.now() - stepAt < 1200;
  const y = gliding && goal !== null ? goal : window.scrollY;
  const target = dir > 0 ? tops.find((t) => t > y + 6) : [...tops].reverse().find((t) => t < y - 6);
  if (target === undefined) return;
  goal = target;
  window.scrollTo({ top: target, behavior: "smooth" });
}

function onWheel(e: WheelEvent) {
  if (!root.classList.contains("snap-lock") || e.ctrlKey || e.defaultPrevented) return;
  if (Math.abs(e.deltaY) <= Math.abs(e.deltaX)) return;
  if (canScrollInside(e.target, e.deltaY)) return;
  e.preventDefault();
  const now = performance.now();
  const quiet = now - lastEvt;
  lastEvt = now;
  if (latched) {
    // a wheel notch (one big delta after a pause) is a new step even soon after the last one;
    // anything else is still the burst that stepped (its momentum tail) until the wheel rests
    const notch = Math.abs(px(e)) >= NOTCH && quiet >= NOTCH_GAP;
    if (!notch && (quiet < TAIL_QUIET || now - stepAt < COOLDOWN)) return;
    latched = false;
    acc = 0;
  }
  if (quiet > ACC_RESET) acc = 0;
  acc += px(e);
  if (Math.abs(acc) < STEP_AT) return;
  const dir = acc > 0 ? 1 : -1;
  acc = 0;
  latched = true;
  step(dir);
  stepAt = now;
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
