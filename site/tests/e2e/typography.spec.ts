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

/** WCAG contrast of a computed CSS colour (rgb() or oklab()) against an sRGB hex ground. */
function contrast(css: string, ground: string): number {
  const lin = (c: number) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  let r: number, g: number, b: number;
  const n = (css.match(/-?[\d.]+/g) ?? []).map(Number);
  if (css.startsWith('oklab')) {
    const [L, A, B] = n;
    const l = (L + 0.3963377774 * A + 0.2158037573 * B) ** 3, m = (L - 0.1055613458 * A - 0.0638541728 * B) ** 3,
      s = (L - 0.0894841775 * A - 1.291485548 * B) ** 3;
    [r, g, b] = [4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s, -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
      -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s];
  } else [r, g, b] = n.slice(0, 3).map((v) => lin(v / 255));
  const y1 = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  const h = ground.replace('#', ''); const [R, G, B2] = [0, 2, 4].map((i) => lin(parseInt(h.slice(i, i + 2), 16) / 255));
  const y2 = 0.2126 * R + 0.7152 * G + 0.0722 * B2;
  return (Math.max(y1, y2) + 0.05) / (Math.min(y1, y2) + 0.05);
}

test('QE green text clears 4.5:1 in Wicked Light on its tints and the trellis', async ({ page }) => {
  await page.goto('/');
  await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'light'));
  // #cad4ca is the darkest ground measured under these glyphs (tint + trellis), review round 3
  for (const sel of ['.qw-foot code', '.xp-cta-label']) {
    const col = await page.locator(sel).first().evaluate((el) => getComputedStyle(el).color);
    expect(contrast(col, '#cad4ca'), `${sel} ${col}`).toBeGreaterThanOrEqual(4.5);
  }
});
