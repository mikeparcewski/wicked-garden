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

test('the topbar tooltips open below the bar, fully on screen, and hide while the menu is open', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 700 });
  const bar = await page.locator('.topbar').evaluate((el) => el.getBoundingClientRect().bottom);
  for (const sel of ['#themeBtn', '.topbar a[data-tip="github"]', '.topbar .dropdown-wrap']) {
    const el = page.locator(sel);
    await el.hover();
    const tip = await el.evaluate((e) => {
      const a = getComputedStyle(e, '::after');
      const top = e.getBoundingClientRect().top + parseFloat(a.top);
      return { top, bottom: top + parseFloat(a.height) };
    });
    expect(tip.top, `${sel} tip top`).toBeGreaterThanOrEqual(bar);
    expect(tip.bottom, `${sel} tip bottom`).toBeLessThan(700);
  }
  // at the narrowest window that still shows the inline icons, the last tip stays inside the window
  await page.setViewportSize({ width: 641, height: 700 });
  await page.locator('#themeBtn').hover();
  const right = await page.locator('#themeBtn').evaluate((e) => {
    const a = getComputedStyle(e, '::after');
    const r = e.getBoundingClientRect();
    const box = parseFloat(a.width) + (a.boxSizing === 'content-box'
      ? parseFloat(a.paddingLeft) + parseFloat(a.paddingRight) + parseFloat(a.borderLeftWidth) + parseFloat(a.borderRightWidth) : 0);
    const shift = a.transform === 'none' ? 0 : new DOMMatrix(a.transform).m41;
    return r.left + parseFloat(a.left) + shift + box;
  });
  expect(right).toBeLessThanOrEqual(641);
  await page.setViewportSize({ width: 1440, height: 700 });
  await page.locator('#projectsBtn').click();
  await page.locator('#projectsBtn').hover();
  await expect.poll(() => page.locator('.topbar .dropdown-wrap').evaluate((e) => getComputedStyle(e, '::after').opacity)).toBe('0');
  // the menu is wide enough that no row is cut short
  const cut = await page.locator('#projectsMenu .di-label').evaluateAll((els) => els.filter((e) => e.scrollWidth > e.clientWidth + 1).length);
  expect(cut).toBe(0);
});
