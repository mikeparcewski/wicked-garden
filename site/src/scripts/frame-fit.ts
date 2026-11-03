/* ============================================================================
   Frame fit (site-local). At >= 1024px wide every section is one viewport, and the
   demo stages that fill their frame (gate, graph, panel, memory) get the height the
   frame has left once the title, the lead, the foot and the gaps are laid out:
   measured, not guessed. A fixed budget per stage broke wherever the lead set
   taller than the budget assumed (the bigger lead type from 860px tall, a wider
   row gap from 900px), so at 1440x900 the gate and the graph outgrew their
   frames and the page lost its snap.
   Each stage's floor and cap stay in CSS (--fit-min / --fit-max on the stage),
   the result goes back as --fit-h, and the CSS falls back to its old clamp()
   without this script. The title and lead never depend on the stage height, so
   one pass settles it. A stage whose floor does not fit leaves its section taller
   than the window, and the snap guard (snap-guard.ts) then unlocks the page.
   Re-runs on resize, after the fonts load and whenever a frame changes size.
============================================================================ */

const TARGETS = [".sx--gate > .sx-stage", ".sx--graph > .sx-stage", ".sx--panel > .sx-stage", ".sx--memory .mq-stage"];
/** what each fitted frame keeps free under its foot (px): rounding, and a font that sets a line taller */
const SLACK = 6;
const MIN_W = 1024;

function stages(): HTMLElement[] {
  return TARGETS.flatMap((sel) => [...document.querySelectorAll<HTMLElement>(sel)]);
}

function px(v: string, fallback: number): number {
  const n = parseFloat(v);
  return Number.isFinite(n) ? n : fallback;
}

function fit() {
  const desk = window.innerWidth >= MIN_W;
  let changed = false;
  for (const el of stages()) {
    const sec = el.closest("section");
    const sx = el.closest<HTMLElement>(".sx");
    if (!desk || !sec || !sx) {
      if (el.style.getPropertyValue("--fit-h")) { el.style.removeProperty("--fit-h"); changed = true; }
      continue;
    }
    const cs = getComputedStyle(sec);
    const st = getComputedStyle(el);
    const min = px(st.getPropertyValue("--fit-min"), 0);
    const max = px(st.getPropertyValue("--fit-max"), Infinity);
    const frame = window.innerHeight - px(cs.paddingTop, 0) - px(cs.paddingBottom, 0);
    // offsetHeight: layout boxes, so an entrance transform (scale .98) never skews the measure
    const rest = sx.offsetHeight - el.offsetHeight;
    const h = Math.round(Math.max(min, Math.min(max, frame - rest - SLACK)));
    if (px(el.style.getPropertyValue("--fit-h"), -1) !== h) { el.style.setProperty("--fit-h", `${h}px`); changed = true; }
  }
  if (changed) window.dispatchEvent(new Event("gd:layout"));
}

let queued = false;
function schedule() {
  if (queued) return;
  queued = true;
  window.requestAnimationFrame(() => { queued = false; fit(); });
}

fit();
window.addEventListener("resize", schedule);
document.fonts?.ready.then(schedule);
window.addEventListener("load", schedule);
if (typeof ResizeObserver !== "undefined") {
  const ro = new ResizeObserver(schedule);
  document.querySelectorAll<HTMLElement>(".sx--gate, .sx--graph, .sx--panel, .sx--memory").forEach((el) => ro.observe(el));
}
