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

test('the three benefits lead their sections, and what is new in 12.62 closes memory', async ({ page }) => {
  await page.goto('/');
  const lead = async (id: string) => (await page.locator(`#${id} .sx-lead`).innerText()).replace(/\s+/g, ' ');
  expect(await lead('gate')).toContain('Proof, not claims. Run the proof gate and “done” is re-checked from evidence');
  await expect(page.locator('#gate .sx-lead').getByRole('link', { name: 'spelled out' })).toHaveAttribute(
    'href',
    'https://github.com/mikeparcewski/wicked-garden#what-blocks-what-advises',
  );
  expect(await lead('graph')).toContain('finds the event and command links grep never sees');
  expect(await lead('qe')).toContain('never runs the reviewer inline with the test writer or the executor');
  // The panel is not always other models: a same-family fallback is labelled.
  expect(await lead('panel')).toContain('a same-family fallback is labelled, and without a quorum it gives no verdict');
  const items = page.locator('#memory .mq-new-list li');
  await expect(items).toHaveCount(3);
  await expect(page.locator('#memory .mq-new-h')).toHaveText('What’s new in 12.62');
  const text = (await page.locator('#memory .mq-new-list').innerText()).replace(/\s+/g, ' ');
  expect(text).toContain('Style learning: repo-learn learns');
  expect(text).toContain('In a wicked-crew job, every agent is asked to propose what it witnessed, as a memory');
});

test('public words: no seat, floor, plane or unmeasured numbers outside the platform map', async ({ page }) => {
  await page.goto('/');
  const text = await page.evaluate(() =>
    Array.from(document.querySelectorAll('main > section:not(#platform-map)')).map((s) => (s as HTMLElement).innerText).join(' '),
  );
  expect(text).not.toMatch(/\bseats?\b/i);
  expect(text).not.toMatch(/\bfloor\b/i);
  expect(text).not.toMatch(/\bplanes?\b/i);
  expect(text).not.toContain('80%');
  // the work-shape count is the archetype catalog's, counted at build time
  await expect(page.locator('.gd-hero-stats')).toContainText(/\d+ work-shapes/);
});
