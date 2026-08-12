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
  // The chrome normalizes to a concrete theme on load (default: light).
  await expect(html).toHaveAttribute('data-theme', /^(light|dark)$/);
  const initial = await html.getAttribute('data-theme');
  const flipped = initial === 'dark' ? 'light' : 'dark';

  await page.locator('#themeBtn').click();
  await expect(html).toHaveAttribute('data-theme', flipped);
  await expect
    .poll(() => page.evaluate(() => localStorage.getItem('wa-theme')))
    .toBe(flipped);

  // Persistence: the no-flash init in Base.astro reads 'wa-theme' before paint.
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
  await expect(menu.getByRole('link', { name: /garden/ })).toBeVisible();
  await expect(menu.getByRole('link', { name: /crew/ })).toBeVisible();

  await page.keyboard.press('Escape');
  await expect(menu).toBeHidden();
  await expect(btn).toHaveAttribute('aria-expanded', 'false');
});
