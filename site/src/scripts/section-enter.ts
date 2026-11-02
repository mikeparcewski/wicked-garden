/* ============================================================================
   Arrival entrances. Each section's stage (.sx-stage) waits, slightly lowered and
   scaled to .98, until the visitor arrives at it (its top crosses 85% of the
   viewport), then settles in after the title and lead (Reveal) have started.
   Only the first arrival plays. Under reduced motion, or without this script,
   nothing is ever hidden (the hiding rule needs html.js-enter, set here).
   The settled state is opacity 1 and transform none, so a stage that has entered
   creates no stacking context.
============================================================================ */

const root = document.documentElement;
const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");

if (!reduce.matches && typeof IntersectionObserver !== "undefined") {
  const stages = [...document.querySelectorAll<HTMLElement>("main > section:not(.gd-hero) .sx-stage")];
  const enter = (el: HTMLElement) => el.classList.add("is-entered");
  const near = (el: HTMLElement) => el.getBoundingClientRect().top < window.innerHeight * 0.85;
  // anything already on screen at load is shown at once, before the class can hide it
  stages.forEach((el) => { if (near(el)) el.classList.add("is-entered", "no-entrance"); });
  root.classList.add("js-enter");
  const io = new IntersectionObserver(
    (entries) => entries.forEach((e) => { if (e.isIntersecting) { enter(e.target as HTMLElement); io.unobserve(e.target); } }),
    { rootMargin: "0px 0px -15% 0px", threshold: 0 },
  );
  stages.forEach((el) => { if (!el.classList.contains("is-entered")) io.observe(el); });
  // belt and braces for a missed observation: on scroll, anything past the 85% mark enters
  let queued = 0;
  window.addEventListener("scroll", () => {
    window.cancelAnimationFrame(queued);
    queued = window.requestAnimationFrame(() => stages.forEach((el) => { if (!el.classList.contains("is-entered") && near(el)) enter(el); }));
  }, { passive: true });
  // the preference can change on an open page: show everything at once
  reduce.addEventListener?.("change", () => { if (reduce.matches) stages.forEach(enter); });
}
