import { test, expect } from '@playwright/test';

/**
 * The shared "wicked platform" band (wicked-web SameGarden) has to fit the screen it is on.
 *
 * It is a scroll-snap target. Under `scroll-snap-type: y mandatory` — which this site used to set,
 * overriding the chrome's `y proximity` — the browser will not rest between snap points, so a band
 * taller than the viewport has its lower half made unreachable: you cannot wheel to the bottom
 * plane at all. It was 1124px against a 1440x700 window, 424px past the fold.
 *
 * The chrome fixed the height in two passes (wicked-web #28, then #29 for short viewports), but a
 * site only picks that up when it re-pins the `wicked-web` commit in package.json AND
 * package-lock.json. This spec is what catches a stale pin: it fails against the old chrome and
 * passes against the current one, so a forgotten re-pin cannot go unnoticed.
 *
 * 1280x660 is the one that matters — a 13" laptop. Testing only at 1440x900 hides this entirely.
 */
const VIEWPORTS = [
  { width: 1440, height: 760 },
  { width: 1440, height: 700 },
  { width: 1280, height: 660 },
];

for (const vp of VIEWPORTS) {
  test(`the platform band fits ${vp.width}x${vp.height}`, async ({ page }) => {
    await page.setViewportSize(vp);
    await page.goto('/');
    // Measure only once webfonts have settled. Before they swap, text is laid out in the
    // fallback face and the band can measure SHORTER than it finally renders -- which would pass
    // this test on a page that does not actually fit. It did not reproduce locally (delta 0),
    // but it is a race, and a size check that can silently pass early is worse than no check.
    await page.evaluate(() => document.fonts.ready);

    const band = page.locator('.same-garden');
    await expect(band).toHaveCount(1);

    // The topbar is position:fixed and overlays the page, so the height a section actually gets
    // is the viewport minus the bar. Measure it rather than hardcoding the token value -- and
    // fail loudly if it cannot be found. Falling back to 0 would make `usable` the whole
    // viewport, quietly LOOSENING this assertion by 64px on a markup change in wicked-web.
    const barH = await page.evaluate(() => {
      const bar =
        document.getElementById('themeBtn')?.closest('header, .topbar') ??
        document.querySelector('.topbar, header[class*="topbar"]');
      return bar ? Math.round(bar.getBoundingClientRect().height) : 0;
    });
    expect(barH, 'could not find the topbar to measure — selector has drifted').toBeGreaterThan(0);
    const usable = vp.height - barH;

    const h = await band.evaluate((el) => Math.round(el.getBoundingClientRect().height));

    expect(
      h,
      `.same-garden is ${h}px in ${usable}px of usable height at ${vp.width}x${vp.height} — ` +
        `check that wicked-web is re-pinned in package.json AND package-lock.json`,
    ).toBeLessThanOrEqual(usable);
  });
}

test('a band that fits is still a snap target', async ({ page }) => {
  // The chrome turns snapping off only below the height the band can fit in. If it ever reports
  // `none` at a size where it fits, the threshold has drifted out of step with the band height —
  // which happened once already: the cut-off was left at 690px after the band shrank to 574px.
  await page.setViewportSize({ width: 1280, height: 660 });
  await page.goto('/');
  await page.evaluate(() => document.fonts.ready);
  const snap = await page.evaluate(
    () => getComputedStyle(document.querySelector('.same-garden')!).scrollSnapAlign.split(' ')[0],
  );
  expect(snap).toBe('start');
});
