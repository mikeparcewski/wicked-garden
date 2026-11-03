import { test, expect } from '@playwright/test';

/**
 * Shared wicked-web chrome (node_modules/wicked-web): theme toggle, the product path
 * ("Wicked Agile / labs / wicked-garden") and the flask that links Wicked Labs in the fixed topbar.
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

test('the product path reads Wicked Agile / labs / wicked-garden, and the flask links Wicked Labs', async ({ page }) => {
  const path = page.getByRole('navigation', { name: 'Breadcrumb' });
  await expect(path.getByRole('link')).toHaveCount(3);
  await expect(path.getByRole('link', { name: 'Wicked Agile' })).toHaveAttribute('href', 'https://wickedagile.com/');
  await expect(path.getByRole('link', { name: 'labs' })).toHaveAttribute('href', 'https://wickedlabs.ai/');
  const here = path.getByRole('link', { name: 'wicked-garden' });
  await expect(here).toHaveAttribute('href', 'https://wg.wickedagile.com');
  await expect(here).toHaveAttribute('aria-current', 'page');
  // the flask is a plain link now: no Experiments menu, no button that opens one
  const lab = page.locator('.topbar .nav').getByRole('link', { name: 'Wicked Labs' });
  await expect(lab).toHaveAttribute('href', 'https://wickedlabs.ai/');
  await expect(lab).toBeVisible();
  await expect(page.locator('#projectsBtn, #projectsMenu, .dropdown-menu')).toHaveCount(0);
});

test('a stored v2 theme is ignored: the reset to Wicked Dark happens once, and the load writes nothing', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('wa-theme', 'light'));
  await page.goto('/');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  expect(await page.evaluate(() => localStorage.getItem('wa-theme-v3'))).toBeNull();
});

test('the topbar tooltips sit inside the bar, clear of the icons and the page, and hide while the menu is open', async ({ page }) => {
  // the tip's painted box: its containing element's box plus the pseudo-element's resolved offsets
  const tipBox = (sel: string) => page.locator(sel).evaluate((e) => {
    const a = getComputedStyle(e, '::after');
    const r = e.getBoundingClientRect();
    const pad = a.boxSizing === 'content-box';
    const w = parseFloat(a.width) + (pad ? parseFloat(a.paddingLeft) + parseFloat(a.paddingRight) + parseFloat(a.borderLeftWidth) + parseFloat(a.borderRightWidth) : 0);
    const h = parseFloat(a.height) + (pad ? parseFloat(a.paddingTop) + parseFloat(a.paddingBottom) + parseFloat(a.borderTopWidth) + parseFloat(a.borderBottomWidth) : 0);
    const m = a.transform === 'none' ? new DOMMatrix() : new DOMMatrix(a.transform);
    const left = r.left + parseFloat(a.left) + m.m41, top = r.top + parseFloat(a.top) + m.m42;
    return { display: a.display, opacity: a.opacity, left, top, right: left + w, bottom: top + h };
  });
  for (const width of [1440, 1024, 800, 768]) {
    await page.setViewportSize({ width, height: 700 });
    const bar = await page.locator('.topbar').evaluate((el) => el.getBoundingClientRect().bottom);
    const blocks = await page.locator('.topbar .icon-btn:visible, .topbar .crumbs a, .topbar .crumb-sep').evaluateAll((els) =>
      els.map((e) => { const r = e.getBoundingClientRect(); return { l: r.left, r: r.right, t: r.top, b: r.bottom }; }));
    // every tip the installed chrome has (whatever its icon row holds)
    const tips = await page.locator('.topbar [data-tip]:visible').evaluateAll((els) => els.map((e) => e.getAttribute('data-tip')!));
    expect(tips.length).toBeGreaterThanOrEqual(3);
    for (const sel of tips.map((t) => `.topbar [data-tip="${t}"]`)) {
      await page.locator(sel).hover();
      await expect.poll(() => tipBox(sel).then((t) => t.opacity)).toBe('1');
      const t = await tipBox(sel);
      // inside the bar: never over page content, never off the window
      expect(t.top, `${sel} at ${width}`).toBeGreaterThanOrEqual(0);
      expect(t.bottom, `${sel} at ${width}`).toBeLessThanOrEqual(bar);
      expect(t.left, `${sel} at ${width}`).toBeGreaterThanOrEqual(0);
      // clear of every icon and every part of the product path
      for (const b of blocks) {
        const hit = t.left < b.r && t.right > b.l && t.top < b.b && t.bottom > b.t;
        expect(hit, `${sel} tip at ${width} overlaps a bar control`).toBe(false);
      }
    }
  }
  // below 768px there is no room beside the product path: no tips (the icons keep their labels)
  await page.setViewportSize({ width: 700, height: 700 });
  expect((await tipBox('#themeBtn')).display).toBe('none');
});
