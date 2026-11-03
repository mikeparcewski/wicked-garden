/** Move focus on a visitor's key press (a roving tab stop) without jumping the page: focus with
 *  preventScroll, then bring the control into view only when it is off screen or under the fixed
 *  topbar (on a phone some of these rows stack and run past the window's edge). Only ever called from
 *  key handlers: nothing on a timer focuses or scrolls. */
export function focusFromKey(el: HTMLElement | null | undefined): void {
  if (!el) return;
  el.focus({ preventScroll: true });
  const r = el.getBoundingClientRect();
  const bar = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--topbar-h")) || 64;
  if (r.top < bar || r.bottom > window.innerHeight) el.scrollIntoView({ block: "nearest" });
}
