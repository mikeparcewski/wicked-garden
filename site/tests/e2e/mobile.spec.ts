import { test, expect } from '@playwright/test';

/**
 * Mobile smoke at iPhone 12 dimensions (390x844). The viewport is set
 * explicitly instead of spreading devices['iPhone 12'] because that device
 * descriptor carries defaultBrowserType: 'webkit', which would silently move
 * the test off the cached Chromium build.
 */
test.use({
  viewport: { width: 390, height: 844 },
  isMobile: true,
  hasTouch: true,
});

test('mobile: page renders, hero island visible, hamburger menu opens', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('h1')).toContainText('The tools your coding agent');

  // The hero island has no mobile fallback — the grid collapses to one column
  // and the HeroStamp card renders below the pitch (site.css @max-width:1000px).
  const card = page.locator('.hs-card');
  await card.scrollIntoViewIfNeeded();
  await expect(card).toBeVisible();
  await expect(card.locator('.hs-claim')).not.toBeEmpty();

  // The qe wall stands up on a phone: writer and executor stacked, the lanes drop through a
  // horizontal wall, then the reviewer.
  const qe = page.locator('#qe');
  await qe.scrollIntoViewIfNeeded();
  await expect(qe.locator('.qw-role')).toHaveCount(3);
  await expect(qe.locator('.qw-wall')).toBeVisible();
  await expect(qe.locator('.qw-track')).toBeVisible();
  const [exe, wall, rev] = await Promise.all(['[data-role="executor"]', '.qw-wall', '[data-role="reviewer"]'].map((s) =>
    qe.locator(s).evaluate((el) => el.getBoundingClientRect().top)));
  expect(exe).toBeLessThan(wall);
  expect(wall).toBeLessThan(rev);

  // The catalog's domains scroll sideways in their own row (never a squashed 4-column grid).
  const tabs = page.locator('#toolkit .cx-tabs');
  expect(await tabs.evaluate((el) => getComputedStyle(el).display)).toBe('flex');
  expect(await tabs.evaluate((el) => el.scrollWidth > el.clientWidth)).toBe(true);

  // Nothing in main is cut by the viewport edge, outside its own scroller.
  const clipped = await page.evaluate(() => {
    const out: string[] = [];
    for (const el of Array.from(document.querySelectorAll('main *'))) {
      const r = el.getBoundingClientRect();
      if (!r.width || (r.right <= innerWidth + 1 && r.left >= -1)) continue;
      // only a container the visitor can scroll excuses it; a hidden or clip box would just cut it off
      let p = el.parentElement, inScroller = false;
      while (p && p !== document.body) { if (/(auto|scroll)/.test(getComputedStyle(p).overflowX) && p.scrollWidth > p.clientWidth && p.getBoundingClientRect().right <= innerWidth + 1) { inScroller = true; break; } p = p.parentElement; }
      if (!inScroller) out.push(`${el.tagName}.${String((el as HTMLElement).className).split(' ')[0]}`);
    }
    return out;
  });
  expect(clipped).toEqual([]);

  // No horizontal overflow — the page must not scroll sideways on a phone.
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);

  // Mobile chrome: inline nav collapses behind the hamburger; menu opens.
  const menuBtn = page.locator('#menuBtn');
  await expect(menuBtn).toBeVisible();
  await menuBtn.click();
  await expect(page.locator('#mobileMenu')).toBeVisible();
  // the menu's first row is Wicked Labs (the flask's link), not a list of the product sites
  await expect(page.locator('#mobileMenu').getByRole('link', { name: /Wicked Labs/ })).toHaveAttribute('href', 'https://wickedlabs.ai/');
  await expect(page.locator('#mobileMenu').getByRole('link', { name: /Wicked Labs/ })).toBeVisible();
  // every row's glyph sits on its label's line, not above it
  const off = await page.locator('#mobileMenu .mm-label').evaluateAll((labels) => labels.map((l) => {
    const g = l.querySelector('.mm-glyph')!.getBoundingClientRect();
    const r = document.createRange(); r.selectNodeContents(l); const t = Array.from(r.getClientRects()).filter((q) => q.width > 0);
    const text = t[t.length - 1];
    const mid = (g.top + g.bottom) / 2;
    return mid >= text.top && mid <= text.bottom ? null : `${l.textContent!.trim()}: glyph ${Math.round(g.top)}-${Math.round(g.bottom)}, text ${Math.round(text.top)}-${Math.round(text.bottom)}`;
  }).filter(Boolean));
  expect(off).toEqual([]);
});

for (const width of [390, 360, 320]) {
  test(`mobile ${width}px: the product path keeps the mark, never pushes the icons, and the mark shows no lettering`, async ({ page }) => {
    await page.setViewportSize({ width, height: 740 });
    await page.goto('/');
    await page.evaluate(async () => { await document.fonts.ready; });
    const g = await page.evaluate(() => {
      const box = (s: string) => { const r = document.querySelector(s)!.getBoundingClientRect(); return { l: r.left, r: r.right, t: r.top, b: r.bottom }; };
      const name = document.querySelector<HTMLElement>('.crumbs li:last-child .crumb')!, ns = getComputedStyle(name);
      return { mark: box('.crumbs .wordmark'), art: box('.crumbs .wordmark .wordmark-lockup'), clip: getComputedStyle(document.querySelector('.crumbs .wordmark .wordmark-lockup')!).clipPath,
               path: box('.crumbs'), nav: box('.topbar .nav'), name: box('.crumbs li:last-child .crumb'), named: name.textContent!.trim(), vw: innerWidth,
               sep: box('.crumbs li:nth-child(2) .crumb-sep'), labs: box('.crumbs li:nth-child(2) .crumb'),
               cut: name.scrollWidth > name.clientWidth + 1, ellipsis: ns.textOverflow === 'ellipsis' && ns.overflowX === 'hidden' && !/flex|grid/.test(ns.display) };
    });
    // a cut product name ends in the chrome's ellipsis (a flex box would hard-cut it)
    if (g.cut) expect(g.ellipsis, 'the product name is cut without an ellipsis').toBe(true);
    // the 44px targets keep the chrome's spacing: the first slash 8px after the clipped mark (22px of artwork)
    expect(Math.abs(g.sep.l - (g.art.l + 22 + 8))).toBeLessThanOrEqual(1.5);
    // the mark sits inside the window and the path ends before the icons
    expect(g.mark.l).toBeGreaterThanOrEqual(0);
    expect(g.path.r).toBeLessThanOrEqual(g.nav.l);
    expect(g.name.r).toBeLessThanOrEqual(g.nav.l);
    expect(g.named).toBe('wicked-garden');
    // the artwork is clipped to its first 22px (the mark; the lettering starts past 25px)
    expect(g.clip).toMatch(/^inset\(.*22px/);
    expect(g.art.l).toBeGreaterThanOrEqual(g.mark.l);
    expect(g.nav.r).toBeLessThanOrEqual(g.vw);
  });
}

for (const vp of [{ width: 390, height: 844 }, { width: 360, height: 740 }, { width: 320, height: 740 }]) {
  test(`mobile ${vp.width}x${vp.height}: the hero stats read as text, each number spaced from its word and on its row`, async ({ page }) => {
    await page.setViewportSize(vp);
    await page.goto('/');
    await page.evaluate(async () => { await document.fonts.ready; });
    const stats = page.locator('.gd-hero-stats');
    await expect(stats).toContainText(/\d+ work-shapes/);
    const g = await stats.evaluate((ul) => Array.from(ul.querySelectorAll('li')).filter((li) => li.querySelector('b')).map((li) => {
      const b = li.querySelector('b')!;
      // the gap between the number and the first letter after it, as painted (a dropped space is a 0px gap)
      const walk = document.createTreeWalker(li, NodeFilter.SHOW_TEXT);
      let n: Node | null, first: DOMRect | null = null;
      while ((n = walk.nextNode())) {
        if (b.contains(n)) continue;
        const i = n.textContent!.search(/\S/);
        if (i < 0) continue;
        const r = document.createRange(); r.setStart(n, i); r.setEnd(n, i + 1);
        first = r.getBoundingClientRect(); break;
      }
      const nb = b.getBoundingClientRect();
      return { text: li.textContent!.trim(), gap: first ? first.left - nb.right : null, base: nb.bottom };
    }));
    expect(g.length).toBeGreaterThanOrEqual(3);
    for (const s of g) if (s.gap !== null) expect(s.gap, `"${s.text}" fuses its number to its word`).toBeGreaterThan(2);
    // stats on one row share a text baseline (a 44px link box must not push its text below the row)
    const rows = new Map<number, number[]>();
    for (const s of g) { const k = [...rows.keys()].find((y) => Math.abs(y - s.base) < 30) ?? s.base; rows.set(k, [...(rows.get(k) ?? []), s.base]); }
    for (const bases of rows.values()) expect(Math.max(...bases) - Math.min(...bases)).toBeLessThanOrEqual(1);
  });

  test(`mobile ${vp.width}x${vp.height}: every control, chrome included, is a 44px target`, async ({ page }) => {
    await page.setViewportSize(vp);
    await page.goto('/');
    await page.evaluate(async () => { await document.fonts.ready; });
    const measure = () => page.evaluate(() => {
      const out: string[] = [];
      for (const el of Array.from(document.querySelectorAll<HTMLElement>('a[href], button, [role=tab], [role=switch], input'))) {
        const cs = getComputedStyle(el);
        // layout size (an entrance transform scales a stage to .98 until it is reached)
        if (!el.offsetWidth || !el.offsetHeight || cs.visibility === 'hidden' || el.closest('[hidden], [inert], .mobile-menu')) continue;
        // a link inside a sentence is exempt (WCAG 2.5.8): an inline element in a longer run of text
        const p = el.parentElement;
        const inline = cs.display === 'inline' && !!p && p.textContent!.trim().length > el.textContent!.trim().length + 12;
        if (!inline && (el.offsetWidth < 44 || el.offsetHeight < 44)) {
          out.push(`${el.tagName.toLowerCase()}.${String(el.className).split(' ')[0]} "${(el.getAttribute('aria-label') || el.textContent || '').trim().slice(0, 30)}" ${el.offsetWidth}x${el.offsetHeight}`);
        }
      }
      return out;
    });
    expect(await measure()).toEqual([]);
    // the hero card's controls stay inside the card (four 44px pips and Play wrap on the narrowest phones)
    const out = await page.locator('.hs-card').evaluate((card) => {
      const c = card.getBoundingClientRect();
      return Array.from(card.querySelectorAll('.hs-controls > *, .hs-pip')).filter((e) => {
        const r = e.getBoundingClientRect();
        return r.width > 0 && (r.left < c.left - 0.5 || r.right > c.right + 0.5);
      }).length;
    });
    expect(out).toBe(0);
    // and with the gate's "where it only advises" detail open (its close button is a target too)
    const where = page.locator('#gate .pg-where-btn');
    await where.scrollIntoViewIfNeeded();
    await where.click();
    await expect(page.locator('#gate .pg-advise')).toBeVisible();
    expect(await measure()).toEqual([]);
  });
}
