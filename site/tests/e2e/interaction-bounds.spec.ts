import { test, expect, type Page } from '@playwright/test';

/**
 * Interactions never cause page display issues (operator criterion 6). The bug this guards: hovering
 * the bottom rows of the old catalog grid opened absolutely positioned skill trays that slid UNDER the
 * text below them (a later sibling Reveal kept `will-change` on and painted over the tray).
 *
 * 1. Every element the stylesheets give a :hover or :focus rule (plus every control) is hovered and
 *    focused. Its painted box (the element and its visible descendants) is compared with its resting
 *    box. Where it grows by more than 2px, the part beyond the resting box must not intersect text
 *    outside the element (the paint-order probe asks elementFromPoint with the hovered subtree made
 *    hit-testable, since trays are pointer-events:none) and must not cross its section.
 * 2. While each section's demo auto-plays (and it must visibly change state), no section top or height may
 *    move and no visible text may intersect other text in the section.
 * 3. Every toggle (roles, flips, filters, switches, tabs, picks, the advise overlay) is clicked: again nothing
 *    may move and no text may cover other text.
 * Five sizes; the hover/focus pass in both themes, the motion passes in the dark theme (geometry is theme-independent).
 */

const VIEWPORTS = [
  { width: 1440, height: 700 },
  { width: 1280, height: 660 },
  { width: 1920, height: 1080 },
  { width: 390, height: 844 },
  { width: 360, height: 740 },
];
const THEMES = ['dark', 'light'] as const;

async function open(page: Page, vp: { width: number; height: number }, theme: string) {
  await page.setViewportSize(vp);
  await page.addInitScript((t) => { try { localStorage.setItem('wa-theme-v3', t); } catch { /* storage off */ } }, theme);
  await page.goto('/');
  await page.evaluate(async () => { await document.fonts.ready; });
  // walk the page so every Reveal plays its entrance, then wait for each to settle
  await page.evaluate(async () => {
    const H = document.documentElement.scrollHeight;
    for (let y = 0; y < H; y += innerHeight / 2) {
      window.scrollTo({ top: y, behavior: 'instant' as ScrollBehavior });
      await new Promise((r) => setTimeout(r, 40));
    }
    window.scrollTo({ top: 0, behavior: 'instant' as ScrollBehavior });
  });
  await expect
    .poll(() => page.evaluate(() => document.querySelectorAll('[data-reveal]:not([data-reveal="shown"])').length), { timeout: 8_000 })
    .toBe(0);
}

/** Tag every candidate with data-ib=<n>; return how many. */
async function tagCandidates(page: Page): Promise<number> {
  return page.evaluate(() => {
    const bases = new Set<string>();
    const walk = (rules: CSSRuleList) => {
      for (const r of Array.from(rules)) {
        const g = r as CSSGroupingRule & { selectorText?: string };
        if (!g.selectorText && g.cssRules) { walk(g.cssRules); continue; }
        if (!g.selectorText) continue;
        for (const part of g.selectorText.split(',')) {
          const m = part.match(/^(.*?)(:hover|:focus-visible|:focus-within|:focus)/);
          if (!m) continue;
          const comp = m[1].trim().split(/[\s>+~]+/).pop();
          if (comp && comp !== '*' && comp !== '&') bases.add(comp);
        }
      }
    };
    for (const ss of Array.from(document.styleSheets)) { try { walk(ss.cssRules); } catch { /* cross-origin */ } }
    const els = new Set<Element>(document.querySelectorAll('main a[href], main button, main [role="tab"], main [role="switch"], main input, main [tabindex]:not([tabindex="-1"])'));
    for (const b of bases) { try { document.querySelectorAll(`main ${b}`).forEach((e) => els.add(e)); } catch { /* not a selector */ } }
    let n = 0;
    for (const el of els) {
      const r = el.getBoundingClientRect();
      const cs = getComputedStyle(el);
      if (!r.width || !r.height || cs.visibility === 'hidden' || cs.display === 'none') continue;
      if (el.closest('[aria-hidden="true"]')) continue;
      el.setAttribute('data-ib', String(n++));
    }
    return n;
  });
}

interface Probe { grew: number; hits: string[]; crosses: number }

/** Painted box now vs `rest`; when it grew, what it covers outside itself and whether it leaves its section. */
async function probe(page: Page, i: number, rest: number[] | null): Promise<{ box: number[]; p: Probe | null }> {
  return page.evaluate(([i, rest]) => {
    const el = document.querySelector(`[data-ib="${i}"]`) as HTMLElement;
    const shown = (e: Element) => { for (let n: Element | null = e; n && n !== document.documentElement; n = n.parentElement) { const cs = getComputedStyle(n); if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) < 0.05) return false; } return true; };
    let u: number[] | null = null;
    for (const e of [el, ...Array.from(el.querySelectorAll('*'))]) {
      if (!shown(e)) continue;
      const r = e.getBoundingClientRect(); if (!r.width || !r.height) continue;
      u = u ? [Math.min(u[0], r.left), Math.min(u[1], r.top), Math.max(u[2], r.right), Math.max(u[3], r.bottom)] : [r.left, r.top, r.right, r.bottom];
    }
    const box = u ?? [0, 0, 0, 0];
    if (!rest) return { box, p: null };
    const grew = Math.max(rest[0] - box[0], rest[1] - box[1], box[2] - rest[2], box[3] - rest[3]);
    if (grew <= 2) return { box, p: { grew, hits: [], crosses: 0 } };
    const st = document.createElement('style');
    st.textContent = `[data-ib="${i}"], [data-ib="${i}"] * { pointer-events: auto !important; }`;
    document.head.appendChild(st);
    const hits: string[] = [];
    for (const t of Array.from(document.querySelectorAll('main *, footer *'))) {
      if (el.contains(t) || t.contains(el)) continue;
      if (!Array.from(t.childNodes).some((n) => n.nodeType === 3 && n.textContent!.trim())) continue;
      if (!shown(t)) continue;
      const r = t.getBoundingClientRect();
      const l = Math.max(r.left, box[0]), tp = Math.max(r.top, box[1]), rr = Math.min(r.right, box[2]), b = Math.min(r.bottom, box[3]);
      if (rr - l < 3 || b - tp < 3) continue;
      if (l >= rest[0] - 1 && rr <= rest[2] + 1 && tp >= rest[1] - 1 && b <= rest[3] + 1) continue;
      const x = (l + rr) / 2, y = (tp + b) / 2;
      if (x < 0 || y < 0 || x > innerWidth || y > innerHeight) continue;
      const top = document.elementFromPoint(x, y);
      const who = top && el.contains(top) ? 'covers' : top && (t === top || t.contains(top)) ? 'slides under' : 'overlaps';
      hits.push(`${who}: ${(t.textContent || '').trim().slice(0, 40)}`);
    }
    st.remove();
    const sec = el.closest('section, footer');
    const crosses = sec ? Math.max(0, Math.round(box[3] - sec.getBoundingClientRect().bottom), Math.round(sec.getBoundingClientRect().top - box[1])) : 0;
    return { box, p: { grew, hits: hits.slice(0, 4), crosses } };
  }, [i, rest] as const);
}

/** The sections whose demo plays by itself, and how long one full cycle of its states takes (ms): each is
 *  watched for that long, so its tallest state is reached (the QE inbox fills at 10.4s, the panel's third mode
 *  at 9.2s), and must show more than one state. */
const AUTOPLAY: Record<string, number> = {
  hero: 19_000, gate: 30_000, graph: 11_000, qe: 13_500, fleet: 16_000, panel: 14_000, memory: 9_000,
  toolkit: 11_000, extend: 15_000, install: 8_000,
};

/** The verdicts a full cycle must show: the hero cycles four claims, the gate four scripts. */
const VERDICTS: Record<string, { sel: string; words: string[] }> = {
  hero: { sel: '#hero .hs-word', words: ['REJECTED', 'PROVED', 'FAILS CLOSED'] },
  gate: { sel: '#gate .pg-mark-word', words: ['PROVED', 'REJECTED', 'FAILS CLOSED'] },
};

/** The motion passes also run at a narrow desktop, where the frames are tightest and snapping falls back. */
const MOTION_VIEWPORTS = [...VIEWPORTS, { width: 1024, height: 700 }];

/** Every control that switches a state: lit roles, flips, filters, switches, tabs, picks, the advise overlay. */
const TOGGLES = [
  '#hero .hs-pip:nth-child(3)', '#gate .pg-switch:nth-child(2)', '#gate .pg-lever', '#gate .pg-where-btn', '#gate .pg-advise-close',
  '#gate .pg-reset', '#graph .gx-seg-btn:nth-child(2)', '#graph .gx-rename-btn', '#qe .qw-role--writer .qw-role-btn',
  '#qe .qw-role--executor .qw-role-btn', '#qe .qw-btn', '#fleet .qf-btn[data-surf="execute"]', '#fleet .qf-btn[data-surf="insight"]',
  '#panel .pv-opt:nth-child(3)', '#panel .pv-opt:nth-child(2)', '#memory .mq-btn--ok', '#memory .mq-btn--drop', '#toolkit #dom-product',
  '#toolkit #dom-work-shapes', '#toolkit #dom-qe', '#extend .xp-pick:nth-child(3)', '#install #ib-tab-plugin',
  '#gate .pg-switch:nth-child(3)', '#gate .pg-switch:nth-child(4)', '#install .cc', '#extend .xp-cta .cc',
];

async function sectionBoxes(page: Page) {
  return page.evaluate(() => Array.from(document.querySelectorAll('main > section')).map((s) => {
    const r = s.getBoundingClientRect();
    return [s.id, Math.round(r.top + scrollY), Math.round(r.height)] as [string, number, number];
  }));
}

/** Visible text in a section that intersects other visible text (a moving chip over a label, a regrouping tile
 *  over its neighbour, copy squeezed into the next box). Each line fragment of an inline element is its own box;
 *  pairs that turn together under one transform are one piece; inert content (what an open overlay covers and
 *  takes out of reach, an unselected panel) is not on the page for this purpose. */
async function textOverlaps(page: Page, id: string): Promise<string[]> {
  return page.evaluate((id) => {
    const sec = document.getElementById(id)!;
    // what can paint: the box cut down by every clipping ancestor up to the section
    const visible = (e: Element, r: DOMRect) => {
      let l = r.left, t = r.top, rr = r.right, b = r.bottom;
      for (let n = e.parentElement; n && n !== sec.parentElement; n = n.parentElement) {
        const cs = getComputedStyle(n);
        if (cs.overflowX === 'visible' && cs.overflowY === 'visible') continue;
        const c = n.getBoundingClientRect();
        l = Math.max(l, c.left); t = Math.max(t, c.top); rr = Math.min(rr, c.right); b = Math.min(b, c.bottom);
      }
      return new DOMRect(l, t, Math.max(0, rr - l), Math.max(0, b - t));
    };
    const shown = (e: Element) => { if (e.closest('[inert]')) return false; for (let n: Element | null = e; n && n !== sec; n = n.parentElement) { const cs = getComputedStyle(n); if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) < 0.3) return false; } return true; };
    const turned = (e: Element) => { for (let n: Element | null = e; n && n !== sec; n = n.parentElement) { if (getComputedStyle(n).transform !== 'none') return n; } return null; };
    const items: { e: Element; rs: DOMRect[]; t: Element | null }[] = [];
    for (const e of Array.from(sec.querySelectorAll('*'))) {
      if (!Array.from(e.childNodes).some((n) => n.nodeType === 3 && n.textContent!.trim())) continue;
      if (!shown(e)) continue;
      const rs = Array.from(e.getClientRects()).map((r) => visible(e, r)).filter((r) => r.width >= 2 && r.height >= 2 && r.bottom > 0 && r.top < innerHeight);
      if (rs.length) items.push({ e, rs, t: turned(e) });
    }
    const out: string[] = [];
    for (let i = 0; i < items.length; i++) for (let j = i + 1; j < items.length; j++) {
      const a = items[i], b = items[j];
      if (a.e.contains(b.e) || b.e.contains(a.e)) continue;
      if (a.t && a.t === b.t) continue;
      let worst: [number, number] | null = null;
      for (const ra of a.rs) for (const rb of b.rs) {
        const w = Math.min(ra.right, rb.right) - Math.max(ra.left, rb.left), h = Math.min(ra.bottom, rb.bottom) - Math.max(ra.top, rb.top);
        if (w > 4 && h > 4) worst = [w, h];
      }
      if (worst) out.push(`"${(a.e.textContent || '').trim().slice(0, 24)}" over "${(b.e.textContent || '').trim().slice(0, 24)}" (${Math.round(worst[0])}x${Math.round(worst[1])})`);
    }
    return out.slice(0, 6);
  }, id);
}

for (const vp of VIEWPORTS) {
  for (const theme of THEMES) {
    test(`hover and focus stay inside their element at ${vp.width}x${vp.height} (${theme})`, async ({ page }) => {
      test.setTimeout(150_000);
      await open(page, vp, theme);
      // the final hover / focus state, not a frame of its transition
      await page.addStyleTag({ content: '*, *::before, *::after { transition-duration: 0s !important; transition-delay: 0s !important; }' });
      const n = await tagCandidates(page);
      expect(n, 'no interactive elements found').toBeGreaterThan(30);
      const problems: string[] = [];
      for (let i = 0; i < n; i++) {
        const el = page.locator(`[data-ib="${i}"]`);
        const name = await el.evaluate((e) => `${e.tagName.toLowerCase()}.${String((e as HTMLElement).className || '').split(' ')[0]} "${((e as HTMLElement).innerText || e.getAttribute('aria-label') || '').trim().slice(0, 30)}"`);
        await el.evaluate((e) => e.scrollIntoView({ block: 'center', behavior: 'instant' as ScrollBehavior }));
        await page.mouse.move(2, vp.height - 2);
        const rest = (await probe(page, i, null)).box;
        if (rest[2] - rest[0] < 1) continue;
        const cx = (rest[0] + rest[2]) / 2, cy = (rest[1] + rest[3]) / 2;
        if (cy > 0 && cy < vp.height && cx > 0 && cx < vp.width) {
          await page.mouse.move(cx, cy);
          const h = (await probe(page, i, rest)).p!;
          if (h.hits.length || h.crosses > 1) problems.push(`hover ${name}: grew ${h.grew}px, ${h.hits.join('; ')}${h.crosses > 1 ? `, crosses its section by ${h.crosses}px` : ''}`);
          await page.mouse.move(2, vp.height - 2);
        }
        const focusable = await el.evaluate((e) => (e as HTMLElement).tabIndex >= 0 || e.matches('a[href], button, input'));
        if (focusable) {
          await el.focus();
          const f = (await probe(page, i, rest)).p!;
          if (f.hits.length || f.crosses > 1) problems.push(`focus ${name}: grew ${f.grew}px, ${f.hits.join('; ')}${f.crosses > 1 ? `, crosses its section by ${f.crosses}px` : ''}`);
          await el.evaluate((e) => (e as HTMLElement).blur());
        }
      }
      expect(problems, problems.join('\n')).toEqual([]);
    });
  }
}

for (const vp of MOTION_VIEWPORTS) {
  test(`auto-play moves nothing and covers no text at ${vp.width}x${vp.height}`, async ({ page }) => {
    test.setTimeout(300_000);
    await open(page, vp, 'dark');
    const base = await sectionBoxes(page);
    const problems: string[] = [];
    for (const [id] of base.slice(0, -1)) {
      const cycle = AUTOPLAY[id] ?? 0;
      const playing = cycle > 0;
      // park so the section's demo is in view (a phone parks on the demo itself)
      await page.evaluate(([id, phone]) => {
        const s = document.getElementById(id as string)!;
        const target = (phone ? s.querySelector('.sx-stage, .gd-hero-demo') : null) ?? s;
        const tb = document.querySelector('.topbar')!.getBoundingClientRect().height;
        const r = target.getBoundingClientRect();
        window.scrollTo({ top: r.top + scrollY - (phone ? Math.max(tb, (innerHeight - r.height) / 2) : tb), behavior: 'instant' as ScrollBehavior });
      }, [id, vp.width < 1024] as const);
      await page.mouse.move(vp.width - 2, vp.height - 2);
      const seen = new Set<string>();
      const verdicts = new Set<string>();
      // watch a playing demo for one full cycle of its states
      const start = Date.now();
      const done = () => Date.now() - start > (playing ? cycle : 600);
      while (!done()) {
        await page.waitForTimeout(300);
        const cur = await sectionBoxes(page);
        cur.forEach((c, j) => {
          const b = base[j];
          if (Math.abs(b[1] - c[1]) > 1 || Math.abs(b[2] - c[2]) > 1) problems.push(`parked on #${id}: #${c[0]} top ${b[1]}->${c[1]} height ${b[2]}->${c[2]}`);
        });
        for (const o of await textOverlaps(page, id)) problems.push(`#${id}: ${o}`);
        seen.add(await page.evaluate((id) => (document.getElementById(id)!.querySelector('.sx-stage, .gd-hero-demo') as HTMLElement | null)?.innerText ?? '', id));
        if (VERDICTS[id]) { const w = await page.evaluate((sel) => document.querySelector(sel)?.textContent?.trim() ?? '', VERDICTS[id].sel); if (w) verdicts.add(w); }
      }
      // it really played: the demo showed more than one state while it was watched
      if (playing) expect(seen.size, `#${id} never changed state while on screen`).toBeGreaterThan(1);
      // and it went through every verdict it can show, each of which was checked for movement and overlap
      if (VERDICTS[id]) expect([...verdicts].sort(), `#${id} verdicts seen`).toEqual(expect.arrayContaining(VERDICTS[id].words));
    }
    expect([...new Set(problems)], [...new Set(problems)].slice(0, 10).join('\n')).toEqual([]);
  });

  test(`toggled states move nothing and cover no text at ${vp.width}x${vp.height}`, async ({ page }) => {
    test.setTimeout(120_000);
    await open(page, vp, 'dark');
    const base = await sectionBoxes(page);
    const problems: string[] = [];
    for (const sel of TOGGLES) {
      const el = page.locator(sel).first();
      if (!(await el.isVisible())) continue;
      await el.evaluate((e) => e.scrollIntoView({ block: 'center', behavior: 'instant' as ScrollBehavior }));
      await el.click();
      await page.waitForTimeout(1_300);
      const cur = await sectionBoxes(page);
      cur.forEach((c, j) => {
        const b = base[j];
        if (Math.abs(b[1] - c[1]) > 1 || Math.abs(b[2] - c[2]) > 1) problems.push(`after ${sel}: #${c[0]} top ${b[1]}->${c[1]} height ${b[2]}->${c[2]}`);
      });
      const id = await el.evaluate((e) => e.closest('section')!.id);
      for (const o of await textOverlaps(page, id)) problems.push(`after ${sel}: ${o}`);
    }
    expect([...new Set(problems)], [...new Set(problems)].slice(0, 10).join('\n')).toEqual([]);
  });
}
