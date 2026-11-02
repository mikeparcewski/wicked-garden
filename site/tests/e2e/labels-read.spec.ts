import { test, expect } from '@playwright/test';
import { hydrated } from './utils';

/**
 * The gate's four check names and the QE report card's labels are short, fixed words. They must read in
 * full at every desktop size: an ellipsis on "attestation" in the first frame (the hero's ticks) and again
 * in the gate's evidence trail made the one claim the page follows look cut off. The chips size to their
 * own text and share the slack, and the report card's two labels wrap instead of truncating.
 *
 * A label is cut when its box is narrower than its text (scrollWidth > clientWidth on an overflow-clipped
 * element). Each state is sampled for a while, because the chips change state as the demos play.
 */
const VIEWPORTS = [
  { width: 1920, height: 1080 },
  { width: 1440, height: 700 },
  { width: 1280, height: 660 },
  { width: 1024, height: 700 },
  { width: 390, height: 844 },
];

const LABELS = ['.hs-tick-name', '.pg-chip-name', '.qw-fig-h > span'];

for (const vp of VIEWPORTS) {
  test(`check names and report-card labels read in full at ${vp.width}x${vp.height}`, async ({ page }) => {
    await page.setViewportSize(vp);
    await page.goto('/');
    await hydrated(page);
    await page.evaluate(async () => { await document.fonts.ready; });

    for (const sel of LABELS) {
      const first = page.locator(sel).first();
      await expect(first, `${sel} should render`).toBeAttached();
      await first.evaluate((el) => el.scrollIntoView({ block: 'center', behavior: 'instant' }));
      // the demos cycle states (checking, ok, fail, skip); every state must leave the names whole
      for (let i = 0; i < 6; i++) {
        const cut = await page.evaluate((s) =>
          [...document.querySelectorAll<HTMLElement>(s)]
            .filter((el) => el.getClientRects().length > 0 && el.scrollWidth > el.clientWidth + 1)
            .map((el) => `${el.textContent?.trim()} (${el.clientWidth}px for ${el.scrollWidth}px)`), sel);
        expect(cut, `${sel} cut at ${vp.width}x${vp.height}`).toEqual([]);
        await page.waitForTimeout(400);
      }
    }
  });
}
