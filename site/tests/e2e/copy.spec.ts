import { test, expect } from '@playwright/test';

/**
 * The reviewed messaging under the hero: the sub-line names the proof gate, three benefits, and
 * what's new in 12.64. Asserted on rendered text, so a word fused to the following inline tag
 * (Astro compressHTML deletes a newline before <span>/<b>/<code>) fails here, not in review.
 */
test('the hero sub-line names the hosts and the proof gate, with no fused words', async ({ page }) => {
  await page.goto('/');
  const sub = (await page.locator('.gd-hero-sub').innerText()).replace(/\s+/g, ' ');
  expect(sub).toContain('Skills for Claude Code, Codex, Antigravity, OpenCode and Pi');
  expect(sub).toContain('matters most: a proof gate that re-derives “done” from evidence');
  expect(sub).not.toContain('never asserted');
});

test('the three benefits lead their sections, and what is new in 12.64 closes memory', async ({ page }) => {
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
  await expect(page.locator('#memory .mq-new-h')).toHaveText('What’s new in 12.64');
  const text = (await page.locator('#memory .mq-new-list').innerText()).replace(/\s+/g, ' ');
  expect(text).toContain('Answers from your data: in a wicked-crew chat or job');
  expect(text).toContain('Data shapes: shapes proposes');
  expect(text).toContain('Apps: wicked-garden-apps builds');
  expect(text).toContain('An app can show your knowledge, memories and rules');
  expect(text).toContain('never stores a row');
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

test('claims the source backs: no unmeasured family count, no false privacy line, no retired domain, memory scoped to crew', async ({ page }) => {
  await page.goto('/');
  const text = (await page.evaluate(() => (document.querySelector('main') as HTMLElement).innerText)).replace(/\s+/g, ' ');
  // N9: only measured numbers (skills, QE specialists, work-shapes); the family tabs are a grouping
  expect(text).not.toMatch(/\d+ domains/);
  // garden's skills run inside hosted agents and the panel calls other vendors' CLIs: claim only local storage
  expect(text).not.toContain('nothing leaves your machine');
  expect(text).toContain('memory, evidence and the code graph stay in local files');
  // the installer ships no shared `wicked` CLI, and the smaht domain and its sub-skills are retired
  expect(text).not.toMatch(/shared wicked CLI|ships the wicked CLI/);
  expect(text).not.toMatch(/propose-skills|\bsmaht\b/);
  // approval is the crew-job path; outside a job the agent stores directly
  await expect(page.locator('#memory .sx-h2')).toHaveText('In a crew job, agents propose. You approve.');
  expect((await page.locator('#memory .sx-lead').innerText()).replace(/\s+/g, ' ')).toContain('In a wicked-crew job an agent can only propose');
  // the hero says how to call a skill, and lists what is inside, each linked to its frame
  expect((await page.locator('.gd-hero-call').innerText()).replace(/\s+/g, ' ')).toContain('in Claude Code, /wicked-garden-prove;');
  await expect(page.locator('.gd-hero-inside a')).toHaveCount(5);
  await expect(page.locator('.gd-hero-inside a').first()).toHaveAttribute('href', '#gate');
});
