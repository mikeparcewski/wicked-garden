import { test, expect } from '@playwright/test';

/**
 * The snap guard (src/scripts/snap-guard.ts): sections lock in (mandatory, one stop each) only where
 * every section fits its frame, the window is at least 1024x640 and motion is allowed; a wheel notch
 * then steps exactly one section. Anywhere else the page never traps content.
 */

for (const vp of [{ width: 1440, height: 700 }, { width: 1280, height: 660 }, { width: 1920, height: 1080 }]) {
  test(`every section fits its frame and the page locks in at ${vp.width}x${vp.height}`, async ({ page }) => {
    await page.setViewportSize(vp);
    await page.goto('/');
    await page.evaluate(async () => { await document.fonts.ready; });
    const fit = await page.evaluate(() => {
      const tb = document.querySelector('.topbar')!.getBoundingClientRect().height;
      return Array.from(document.querySelectorAll('main > section')).map((s, i) => ({
        id: s.id, h: Math.ceil(s.getBoundingClientRect().height), frame: i === 0 ? innerHeight : innerHeight - tb,
      }));
    });
    for (const s of fit) expect(s.h, `#${s.id} is ${s.h}px in a ${s.frame}px frame`).toBeLessThanOrEqual(s.frame);
    await expect(page.locator('html')).toHaveClass(/snap-lock/);
    expect(await page.evaluate(() => getComputedStyle(document.documentElement).scrollSnapType)).toBe('y mandatory');
  });
}

test('one wheel notch steps exactly one section, a flick ends on a section', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 700 });
  await page.goto('/');
  await expect(page.locator('html')).toHaveClass(/snap-lock/);
  const stops = await page.evaluate(() => {
    const tb = document.querySelector('.topbar')!.getBoundingClientRect().height;
    return Array.from(document.querySelectorAll('main > section')).map((s, i) => Math.round(s.getBoundingClientRect().top + scrollY - (i ? tb : 0)));
  });
  await page.mouse.move(1300, 400);
  for (let k = 1; k <= 3; k++) {
    await page.mouse.wheel(0, 100);
    await expect.poll(() => page.evaluate(() => Math.round(scrollY)), { timeout: 4_000 }).toBe(stops[k]);
  }
  for (let k = 0; k < 6; k++) { await page.mouse.wheel(0, 120); await page.waitForTimeout(50); }
  await page.waitForTimeout(1500);
  const y = await page.evaluate(() => Math.round(scrollY));
  expect(stops.some((s) => Math.abs(s - y) <= 2), `rested at ${y}, stops ${stops.join(',')}`).toBe(true);
});

test('no lock below 1024px wide or under 640px tall', async ({ page }) => {
  await page.setViewportSize({ width: 1023, height: 800 });
  await page.goto('/');
  await expect(page.locator('html')).not.toHaveClass(/snap-lock/);
  expect(await page.evaluate(() => getComputedStyle(document.documentElement).scrollSnapType)).toBe('none');
  await page.setViewportSize({ width: 1280, height: 620 });
  await expect(page.locator('html')).not.toHaveClass(/snap-lock/);
});
