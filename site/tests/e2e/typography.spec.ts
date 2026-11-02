import { test, expect } from '@playwright/test';

/**
 * Faces and colours under wicked-web v3: commands are JetBrains Mono at the code step, their
 * "copy" label is the text face, and the page glow carries no retired signal yellow.
 */
test('the faces actually load (a computed stack alone passes even when every woff2 fails)', async ({ page }) => {
  await page.goto('/');
  const loaded = await page.evaluate(async () => {
    await document.fonts.ready;
    const ok = (f: string) => [...document.fonts].some((x) => x.family.replace(/"/g, '') === f && x.status === 'loaded');
    return { sans: ok('Wicked Sans'), serif: ok('Wicked Serif'), mono: ok('JetBrains Mono') };
  });
  expect(loaded).toEqual({ sans: true, serif: true, mono: true });
});

test('the install chip: command in mono at 13px, its label in the text face', async ({ page }) => {
  await page.goto('/');
  const chip = page.locator('button', { hasText: 'npx wicked-installer' }).first();
  await expect(chip).toHaveCSS('font-family', /JetBrains Mono/);
  await expect(chip).toHaveCSS('font-size', '13px');
  await expect(chip.locator('span').last()).toHaveCSS('font-family', /^"?Wicked Sans/);
});

test('the page glow uses the neutral mesh, never the retired yellow', async ({ page }) => {
  await page.goto('/');
  for (const theme of ['dark', 'light']) {
    await page.evaluate((t) => document.documentElement.setAttribute('data-theme', t), theme);
    const bg = await page.evaluate(() => getComputedStyle(document.body, '::after').backgroundImage);
    expect(bg, theme).toContain('radial-gradient');
    // every colour stop is neutral: rgb(a) stops have r = g = b within 6, oklab stops have |a|, |b| under 0.02
    const stops = bg.match(/(rgba?|oklab)\([^)]*\)/g) ?? [];
    expect(stops.length, theme).toBeGreaterThan(0);
    for (const st of stops) {
      const n = (st.match(/-?[\d.]+/g) ?? []).map(Number);
      if (st.startsWith('oklab')) expect(Math.max(Math.abs(n[1]), Math.abs(n[2])), `${theme} ${st}`).toBeLessThan(0.02);
      else expect(Math.max(n[0], n[1], n[2]) - Math.min(n[0], n[1], n[2]), `${theme} ${st}`).toBeLessThanOrEqual(6);
    }
  }
});

test('the QE wall is fully opaque, so its "cold evidence only" tag keeps its contrast', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('.qw-wall').first()).toHaveCSS('opacity', '1');
});
