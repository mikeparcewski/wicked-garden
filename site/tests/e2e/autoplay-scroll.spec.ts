import { test, expect, devices, type Page } from '@playwright/test';
import { hydrated, expectRevealed } from './utils';

/**
 * An auto-playing block never moves the page or takes focus. The demos swap content on their own
 * timers inside fixed boxes; with Chromium's scroll anchoring on, the QE fleet's regroup (every 2.6s)
 * moved the tile anchoring the viewport, and the page jumped back by a row or more while the visitor
 * read (site.css: html { overflow-anchor: none }). Each case scrolls past the hero, sits through at
 * least two ticks of the blocks on screen, and checks the page has not moved and focus is untouched.
 */

/** sit still for `ms`: every scroll position seen, every focus move, and whether focus ended where it began */
async function sit(page: Page, ms: number) {
  return page.evaluate(
    (ms) =>
      new Promise<{ ys: number[]; focusins: number; sameFocus: boolean }>((done) => {
        const ys = new Set<number>([Math.round(window.scrollY)]);
        const a0 = document.activeElement;
        let focusins = 0;
        const on = () => ys.add(Math.round(window.scrollY));
        const fin = () => { focusins += 1; };
        window.addEventListener('scroll', on, { passive: true });
        document.addEventListener('focusin', fin, true);
        setTimeout(() => {
          window.removeEventListener('scroll', on);
          document.removeEventListener('focusin', fin, true);
          on();
          done({ ys: [...ys], focusins, sameFocus: document.activeElement === a0 });
        }, ms);
      }),
    ms,
  );
}

// two ticks of the slowest loop on the page (the panel steps every 4.6s, the packs every 4.2s, the fleet
// regroups every 2.6s) plus a margin
const TWO_TICKS = 10_000;

test.describe('phone (390x844): autoplay never moves the page', () => {
  const iphone = devices['iPhone 12'];
  // 390x844 (the iPhone 12 descriptor's viewport is 390x664; 844 is its screen, where the jump was seen)
  test.use({ viewport: { width: 390, height: 844 }, userAgent: iphone.userAgent, deviceScaleFactor: iphone.deviceScaleFactor, isMobile: true, hasTouch: true });

  for (const id of ['gate', 'graph', 'qe', 'fleet', 'panel', 'memory', 'toolkit', 'extend', 'install']) {
    test(`past the hero, reading #${id}`, async ({ page }) => {
      test.setTimeout(45_000);
      await page.goto('/');
      await hydrated(page);
      // 300px into the section: its demo is on screen and playing
      const y = await page.evaluate((id) => {
        const s = document.getElementById(id)!;
        window.scrollTo({ top: Math.round(s.getBoundingClientRect().top + window.scrollY + 300), behavior: 'instant' });
        return Math.round(window.scrollY);
      }, id);
      const hero = await page.evaluate(() => document.getElementById('hero')!.getBoundingClientRect().bottom);
      expect(hero, 'the hero is scrolled past').toBeLessThan(0);
      const seen = await sit(page, TWO_TICKS);
      expect(seen.ys, `scroll positions while #${id} played`).toEqual([y]);
      expect(seen.focusins, 'nothing took focus').toBe(0);
      expect(seen.sameFocus).toBe(true);
    });
  }

  test('the fleet really plays while it is read (the case above is not vacuous)', async ({ page }) => {
    test.setTimeout(45_000);
    await page.goto('/');
    await hydrated(page);
    await page.evaluate(() => {
      const s = document.getElementById('fleet')!;
      window.scrollTo({ top: Math.round(s.getBoundingClientRect().top + window.scrollY + 300), behavior: 'instant' });
    });
    const tab = () => page.locator('#fleet [role="tab"][aria-selected="true"]').innerText();
    const a = await tab();
    await expect.poll(tab, { timeout: 8_000 }).not.toBe(a);
  });
});

test.describe('desktop: autoplay never moves the page', () => {
  for (const [w, h] of [[1440, 700], [1440, 900], [1100, 650]]) {
    test(`${w}x${h}: one step past the hero, then two ticks`, async ({ page }) => {
      test.setTimeout(45_000);
      await page.setViewportSize({ width: w, height: h });
      await page.goto('/');
      await hydrated(page);
      await page.mouse.move(w / 2, h / 2);
      const locked = await page.evaluate(() => document.documentElement.classList.contains('snap-lock'));
      // snap-locked, one wheel step is one frame; where the page scrolls freely, go to the gate's top
      if (locked) await page.mouse.wheel(0, 160);
      else await page.evaluate(() => window.scrollTo({ top: document.getElementById('gate')!.getBoundingClientRect().top + window.scrollY, behavior: 'instant' }));
      // the step comes to rest
      let last = -1;
      await expect.poll(async () => { const y = await page.evaluate(() => Math.round(window.scrollY)); const same = y === last; last = y; return same && y > 0; }, { intervals: [300] }).toBe(true);
      const hero = await page.evaluate(() => document.getElementById('hero')!.getBoundingClientRect().bottom);
      expect(hero, 'the hero is scrolled past').toBeLessThanOrEqual(1);
      await page.mouse.move(w - 4, h - 4);
      const seen = await sit(page, TWO_TICKS);
      expect(seen.ys).toEqual([last]);
      expect(seen.focusins, 'nothing took focus').toBe(0);
      expect(seen.sameFocus).toBe(true);
    });
  }
});

test.describe('a key press still brings the control it focuses into view', () => {
  // on a phone the install tabs stack, so the next one can sit below the window's edge
  test.use({ viewport: { width: 390, height: 664 }, isMobile: true, hasTouch: true });

  test('ArrowRight on the install tabs, the next tab just off screen', async ({ page }) => {
    await page.goto('/');
    await hydrated(page);
    const first = page.locator('#ib-tab-family');
    const next = page.locator('#ib-tab-plugin');
    // the install bench has risen in (its entrance moves it), then the first tab sits at the window's bottom
    // edge and the second one below it
    await first.evaluate((el) => el.scrollIntoView({ block: 'center', behavior: 'instant' }));
    await expectRevealed(first);
    // and its stage's arrival (a transform, which moves the tabs' boxes while it runs) has settled
    await expect.poll(() => first.evaluate((el) => { const st = el.closest('.sx-stage'); return !st || (st.classList.contains('is-entered') && getComputedStyle(st).transform === 'none'); })).toBe(true);
    await first.evaluate((el) => { const r = el.getBoundingClientRect(); window.scrollTo({ top: window.scrollY + r.bottom - window.innerHeight + 2, behavior: 'instant' }); });
    await first.focus();
    const below = await next.evaluate((el) => el.getBoundingClientRect().top >= window.innerHeight - 4);
    await page.keyboard.press('ArrowRight');
    await expect(next).toBeFocused();
    await expect.poll(() => next.evaluate((el) => { const r = el.getBoundingClientRect(); return r.top >= 64 - 1 && r.bottom <= window.innerHeight + 1; })).toBe(true);
    // (the case only proves something when the next tab started off screen)
    expect(below).toBe(true);
  });
});
