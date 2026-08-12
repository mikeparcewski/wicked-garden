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

  // The qe wall band collapses cleanly: roles stack, the desktop-only dashed
  // wall + evidence channel are gone, the report-card flip still works.
  const qe = page.locator('#qe');
  await qe.scrollIntoViewIfNeeded();
  await expect(qe.locator('.qw-role')).toHaveCount(3);
  await expect(qe.locator('.qw-wall')).toBeHidden();
  await expect(qe.locator('.qw-channel')).toBeHidden();

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
