/* ============================================================================
   The story spine: one claim followed down the page. The hero's agent claims
   "build: all acceptance tests pass"; each section shows another way garden checks
   it. A small decorative token (aria-hidden) in the left gutter updates its status
   line as each section comes into frame: the most visible section's data-token
   names the step ("off" hides it). The labels are illustrative, like the demos.
   Hidden below 1024px wide; under reduced motion its changes are not animated (CSS).
============================================================================ */

const token = document.querySelector<HTMLElement>(".st-token");
if (token && typeof IntersectionObserver !== "undefined") {
  const all = [...document.querySelectorAll<HTMLElement>("main > section")];
  const seen = new Map<Element, number>();
  const io = new IntersectionObserver(
    (entries) => {
      for (const e of entries) {
        const frame = Math.max(1, Math.min(e.boundingClientRect.height, window.innerHeight));
        seen.set(e.target, e.isIntersecting ? e.intersectionRect.height / frame : 0);
      }
      let best: HTMLElement | null = null;
      let ratio = 0;
      for (const s of all) {
        const r = seen.get(s) ?? 0;
        if (r > ratio) { ratio = r; best = s; }
      }
      token.dataset.step = best && ratio > 0.45 ? best.dataset.token || "off" : "off";
    },
    { threshold: [0, 0.25, 0.45, 0.6, 0.8, 1] },
  );
  all.forEach((s) => io.observe(s));
}
