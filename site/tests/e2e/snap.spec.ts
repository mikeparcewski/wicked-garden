import { test, expect } from '@playwright/test';

/**
 * The snap guard (src/scripts/snap-guard.ts): sections lock in (mandatory, one stop each) only where
 * every section fits its frame, the window is at least 1024x640 and motion is allowed; a wheel burst
 * then steps exactly one section. Anywhere else the page never traps content. Every section is one
 * viewport tall and snaps at y = 0 (the bar sits over its own top padding), so the strip behind the bar
 * at a stop is the section itself.
 */

/** The y of each section stop (its top: the bar sits over the section's own padding). */
async function sectionStops(page: import('@playwright/test').Page) {
  return page.evaluate(() => Array.from(document.querySelectorAll('main > section')).map((s) => Math.round(s.getBoundingClientRect().top + scrollY)));
}

// the three desktop sizes, plus laptop windows where a fixed stage budget used to overflow (the gate and the
// graph grew past 900-960px windows): those stages are now measured to fit (scripts/frame-fit.ts)
for (const vp of [{ width: 1440, height: 700 }, { width: 1280, height: 660 }, { width: 1920, height: 1080 },
  { width: 1440, height: 900 }, { width: 1536, height: 960 }]) {
  test(`every section fits its frame and the page locks in at ${vp.width}x${vp.height}`, async ({ page }) => {
    await page.setViewportSize(vp);
    await page.goto('/');
    await page.evaluate(async () => { await document.fonts.ready; });
    const fit = await page.evaluate(() =>
      Array.from(document.querySelectorAll('main > section')).map((s) => ({
        id: s.id, h: Math.ceil(s.getBoundingClientRect().height), frame: innerHeight,
      })));
    for (const s of fit) expect(s.h, `#${s.id} is ${s.h}px in a ${s.frame}px frame`).toBeLessThanOrEqual(s.frame);
    await expect(page.locator('html')).toHaveClass(/snap-lock/);
    expect(await page.evaluate(() => getComputedStyle(document.documentElement).scrollSnapType)).toBe('y mandatory');
  });
}

test('one wheel notch steps exactly one section, a flick ends on a section', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 700 });
  await page.goto('/');
  await expect(page.locator('html')).toHaveClass(/snap-lock/);
  const stops = await sectionStops(page);
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

// High-resolution and smooth-scroll wheels send many small deltas. Native mandatory snapping pulled each one
// back to the hero; the guard sums a burst and steps one section once it has moved 40px.
for (const burst of [{ n: 14, dy: 12 }, { n: 40, dy: 30 }, { n: 8, dy: 40 }, { n: 8, dy: 49 }, { n: 1, dy: 60 }]) {
  test(`a burst of ${burst.n} x ${burst.dy}px wheel events steps exactly one section`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 700 });
    await page.goto('/');
    await expect(page.locator('html')).toHaveClass(/snap-lock/);
    const stops = await sectionStops(page);
    await page.mouse.move(1300, 400);
    for (let k = 0; k < burst.n; k++) { await page.mouse.wheel(0, burst.dy); await page.waitForTimeout(16); }
    await expect.poll(() => page.evaluate(() => Math.round(scrollY)), { timeout: 4_000 }).toBe(stops[1]);
    await page.waitForTimeout(900);
    expect(await page.evaluate(() => Math.round(scrollY))).toBe(stops[1]);
  });
}

test('quick notches each step one more section, even while the page is still gliding', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 700 });
  await page.goto('/');
  await expect(page.locator('html')).toHaveClass(/snap-lock/);
  const stops = await sectionStops(page);
  await page.mouse.move(1300, 400);
  for (let k = 0; k < 3; k++) { await page.mouse.wheel(0, 100); await page.waitForTimeout(350); }
  await expect.poll(() => page.evaluate(() => Math.round(scrollY)), { timeout: 4_000 }).toBe(stops[3]);
});

test('at a stop the strip behind the bar is the section itself', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 700 });
  await page.goto('/');
  await expect(page.locator('html')).toHaveClass(/snap-lock/);
  const stops = await sectionStops(page);
  for (const k of [1, 2, 3]) {
    await page.evaluate((y) => window.scrollTo({ top: y, behavior: 'instant' as ScrollBehavior }), stops[k]);
    const under = await page.evaluate(() => {
      const tb = document.querySelector('.topbar')!.getBoundingClientRect().height;
      const at = document.elementsFromPoint(innerWidth / 2, tb / 2).find((e) => e.closest('main > section'));
      return at?.closest('main > section')?.id ?? null;
    });
    const id = await page.evaluate((k) => document.querySelectorAll('main > section')[k].id, k);
    expect(under, `behind the bar at stop ${k}`).toBe(id);
  }
});

test('no lock below 1024px wide or under 640px tall, and no snapping at all there', async ({ page }) => {
  await page.setViewportSize({ width: 1023, height: 800 });
  await page.goto('/');
  await expect(page.locator('html')).not.toHaveClass(/snap-lock/);
  expect(await page.evaluate(() => getComputedStyle(document.documentElement).scrollSnapType)).toBe('none');
  await page.setViewportSize({ width: 1280, height: 620 });
  await expect(page.locator('html')).not.toHaveClass(/snap-lock/);
  // the fallback is free scrolling: proximity would pull every small wheel step back to the section top
  expect(await page.evaluate(() => getComputedStyle(document.documentElement).scrollSnapType)).toBe('none');
  await page.mouse.move(640, 300);
  for (let k = 0; k < 14; k++) { await page.mouse.wheel(0, 12); await page.waitForTimeout(16); }
  await page.waitForTimeout(1200);
  expect(await page.evaluate(() => Math.round(scrollY))).toBeGreaterThan(100);
});

// Where nothing locks at >= 1024px (a short laptop under 640px tall; reduced motion) the page scrolls freely,
// and a Tab stop scrolled into view must land below the fixed bar, not under it.
for (const c of [{ width: 1366, height: 625, motion: 'no-preference' as const }, { width: 1440, height: 700, motion: 'reduce' as const },
  { width: 1280, height: 660, motion: 'reduce' as const }]) {
  test(`Tab never stops on a control under the bar at ${c.width}x${c.height} (${c.motion})`, async ({ page }) => {
    await page.emulateMedia({ reducedMotion: c.motion });
    await page.setViewportSize({ width: c.width, height: c.height });
    await page.goto('/');
    await page.evaluate(async () => { await document.fonts.ready; });
    await expect(page.locator('html')).not.toHaveClass(/snap-lock/);
    const under: string[] = [];
    let stops = 0;
    for (let i = 0; i < 120; i++) {
      await page.keyboard.press('Tab');
      // wait for the scroll the focus started (smooth where motion is allowed) to settle
      await page.evaluate(() => new Promise<void>((done) => {
        let last = scrollY, still = 0;
        const tick = () => { if (scrollY === last) still++; else { still = 0; last = scrollY; } if (still >= 4) done(); else requestAnimationFrame(tick); };
        requestAnimationFrame(tick);
      }));
      const r = await page.evaluate(() => {
        const el = document.activeElement as HTMLElement | null;
        if (!el || el === document.body) return { end: true };
        if (el.closest('.topbar')) return null;
        const bar = document.querySelector('.topbar')!.getBoundingClientRect().bottom;
        const b = el.getBoundingClientRect();
        if (!b.width || !b.height) return null;
        return { top: b.top, bar, name: `${el.tagName.toLowerCase()} "${(el.getAttribute('aria-label') || el.textContent || '').trim().slice(0, 32)}"` };
      });
      if (r && 'end' in r) break;
      if (!r) continue;
      stops++;
      if (r.top < r.bar - 0.5) under.push(`${r.name} top ${Math.round(r.top)} < bar ${Math.round(r.bar)}`);
    }
    expect(stops).toBeGreaterThan(40);
    expect(under).toEqual([]);
  });
}
