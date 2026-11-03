import { test, expect } from '@playwright/test';

/**
 * Mobile smoke at iPhone 12 dimensions (390x844). The viewport is set
 * explicitly instead of spreading devices['iPhone 12'] because that device
 * descriptor carries defaultBrowserType: 'webkit', which would silently move
 * the test off the cached Chromium build.
 */
test.use({
  viewport: { width: 390, height: 844 },
  isMobile: true,
  hasTouch: true,
});

test('mobile: page renders, hero island visible, hamburger menu opens', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('h1')).toContainText('The tools your coding agent');

  // The hero island has no mobile fallback — the grid collapses to one column
  // and the HeroStamp card renders below the pitch (site.css @max-width:1000px).
  const card = page.locator('.hs-card');
  await card.scrollIntoViewIfNeeded();
  await expect(card).toBeVisible();
  await expect(card.locator('.hs-claim')).not.toBeEmpty();

  // The qe wall stands up on a phone: writer and executor stacked, the lanes drop through a
  // horizontal wall, then the reviewer.
  const qe = page.locator('#qe');
  await qe.scrollIntoViewIfNeeded();
  await expect(qe.locator('.qw-role')).toHaveCount(3);
  await expect(qe.locator('.qw-wall')).toBeVisible();
  await expect(qe.locator('.qw-track')).toBeVisible();
  const [exe, wall, rev] = await Promise.all(['[data-role="executor"]', '.qw-wall', '[data-role="reviewer"]'].map((s) =>
    qe.locator(s).evaluate((el) => el.getBoundingClientRect().top)));
  expect(exe).toBeLessThan(wall);
  expect(wall).toBeLessThan(rev);

  // The catalog's domains scroll sideways in their own row (never a squashed 4-column grid).
  const tabs = page.locator('#toolkit .cx-tabs');
  expect(await tabs.evaluate((el) => getComputedStyle(el).display)).toBe('flex');
  expect(await tabs.evaluate((el) => el.scrollWidth > el.clientWidth)).toBe(true);

  // Nothing in main is cut by the viewport edge, outside its own scroller.
  const clipped = await page.evaluate(() => {
    const out: string[] = [];
    for (const el of Array.from(document.querySelectorAll('main *'))) {
      const r = el.getBoundingClientRect();
      if (!r.width || (r.right <= innerWidth + 1 && r.left >= -1)) continue;
      // only a container the visitor can scroll excuses it; a hidden or clip box would just cut it off
      let p = el.parentElement, inScroller = false;
      while (p && p !== document.body) { if (/(auto|scroll)/.test(getComputedStyle(p).overflowX) && p.scrollWidth > p.clientWidth && p.getBoundingClientRect().right <= innerWidth + 1) { inScroller = true; break; } p = p.parentElement; }
      if (!inScroller) out.push(`${el.tagName}.${String((el as HTMLElement).className).split(' ')[0]}`);
    }
    return out;
  });
  expect(clipped).toEqual([]);

  // No horizontal overflow — the page must not scroll sideways on a phone.
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);

  // Mobile chrome: inline nav collapses behind the hamburger; menu opens.
  const menuBtn = page.locator('#menuBtn');
  await expect(menuBtn).toBeVisible();
  await menuBtn.click();
  await expect(page.locator('#mobileMenu')).toBeVisible();
  await expect(page.locator('#mobileMenu').getByRole('link', { name: /garden/ })).toBeVisible();
});

for (const vp of [{ width: 390, height: 844 }, { width: 360, height: 740 }]) {
  test(`mobile ${vp.width}x${vp.height}: every control, chrome included, is a 44px target`, async ({ page }) => {
    await page.setViewportSize(vp);
    await page.goto('/');
    await page.evaluate(async () => { await document.fonts.ready; });
    const measure = () => page.evaluate(() => {
      const out: string[] = [];
      for (const el of Array.from(document.querySelectorAll<HTMLElement>('a[href], button, [role=tab], [role=switch], input'))) {
        const cs = getComputedStyle(el);
        // layout size (an entrance transform scales a stage to .98 until it is reached)
        if (!el.offsetWidth || !el.offsetHeight || cs.visibility === 'hidden' || el.closest('[hidden], [inert], .mobile-menu')) continue;
        // a link inside a sentence is exempt (WCAG 2.5.8): an inline element in a longer run of text
        const p = el.parentElement;
        const inline = cs.display === 'inline' && !!p && p.textContent!.trim().length > el.textContent!.trim().length + 12;
        if (!inline && (el.offsetWidth < 44 || el.offsetHeight < 44)) {
          out.push(`${el.tagName.toLowerCase()}.${String(el.className).split(' ')[0]} "${(el.getAttribute('aria-label') || el.textContent || '').trim().slice(0, 30)}" ${el.offsetWidth}x${el.offsetHeight}`);
        }
      }
      return out;
    });
    expect(await measure()).toEqual([]);
    // and with the gate's "where it only advises" detail open (its close button is a target too)
    const where = page.locator('#gate .pg-where-btn');
    await where.scrollIntoViewIfNeeded();
    await where.click();
    await expect(page.locator('#gate .pg-advise')).toBeVisible();
    expect(await measure()).toEqual([]);
  });
}
