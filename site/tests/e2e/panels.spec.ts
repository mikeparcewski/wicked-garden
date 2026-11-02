import { test, expect } from '@playwright/test';
import { hydrated } from './utils';

/**
 * The second-opinion panel (#panel) and memory you approve (#memory): each auto-plays, and its
 * controls take over. Both reserve their tallest state, so a switch never resizes the section.
 */

test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await hydrated(page);
});

test('PanelVote: what you have installed decides the panel, a fallback is labelled, no quorum gives no verdict', async ({ page }) => {
  const panel = page.locator('#panel');
  await panel.scrollIntoViewIfNeeded();
  const h = await panel.evaluate((el) => el.getBoundingClientRect().height);
  const radios = panel.getByRole('radio');
  await expect(radios).toHaveCount(3);

  await panel.getByRole('radio', { name: 'several other agents' }).click();
  await expect(panel.locator('.pv-afford')).toContainText('driving');
  await expect(panel.locator('.pv-vote.is-dissent')).toHaveCount(1);
  await expect(panel.locator('.pv-result')).toContainText('panel 2 of 3');

  await panel.getByRole('radio', { name: 'one model family' }).click();
  await expect(panel.locator('.pv-result')).toContainText('same-family workers, labelled weaker diversity');

  await panel.getByRole('radio', { name: 'fewer than two' }).click();
  await expect(panel.locator('.pv-result')).toContainText('no quorum');
  await expect(panel.locator('.pv-vote')).toHaveCount(3); // the rows stay reserved
  expect(await panel.evaluate((el) => el.getBoundingClientRect().height)).toBe(h);
  await expect(panel.getByRole('button', { name: 'Copy command: wicked-garden-jam' })).toBeVisible();
});

test('MemoryQueue: approve recalls it with a citation, drop leaves nothing to cite', async ({ page }) => {
  const mem = page.locator('#memory');
  await mem.scrollIntoViewIfNeeded();
  const h = await mem.evaluate((el) => el.getBoundingClientRect().height);
  await mem.getByRole('button', { name: 'Approve' }).click();
  await expect(mem.locator('.mq-afford')).toContainText('driving');
  await expect(mem.locator('.mq-answer')).toContainText('[cited · estate record]');
  await mem.getByRole('button', { name: 'Drop' }).click();
  await expect(mem.locator('.mq-answer')).toContainText('nothing to cite');
  expect(await mem.evaluate((el) => el.getBoundingClientRect().height)).toBe(h);
  await mem.getByRole('button', { name: /resume/ }).click();
  await expect(mem.locator('.mq-afford')).toContainText('auto-playing');
});

test('MemoryQueue: turning on reduced motion never overrides a decision the visitor made', async ({ page }) => {
  const mem = page.locator('#memory');
  await mem.scrollIntoViewIfNeeded();
  await mem.getByRole('button', { name: 'Drop' }).click();
  await expect(mem.locator('.mq-answer')).toContainText('nothing to cite');
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.waitForTimeout(500);
  await expect(mem.locator('.mq-answer')).toContainText('nothing to cite');
  await expect(mem.locator('.mq-answer')).not.toContainText('[cited');
});
