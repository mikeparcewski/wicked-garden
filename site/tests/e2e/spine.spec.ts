import { test, expect, type Page } from '@playwright/test';

/**
 * The page's spine, the same as wicked-crew's (ported, site/src/scripts/beats.js): a thread under the
 * topbar with one segment per beat (1024px wide and up) and the beat track in the right gutter (1400px
 * and up, where the gutter holds it), both in garden's plane hue (capability). The QE beat is two
 * sections (#qe and #fleet).
 */
const BEATS: [string, string][] = [
  ['hero', 'The claim'],
  ['gate', 'Gate'],
  ['graph', 'Graph'],
  ['qe', 'QE'],
  ['fleet', 'QE'],
  ['panel', 'Panel'],
  ['memory', 'Memory'],
];
const LINKS = 6;
const HUE = '--plane-capability';

async function goTo(page: Page, id: string) {
  await page.evaluate((id) => document.getElementById(id)!.scrollIntoView({ block: 'start', behavior: 'instant' }), id);
}
/** the computed colour of a token, as the browser resolves it */
async function tokenColour(page: Page, token: string) {
  return page.evaluate((t) => {
    const el = document.createElement('i');
    el.style.color = `var(${t})`;
    document.body.appendChild(el);
    const c = getComputedStyle(el).color;
    el.remove();
    return c;
  }, token);
}

test.describe('the thread and the beat track', () => {
  test('1440x700: a segment per beat, the track names the beat in view, in the plane hue', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 700 });
    await page.goto('/');
    const thread = page.locator('[data-beat-thread]');
    const track = page.getByRole('navigation', { name: 'The claim, beat by beat' });
    await expect(thread.locator('[data-beat-thread-seg]')).toHaveCount(LINKS);
    await expect(track.getByRole('link')).toHaveCount(LINKS);
    for (const [id, name] of BEATS) {
      await goTo(page, id);
      await expect(track.locator('[aria-current="step"] .beats-l')).toHaveText(name);
      await expect(track).toBeVisible();
      await expect(thread).toHaveClass(/is-on/);
    }
    const hue = await tokenColour(page, HUE);
    await expect(track.locator('[aria-current="step"] .beats-dot')).toHaveCSS('background-color', hue);
    await expect(track.locator('[aria-current="step"] .beats-l')).toHaveCSS('color', hue);
    await expect(thread.locator('[data-beat-thread-seg] b').first()).toHaveCSS('background-color', hue);
    // at the last beat every segment before it is full, and a full segment renders full width
    const fill = () => thread.locator('[data-beat-thread-seg] b').evaluateAll((bs) => bs.map((b) => parseFloat((b as HTMLElement).style.getPropertyValue('--f') || '0')));
    expect((await fill()).slice(0, -1).every((x) => x > 0.99)).toBe(true);
    await expect(thread.locator('[data-beat-thread-seg] b').first()).toHaveCSS('transform', 'matrix(1, 0, 0, 1, 0, 0)');
    await expect(thread).toHaveCSS('opacity', '1');
    // back at the top only the first beat has filled; the later ones are empty and render empty
    await goTo(page, BEATS[0][0]);
    await expect.poll(async () => (await fill()).slice(2).every((x) => x === 0)).toBe(true);
    expect((await fill())[0]).toBeGreaterThan(0.99);
    await expect(thread.locator('[data-beat-thread-seg] b').last()).toHaveCSS('transform', 'matrix(0, 0, 0, 1, 0, 0)');
    // half way to the second beat (snapping off, read before anything settles) its segment is part filled
    const mid = await page.evaluate(async (id) => {
      const st = document.createElement('style');
      st.textContent = 'html, html.snap-lock { scroll-snap-type: none !important; scroll-behavior: auto !important; }';
      document.head.appendChild(st);
      const s = document.getElementById(id)!;
      window.scrollTo({ top: s.getBoundingClientRect().top + window.scrollY - window.innerHeight / 2, behavior: 'instant' });
      await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
      const f = parseFloat((document.querySelectorAll('[data-beat-thread-seg] b')[1] as HTMLElement).style.getPropertyValue('--f') || '0');
      st.remove();
      return f;
    }, BEATS[1][0]);
    expect(mid).toBeGreaterThan(0.05);
    expect(mid).toBeLessThan(0.95);
    // the thread lines up with the topbar's row, under it
    const [tb, row, th] = await page.evaluate(() => [
      document.querySelector('.topbar')!.getBoundingClientRect().bottom,
      (() => { const r = document.querySelector('.topbar__inner')!.getBoundingClientRect(); return [r.left, r.right]; })(),
      (() => { const r = document.querySelector('[data-beat-thread]')!.getBoundingClientRect(); return [r.left, r.right, r.top, r.height]; })(),
    ] as const);
    expect(Math.abs(th[0] - row[0])).toBeLessThan(1.5);
    expect(Math.abs(th[1] - row[1])).toBeLessThan(1.5);
    expect(Math.abs(th[2] - tb)).toBeLessThan(1.5);
    expect(th[3]).toBe(3);
  });

  test('1920x1080: the thread widens to 1400px like crew\'s, and the track shows', async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto('/');
    await goTo(page, BEATS[2][0]);
    // centred in the layout width (a classic scrollbar, as on Linux, takes its width off the window)
    const [l, r, cw] = await page.evaluate(() => { const r = document.querySelector('[data-beat-thread]')!.getBoundingClientRect(); return [r.left, r.right, document.documentElement.clientWidth]; });
    expect(r - l).toBe(1400);
    expect(Math.abs(l - (cw - 1400) / 2)).toBeLessThan(1);
    await expect(page.locator('[data-beats]')).toBeVisible();
  });

  test('a beat on the track is a link to its frame; hover and keyboard focus show its name', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 700 });
    await page.goto('/');
    await goTo(page, 'hero');
    const track = page.getByRole('navigation', { name: 'The claim, beat by beat' });
    const review = track.getByRole('link', { name: /^Panel\b.*beat 5 of 6/ });
    await expect(review.locator('.beats-l')).toHaveCSS('opacity', '0');
    await review.hover();
    await expect(review.locator('.beats-l')).toHaveCSS('opacity', '1');
    await page.mouse.move(10, 400);
    await expect(review.locator('.beats-l')).toHaveCSS('opacity', '0');
    // keyboard: Tab from the beat before it focuses it and shows its name
    await track.getByRole('link', { name: /^QE\b/ }).focus();
    await page.keyboard.press('Tab');
    await expect(review).toBeFocused();
    await expect(review.locator('.beats-l')).toHaveCSS('opacity', '1');
    await page.keyboard.press('Enter');
    await expect(page).toHaveURL(/#panel$/);
    await expect(track.locator('[aria-current="step"] .beats-l')).toHaveText('Panel');
    // garden's frames start at the window's top (the bar sits over each frame's own top padding)
    await expect.poll(() => page.evaluate(() => Math.round(document.getElementById('panel')!.getBoundingClientRect().top))).toBe(0);
  });

  test('below 1400px the track is hidden and below 1024px the thread too; past the last beat both fade', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/');
    await goTo(page, 'toolkit');
    await expect(page.locator('[data-beat-thread]')).not.toHaveClass(/is-on/);
    await expect(page.locator('[data-beats]')).toBeHidden();
    await expect(page.locator('[data-beat-thread]')).toHaveCSS('opacity', '0');
    await page.setViewportSize({ width: 1024, height: 768 });
    await goTo(page, 'graph');
    await expect(page.locator('[data-beat-thread]')).toBeVisible();
    await expect(page.locator('[data-beats]')).toBeHidden();
    await page.setViewportSize({ width: 768, height: 1024 });
    await goTo(page, 'graph');
    await expect(page.locator('[data-beat-thread]')).toBeHidden();
    await expect(page.locator('[data-beats]')).toBeHidden();
  });
});
