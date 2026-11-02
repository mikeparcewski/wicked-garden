import { test, expect } from '@playwright/test';

/**
 * Faces and colours under wicked-web v3: commands are JetBrains Mono at the code step, their
 * "copy" label is the text face, and the page glow carries no retired signal yellow.
 */
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
    expect(bg, theme).not.toMatch(/rgba?\(255, 218, 25/);
  }
});

test('the QE wall is fully opaque, so its "cold evidence only" tag keeps its contrast', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('.qw-wall').first()).toHaveCSS('opacity', '1');
});
