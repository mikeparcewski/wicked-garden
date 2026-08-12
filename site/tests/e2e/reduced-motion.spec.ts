import { test, expect } from '@playwright/test';
import { expectRevealed } from './utils';

/**
 * prefers-reduced-motion smoke. The site leans on animation (CSS keyframes,
 * IntersectionObserver reveals, the motion library in the component library),
 * and every animated component carries its own reduced-motion branch — this
 * asserts none of those branches throw and the page still fully renders.
 */
test.use({ contextOptions: { reducedMotion: 'reduce' } });

test('reduced motion: zero page errors and every key section visible', async ({ page }) => {
  const errors: Error[] = [];
  page.on('pageerror', (err) => errors.push(err));

  await page.goto('/');
  await expect(page.locator('h1')).toContainText('The tools your coding agent');

  // Walk every section; Reveal short-circuits to visible under reduced motion.
  const sections: Array<[string, RegExp]> = [
    ['#toolbox', /Six gaps your agent/],
    ['#gate', /Play the lying agent/],
    ['#toolkit', /Six tools were the sample/],
    ['#qe', /No agent grades its own homework/],
    ['#fleet', /Forty specialists/],
    ['#extend', /Your domain\. Your pack\./],
    ['#install', /One command/],
  ];
  for (const [id, heading] of sections) {
    const section = page.locator(id);
    await section.scrollIntoViewIfNeeded();
    const h2 = section.getByRole('heading', { name: heading });
    await expect(h2).toBeVisible();
    await expectRevealed(h2);
  }

  // The hero island still runs its (shortened) verdict loop without throwing.
  await page.locator('.hs-card').scrollIntoViewIfNeeded();
  await expect(page.locator('.hs-card .hs-stage')).toBeVisible();

  // qe bands honor reduced motion: the evidence channel doesn't play and the
  // fleet doesn't auto-cycle — the visitor drives from the start.
  await expect(page.locator('.qw-stage')).not.toHaveClass(/is-playing/);
  await expect(page.locator('#fleet .qf-afford')).toContainText('driving');
  await expect(page.locator('#fleet .qf-agent')).toHaveCount(40);

  expect(errors, `pageerror events: ${errors.map((e) => e.message).join('; ')}`).toEqual([]);
});
