import { test, expect } from '@playwright/test';

/**
 * The reviewed messaging under the hero: the sub-line names the proof gate, three benefits, and
 * what's new in 12.62. Asserted on rendered text, so a word fused to the following inline tag
 * (Astro compressHTML deletes a newline before <span>/<b>/<code>) fails here, not in review.
 */
test('the hero sub-line names the hosts and the proof gate, with no fused words', async ({ page }) => {
  await page.goto('/');
  const sub = (await page.locator('.gd-hero-sub').innerText()).replace(/\s+/g, ' ');
  expect(sub).toContain('Skills for Claude Code, Codex, Antigravity, OpenCode and Pi');
  expect(sub).toContain('matters most: a proof gate that re-derives “done” from evidence');
  expect(sub).not.toContain('never asserted');
});

test('why: three benefits, the advise/block link, and what is new in 12.62', async ({ page }) => {
  await page.goto('/');
  const why = page.locator('#why');
  await expect(why.locator('.wy-card')).toHaveCount(3);
  await expect(why.getByRole('link', { name: 'spelled out' })).toHaveAttribute(
    'href',
    'https://github.com/mikeparcewski/wicked-garden#what-blocks-what-advises',
  );
  // The panel is not always other models: a same-family fallback is labelled.
  await expect(why).toContainText('a same-family fallback is labelled');
  const items = why.locator('.wy-new li');
  await expect(items).toHaveCount(3);
  const text = (await why.locator('.wy-new').innerText()).replace(/\s+/g, ' ');
  expect(text).toContain('Style learning: repo-learn learns');
});
