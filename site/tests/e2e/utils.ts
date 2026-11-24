import { expect, type Locator, type Page } from '@playwright/test';

/** Wait until every Astro island has hydrated (Astro drops the `ssr` attribute once it has). A click
 *  before that lands on server-rendered HTML with no handler, which reads as a broken control. */
export async function hydrated(page: Page): Promise<void> {
  await page.waitForFunction(() => document.querySelectorAll('astro-island[ssr]').length === 0, null, { timeout: 15_000 });
}

/**
 * Assert that the nearest <Reveal> wrapper around `target` has finished its
 * fade-in. Playwright's toBeVisible() ignores opacity, so an element inside a
 * still-transparent Reveal wrapper would pass a plain visibility check while
 * being invisible to a human. This walks up to the nearest ancestor carrying
 * an inline opacity style (the Reveal div) and polls its computed opacity.
 */
export async function expectRevealed(target: Locator): Promise<void> {
  await expect
    .poll(
      () =>
        target.evaluate((el) => {
          let node: HTMLElement | null = el as HTMLElement;
          while (node) {
            if (node.style && node.style.opacity !== '') return getComputedStyle(node).opacity;
            node = node.parentElement;
          }
          return '1'; // no Reveal wrapper — nothing to wait for
        }),
      { timeout: 10_000, message: 'Reveal wrapper should reach opacity 1' },
    )
    .toBe('1');
}

/**
 * Wait until the section stage (.sx-stage) around `target` has finished its arrival entrance.
 * section-enter.ts holds a stage at translateY(14px) scale(.98) until the visitor first reaches it,
 * then transitions it to none (.7s after a .16s delay). A box read inside a stage before that ends
 * is a scaled box, so a before/after size check would compare two points of the transition. Passes
 * at once for a target outside any stage.
 */
export async function expectStageSettled(target: Locator): Promise<void> {
  await expect
    .poll(
      () =>
        target.evaluate((el) => {
          const stage = el.closest('.sx-stage');
          return !stage || (stage.getAnimations().length === 0 && getComputedStyle(stage).transform === 'none');
        }),
      { timeout: 10_000, message: 'the section stage should finish its entrance before the target is measured' },
    )
    .toBe(true);
}

/**
 * Click `chip` (a CopyChip) until its transient "copied" feedback shows.
 * The feedback auto-clears after 1.4s, so the click + assertion are retried
 * as a unit instead of racing a fixed observation window.
 */
export async function clickCopyChip(chip: Locator): Promise<void> {
  await chip.scrollIntoViewIfNeeded();
  await expect(async () => {
    await chip.click();
    await expect(chip).toContainText('copied', { timeout: 1_200 });
  }).toPass({ timeout: 15_000 });
}
