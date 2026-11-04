import { test, expect } from '@playwright/test';
import { hydrated } from './utils';
import { SIZES, place, watch, read, quiet, waitForMotion, expectStill, setHidden, snaps } from './offscreen-kit';

/**
 * Every auto-playing block stops when nobody can see it, and never moves the page
 * (operator, 2026-11-04: "when interactives are playing the scroll is scrolling back to them").
 *
 * For each block, at 1440x900, 1280x720 and 390x844: it plays on screen; off screen (and, where the
 * page does not snap, peeking in under its threshold at an edge) nothing in its stage changes or
 * animates for two of its cycles, the page holds still and nothing takes focus; back on screen it
 * plays again. A pause by the visitor stays paused when it comes back (Play then plays it), a hidden
 * tab holds it, and reduced motion switched on mid-run settles the gate and the packs at once. The QE
 * wall's report card reveals once: it waits off screen, then reveals on screen. A claim picked while
 * the stamp is held shows in full.
 */

// each block's own stage (its useAutoplay root, which holds its controls, rows and tiles) is what is placed and
// watched; the island around it also holds the section's entrance wrappers (page reveals of static text, which
// settle on their own timers) and, for the QE wall, a figure that plays on its own, which are not the block
const ITEMS = [
  { name: 'the hero stamp', stage: '.hs-card', cycle: 2600 },
  { name: 'the gate machine', stage: '.pg-machine', cycle: 2800 },
  { name: 'the graph stage', stage: '.gx-stage', cycle: 2600 },
  { name: 'the QE wall', stage: '.qw-stage', cycle: 2600 },
  { name: 'the QE fleet', stage: '#fleet .sx-stage', cycle: 2600 },
  { name: 'the review panel', stage: '.pv-stage', cycle: 4600 },
  { name: 'the memory queue', stage: '.mq-stage', cycle: 2600 },
  { name: 'the catalog explorer', stage: '.cx-stage', cycle: 2400 },
  { name: 'the extend packs', stage: '.xp-grid', cycle: 4200 },
  { name: 'the install bench', stage: '.ib-stage', cycle: 2600 },
];

for (const size of SIZES) {
  test.describe(`${size.width}x${size.height}`, () => {
    test.use({ viewport: size });

    for (const it of ITEMS) {
      test(`${it.name} holds off screen and plays again when it is back`, async ({ page }) => {
        test.setTimeout(90_000);
        const root = it.stage;
        await page.goto('/');
        await hydrated(page);
        await place(page, it.stage, 'on');
        const playing = await waitForMotion(page, root, it.cycle + 3000);
        expect(playing.mutations, `${it.name} plays on screen`).toBeGreaterThan(0);
        expect(playing.moved, `${it.name}: the page moved while it played`).toBeLessThanOrEqual(1);
        await expectStill(page, it.stage, it.cycle, 'off', it.name, root);
        if (!(await snaps(page))) await expectStill(page, it.stage, it.cycle, 'edge', it.name, root);
        await place(page, it.stage, 'on');
        const again = await waitForMotion(page, root, 2 * it.cycle + 1500);
        expect(again.mutations, `${it.name} plays again back on screen`).toBeGreaterThan(0);
        expect(again.moved, `${it.name}: the page moved while it played`).toBeLessThanOrEqual(1);
        expect(again.focusMoved, `${it.name}: focus moved while it played`).toBe(false);
      });
    }

    test('a pause by the visitor stays paused when the block comes back on screen', async ({ page }) => {
      test.setTimeout(60_000);
      const stage = '#fleet .sx-stage', root = stage;
      await page.goto('/');
      await hydrated(page);
      await place(page, stage, 'on');
      await waitForMotion(page, root, 5000);
      await page.locator(`${root} button[aria-label^="Pause"]`).first().click();
      const toggle = page.locator(`${root} button.px-play`).first();
      await expect(toggle, 'the toggle now offers Play').toHaveAttribute('aria-label', /^Play /);
      // neither the pointer nor focus may hold it: only the Pause
      await page.mouse.move(0, 0);
      await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
      await place(page, stage, 'off');
      await place(page, stage, 'on');
      await quiet(page, root);
      await watch(page, root);
      await page.waitForTimeout(6000);
      const s = await read(page, root);
      expect(s.mutations, 'a paused fleet does not regroup back on screen').toBe(0);
      expect(s.running, 'a paused fleet does not animate back on screen').toBe(0);
      expect(s.focusMoved).toBe(false);
      // Play plays it again
      await toggle.click();
      await page.mouse.move(0, 0);
      await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
      const again = await waitForMotion(page, root, 6000);
      expect(again.mutations, 'Play plays the fleet again').toBeGreaterThan(0);
    });

    test('a hidden tab holds the playing fleet; visible again, it plays', async ({ page }) => {
      test.setTimeout(60_000);
      const stage = '#fleet .sx-stage', root = stage;
      await page.goto('/');
      await hydrated(page);
      await place(page, stage, 'on');
      await waitForMotion(page, root, 5000);
      await setHidden(page, true);
      await watch(page, root);
      await page.waitForTimeout(5600);
      const s = await read(page, root);
      expect(s.mutations, 'DOM changes in a hidden tab').toBe(0);
      expect(s.running, 'animations running in a hidden tab').toBe(0);
      await setHidden(page, false);
      const again = await waitForMotion(page, root, 6000);
      expect(again.mutations, 'the fleet plays once the tab is visible').toBeGreaterThan(0);
    });

    test("the QE wall's report card waits off screen and reveals once it is on screen", async ({ page }) => {
      test.setTimeout(45_000);
      const fig = '.qw-fig';
      await page.goto('/');
      await hydrated(page);
      await expectStill(page, fig, 1300, 'off', 'the report card');
      if (!(await snaps(page))) await expectStill(page, fig, 1300, 'edge', 'the report card');
      await expect(page.locator(fig)).toHaveAttribute('data-revealed', 'false');
      await place(page, fig, 'on');
      await expect(page.locator(fig), 'it reveals on screen').toHaveAttribute('data-revealed', 'true', { timeout: 6000 });
    });

    test('reduced motion switched on mid-run settles the gate and the packs at once', async ({ page }) => {
      test.setTimeout(45_000);
      await page.goto('/');
      await hydrated(page);
      await place(page, '.pg-machine', 'on');
      await expect(page.locator('.pg-machine .is-checking').first(), 'the gate is mid-check').toBeAttached({ timeout: 8000 });
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await expect(page.locator('.pg-machine'), 'the gate shows its verdict').toHaveClass(/is-stamped/);
      await expect(page.locator('.pg-machine .is-checking'), 'no chip is left checking').toHaveCount(0);
      await page.emulateMedia({ reducedMotion: 'no-preference' });
      await page.reload();
      await hydrated(page);
      await place(page, '.xp-grid', 'on');
      await expect(page.locator('.xp-grid .xp-row:not(.is-landed)').first(), 'the next pack is typing its rows').toBeAttached({ timeout: 9000 });
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await expect(page.locator('.xp-grid .xp-row:not(.is-landed)'), 'every row lands at once').toHaveCount(0);
    });
  
    test('a claim picked while the stamp is held (pointer, keyboard) shows in full: a hold never freezes an entrance', async ({ page }) => {
      test.setTimeout(45_000);
      await page.goto('/');
      await hydrated(page);
      await place(page, '.hs-card', 'on');
      const opacity = (sel: string) => page.locator(sel).first().evaluate((el) => Number(getComputedStyle(el).opacity));
      // the pointer: hover holds the card, and a click picks the next claim
      const tabs = page.locator('.hs-dots [role="tab"]');
      await tabs.nth(1).click();
      await page.waitForTimeout(1200);
      expect(await opacity('.hs-claim'), 'the picked claim shows (pointer)').toBeGreaterThan(0.99);
      // the keyboard: focus holds the card, and an arrow picks the next claim
      await page.keyboard.press('ArrowRight');
      await page.waitForTimeout(1200);
      expect(await opacity('.hs-claim'), 'the picked claim shows (keyboard)').toBeGreaterThan(0.99);
      if (await page.locator('.hs-reason').count()) expect(await opacity('.hs-reason'), 'its verdict shows').toBeGreaterThan(0.99);
    });
  });
}
