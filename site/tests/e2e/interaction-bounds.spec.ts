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
 * 2. While each section's demo auto-plays, no section top and no section height may move.
 * Five sizes, both themes (the stability pass in the dark theme: auto-play is theme-independent).
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

  test(`auto-play never moves a section at ${vp.width}x${vp.height}`, async ({ page }) => {
    test.setTimeout(150_000);
    await open(page, vp, 'dark');
    const tops = () => page.evaluate(() => Array.from(document.querySelectorAll('main > section')).map((s) => {
      const r = s.getBoundingClientRect();
      return [s.id, Math.round(r.top + scrollY), Math.round(r.height)] as [string, number, number];
    }));
    const base = await tops();
    const tb = await page.evaluate(() => document.querySelector('.topbar')!.getBoundingClientRect().height);
    const moved: string[] = [];
    const parks = vp.width >= 1024 ? [0] : [0, 0.5];
    for (const [id] of base.slice(0, -1)) {
      for (const at of parks) {
        await page.evaluate(([id, tb, at]) => {
          const s = document.getElementById(id as string)!;
          window.scrollTo({ top: s.getBoundingClientRect().top + scrollY - (tb as number) + s.offsetHeight * (at as number), behavior: 'instant' as ScrollBehavior });
        }, [id, tb, at] as const);
        await page.mouse.move(vp.width - 2, vp.height - 2);
        for (let k = 0; k < 8; k++) {
          await page.waitForTimeout(280);
          const cur = await tops();
          cur.forEach((c, j) => {
            const b = base[j];
            if (Math.abs(b[1] - c[1]) > 1 || Math.abs(b[2] - c[2]) > 1) moved.push(`parked on #${id}: #${c[0]} top ${b[1]}->${c[1]} height ${b[2]}->${c[2]}`);
          });
        }
      }
    }
    expect([...new Set(moved)], moved.slice(0, 8).join('\n')).toEqual([]);
  });
}
