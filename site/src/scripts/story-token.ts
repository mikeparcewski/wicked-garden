/* ============================================================================
   The story spine: one claim followed down the page. The hero's agent claims
   "build: all acceptance tests pass"; each section shows another way garden checks
   it. A small decorative token (aria-hidden) in the left gutter updates its status
   line for the section under the middle of the viewport below the topbar: that section's data-token
   names the step ("off" hides it). The labels are illustrative, like the demos.
   Hidden below 1024px wide; under reduced motion its changes are not animated (CSS).
============================================================================ */

const token = document.querySelector<HTMLElement>(".st-token");
if (token) {
  const sections = [...document.querySelectorAll<HTMLElement>("main > section")];
  let queued = false;
  const update = () => {
    queued = false;
    // the middle of the window under the topbar: the same line the beat track uses (beats.js), so the
    // token and the track always name the same section
    const bar = document.querySelector(".topbar")?.getBoundingClientRect().height ?? 64;
    const mid = bar + (window.innerHeight - bar) / 2;
    const at = sections.find((s) => {
      const r = s.getBoundingClientRect();
      return r.top <= mid && r.bottom > mid;
    });
    const step = at?.dataset.token || "off";
    if (token.dataset.step !== step) token.dataset.step = step;
  };
  const schedule = () => {
    if (queued) return;
    queued = true;
    window.requestAnimationFrame(update);
  };
  update();
  window.addEventListener("scroll", schedule, { passive: true });
  window.addEventListener("resize", schedule);
}
