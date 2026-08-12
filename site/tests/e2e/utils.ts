import { expect, type Locator } from '@playwright/test';

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
