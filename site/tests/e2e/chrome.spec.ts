import { test, expect } from '@playwright/test';

/**
 * Shared wicked-web chrome (node_modules/wicked-web): theme toggle and the
 * ecosystem dropdown in the fixed topbar.
 */

test.beforeEach(async ({ page }) => {
  await page.goto('/');
});

test('theme toggle flips data-theme on <html> and persists across reload', async ({ page }) => {
  const html = page.locator('html');
  // A fresh load is Wicked Dark and persists nothing: only a click writes the choice.
  await expect(html).toHaveAttribute('data-theme', 'dark');
  expect(await page.evaluate(() => localStorage.getItem('wa-theme-v3'))).toBeNull();
  const flipped = 'light';

  await page.locator('#themeBtn').click();
  await expect(html).toHaveAttribute('data-theme', flipped);
  await expect
    .poll(() => page.evaluate(() => localStorage.getItem('wa-theme-v3')))
    .toBe(flipped);

  // Persistence: the no-flash init in Base.astro reads 'wa-theme-v3' before paint.
  await page.reload();
  await expect(html).toHaveAttribute('data-theme', flipped);
});

test('ecosystem dropdown opens on click and closes on Escape', async ({ page }) => {
  const btn = page.locator('#projectsBtn');
  const menu = page.locator('#projectsMenu');
  await expect(menu).toBeHidden();

  await btn.click();
  await expect(menu).toBeVisible();
  await expect(btn).toHaveAttribute('aria-expanded', 'true');
  // The 61396e4 chrome groups the menu by the four planes; assert the plane
  // groups and the unambiguous site links (several labels mention "crew").
  await expect(menu.locator('.dropdown-plane')).toHaveCount(4);
  await expect(menu.locator('a[href="https://wg.wickedagile.com"]')).toBeVisible();
  await expect(menu.locator('a[href="https://wc.wickedagile.com"]')).toBeVisible();

  await page.keyboard.press('Escape');
  await expect(menu).toBeHidden();
  await expect(btn).toHaveAttribute('aria-expanded', 'false');
});

test('a stored v2 theme is ignored: the reset to Wicked Dark happens once, and the load writes nothing', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('wa-theme', 'light'));
  await page.goto('/');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  expect(await page.evaluate(() => localStorage.getItem('wa-theme-v3'))).toBeNull();
});
