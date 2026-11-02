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
      let p = el.parentElement, inScroller = false;
      while (p && p !== document.body) { if (/(auto|scroll|hidden|clip)/.test(getComputedStyle(p).overflowX) && p.getBoundingClientRect().right <= innerWidth + 1) { inScroller = true; break; } p = p.parentElement; }
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
