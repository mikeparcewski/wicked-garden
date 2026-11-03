import { test, expect } from '@playwright/test';
import { expectRevealed, clickCopyChip, hydrated } from './utils';

/**
 * Smoke coverage for the React islands mounted on index.astro (all
 * client:load): HeroStamp, ProveGate, GraphStage, CatalogExplorer, ExtendPack,
 * InstallBench, CopyChip — plus the shared SameGarden platform map. PanelVote and
 * MemoryQueue are in panels.spec.ts. The two
 * qe-domain islands (QeWall, QeFleet) have their own spec (qe.spec.ts).
 * Each test asserts the island (a) renders and (b) responds to one
 * representative interaction.
 */

// Clipboard permissions so CopyChip's navigator.clipboard.writeText resolves
// (the component swallows clipboard errors, so without this the "copied"
// feedback never appears).
test.use({ permissions: ['clipboard-read', 'clipboard-write'] });

test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await hydrated(page);
});

test('hero renders headline, capability-plane stats, and install command', async ({ page }) => {
  await expect(page).toHaveTitle(/wicked-garden — the tools your coding agent/);
  await expect(page.locator('h1')).toContainText('The tools your coding agent');
  await expect(page.locator('.gd-hero-stats')).toContainText(/\d{2,} skills/);
  await expect(page.locator('.gd-hero-stats')).toContainText('40');
  await expect(page.locator('#hero .kicker').first()).toContainText('skill catalog');
  await expect(
    page.locator('#hero').getByRole('button', { name: 'Copy command: npx wicked-installer' }),
  ).toBeVisible();
});

test('HeroStamp: renders and pinning a claim shows its verdict', async ({ page }) => {
  const card = page.locator('.hs-card');
  await card.scrollIntoViewIfNeeded();
  await expect(card).toBeVisible();
  await expect(card.getByRole('tab')).toHaveCount(4);

  // Interaction: pick claim 2 ("reviewed — safe to merge" → PROVED, the word the gate below stamps).
  const pip = card.getByRole('tab', { name: /^claim 2/ });
  await pip.click();
  await expect(pip).toHaveAttribute('aria-selected', 'true');
  await expect(card.locator('.hs-afford')).toContainText('driving');
  await expect(card.locator('.hs-claim')).toContainText('reviewed');
  // asserting → stamped after ~1.1s; the pinned claim keeps its stamp.
  await expect(card.locator('.hs-mark')).toContainText('PROVED');
  await expect(card.locator('.hs-head-r')).toHaveText('checked');
});

test('GraphStage: on the retry change, grep finds three files, the estate graph adds the event consumer, the rename lands in 3', async ({ page }) => {
  const graph = page.locator('#graph');
  await graph.scrollIntoViewIfNeeded();
  const stage = graph.getByRole('group', { name: /grep against the estate graph/ });
  await stage.getByRole('button', { name: 'grep', exact: true }).click();
  await expect(graph.locator('.gx-impact .gx-result')).toContainText('3 hits');
  await expect(graph.locator('.gx-afford')).toContainText('driving');
  await stage.getByRole('button', { name: 'estate graph' }).click();
  await expect(graph.locator('.gx-tag')).toHaveClass(/is-on/);
  await expect(graph.locator('.gx-impact .gx-result')).toContainText('notify.ts');
  await expect(graph.locator('.gx-impact .gx-result')).toContainText('4 files affected');
  await stage.getByRole('button', { name: /rename maxRetry → maxRetries/ }).click();
  await expect(graph.locator('.gx-new').first()).toBeVisible();
  // the old and new names are separate words with an arrow between them, never fused
  expect((await graph.locator('.gx-file').first().innerText()).replace(/\s+/g, ' ')).toContain('maxRetry → maxRetries');
  // the rename's count and the blast radius agree: notify.ts reads the event, not the field
  await expect(graph.locator('.gx-patch .gx-result')).toContainText('3 files touched');
  await expect(graph.locator('.gx-patch .gx-result')).toContainText('notify.ts reads the event, not the field');
  // README-style skill calls, pasted into an agent (not shell commands)
  await expect(graph.getByRole('button', { name: 'Copy skill call: /wicked-garden-search blast-radius maxRetry' })).toBeVisible();
  await expect(graph.getByRole('button', { name: 'Copy skill call: /wicked-garden-engineering-patch rename maxRetry maxRetries' })).toBeVisible();
  await graph.getByRole('button', { name: /resume auto-play/ }).click();
  await expect(graph.locator('.gx-afford')).toContainText('auto-playing');
});

test('ProveGate: the bench opens on the hero\'s claim and stamps it REJECTED first (the story never says PROVED first)', async ({ page }) => {
  const gate = page.locator('#gate');
  await gate.scrollIntoViewIfNeeded();
  const machine = gate.getByRole('region', { name: /Evidence gate/ });
  await expect(machine.locator('.pg-claim-v')).toHaveText('the retry change: all acceptance tests pass');
  await expect(machine.getByRole('switch', { name: /verifier actually ran/ })).toHaveAttribute('aria-checked', 'false');
  await expect(machine.locator('.pg-mark-word')).toHaveText('REJECTED', { timeout: 8_000 });
  await expect(machine.locator('.pg-mark-at')).toHaveText('failed at: verifier');
});

test('ProveGate: turning reduced motion on never runs a bench the visitor armed', async ({ page }) => {
  const gate = page.locator('#gate');
  await gate.scrollIntoViewIfNeeded();
  const machine = gate.getByRole('region', { name: /Evidence gate/ });
  await machine.getByRole('button', { name: 'reset the bench' }).click();
  await expect(machine.locator('.pg-state')).toHaveText('gate: armed');
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.waitForTimeout(600);
  await expect(machine.locator('.pg-state')).toHaveText('gate: armed');
  await expect(machine.getByRole('button', { name: 'Pull the PROVE lever' })).toBeEnabled();
});

test('ProveGate: driving the gate re-derives PROVED, breaking the vault FAILS CLOSED', async ({
  page,
}) => {
  const gate = page.locator('#gate');
  await gate.scrollIntoViewIfNeeded();
  const machine = gate.getByRole('region', { name: /Evidence gate/ });
  await expect(machine).toBeVisible();
  await expect(machine.getByRole('switch')).toHaveCount(4);

  // Take control deterministically: reset stops auto-play and re-arms the bench.
  await machine.getByRole('button', { name: 'reset the bench' }).click();
  await expect(gate.locator('.pg-afford')).toContainText('driving the gate');

  // All four conditions hold → PROVED.
  const lever = machine.getByRole('button', { name: 'Pull the PROVE lever' });
  await lever.click();
  await expect(machine.locator('.pg-mark-word')).toHaveText('PROVED');

  // Break the vault condition → the gate FAILS CLOSED (never a vacuous pass); the trail names the check.
  const vault = machine.getByRole('switch', { name: /vault backend present/ });
  await vault.click();
  await expect(vault).toHaveAttribute('aria-checked', 'false');
  await lever.click();
  await expect(machine.locator('.pg-mark-word')).toHaveText('FAILS CLOSED');
  await expect(machine.locator('.pg-mark-at')).toHaveText('failed at: vault');
  await expect(machine.locator('.pg-chip').first()).toHaveClass(/is-fail/);
  await expect(machine.locator('.pg-chip').nth(1)).toHaveClass(/is-skip/);
});

test('ProveGate: the where-it-advises detail opens inside the machine and never grows the frame', async ({ page }) => {
  const gate = page.locator('#gate');
  await gate.scrollIntoViewIfNeeded();
  const before = await gate.evaluate((el) => el.getBoundingClientRect().height);
  const btn = gate.getByRole('button', { name: 'where it only advises' });
  await btn.click();
  await expect(btn).toHaveAttribute('aria-expanded', 'true');
  const panel = gate.getByRole('region', { name: 'Where the gate only advises' });
  await expect(panel).toBeVisible();
  await expect(panel).toContainText('skills-only hosts (Codex, OpenCode, Pi, Antigravity) have no hooks');
  expect(await gate.evaluate((el) => el.getBoundingClientRect().height)).toBe(before);
  // it takes the bench's place: the bench is hidden, not covered, so no bench text shows under or around it
  for (const sel of ['.pg-head', '.pg-switch', '.pg-chip', '.pg-foot']) await expect(gate.locator(sel).first()).toBeHidden();
  const under = await gate.evaluate((sec) => {
    const pr = sec.querySelector('.pg-advise')!.getBoundingClientRect();
    return Array.from(sec.querySelectorAll('.pg-inner *')).filter((e) => {
      const cs = getComputedStyle(e);
      if (cs.visibility === 'hidden' || Number(cs.opacity) < 0.05 || !Array.from(e.childNodes).some((n) => n.nodeType === 3 && n.textContent!.trim())) return false;
      let p = e.parentElement; while (p && p !== sec) { if (Number(getComputedStyle(p).opacity) < 0.05) return false; p = p.parentElement; }
      const r = e.getBoundingClientRect();
      return r.width > 0 && r.right > pr.left && r.left < pr.right && r.bottom > pr.top && r.top < pr.bottom;
    }).length;
  });
  expect(under).toBe(0);
  await page.keyboard.press('Escape');
  await expect(panel).toBeHidden();
  await expect(btn).toBeFocused();
});

test('CatalogExplorer: the skill families as tabs, qe selected first, arrow keys and the task filter', async ({ page }) => {
  const cat = page.locator('#toolkit');
  await cat.scrollIntoViewIfNeeded();
  // hold the tour (it pauses under the pointer) so the first state is the resting one
  await cat.locator('.cx-stage').hover();
  // no family count: the tab list is a grouping, not a measured number (N9)
  await expect(cat.getByRole('heading', { name: /\d{2,} skills, by what they do\./ })).toBeVisible();
  const tabs = cat.getByRole('tab');
  await expect(tabs).toHaveCount(14);
  // the retired context (smaht) domain is gone; grounding has its own family
  await expect(cat.locator('#dom-smaht')).toHaveCount(0);
  await expect(cat.getByRole('tab', { name: 'grounding' })).toBeVisible();
  const qe = cat.getByRole('tab', { name: 'quality engineering' });
  await expect(qe).toHaveAttribute('aria-selected', 'true');
  const qePanel = cat.locator('#cx-panel-qe');
  await expect(qePanel).toBeVisible();
  await expect(qePanel.getByRole('link', { name: /the wall/ })).toHaveAttribute('href', '#qe');
  await expect(qePanel.getByRole('button', { name: 'Copy skill call: /wicked-garden-qe' })).toBeVisible();
  // no hover trays: the detail is a panel in the frame; the arrow key moves the selection
  await qe.focus();
  await page.keyboard.press('ArrowRight');
  await expect(cat.getByRole('tab', { name: 'product & UX' })).toBeFocused();
  await expect(cat.getByRole('tab', { name: 'product & UX' })).toHaveAttribute('aria-selected', 'true');
  await expect(cat.locator('#cx-panel-product')).toBeVisible();
  await expect(qePanel).toBeHidden();
  // type a task: the matching domains light, the rest dim
  await cat.getByLabel('type a task').fill('rename across files');
  await expect(cat.locator('#dom-engineering')).toHaveClass(/is-hit/);
  await expect(cat.locator('#dom-persona')).toHaveClass(/is-miss/);
  await expect(cat.locator('.cx-peer')).toHaveCount(4);
  await expect(cat.locator('.cx-peer').first()).toContainText('wicked-estate');
  // the gate's one required peer is named as required, never as opt-in
  await expect(cat.locator('.cx-peer.is-required')).toContainText('wicked-vault');
  await expect(cat.locator('.cx-family-lead')).toContainText('without it the gate fails closed');
});

test('CatalogExplorer: a task the visitor types opens its best match, so the open family is always a highlighted one', async ({ page }) => {
  const cat = page.locator('#toolkit');
  await cat.scrollIntoViewIfNeeded();
  await cat.locator('.cx-stage').hover();
  await expect(cat.getByRole('tab', { name: 'quality engineering' })).toHaveAttribute('aria-selected', 'true');
  for (const task of ['rename a function', 'audit a deploy', 'test a11y']) {
    await cat.getByLabel('type a task').fill(task);
    const open = cat.locator('.cx-tab[aria-selected="true"]');
    await expect(open).toHaveClass(/is-hit/);
    // and its panel is the one showing
    const id = (await open.getAttribute('id'))!.slice(4);
    await expect(cat.locator(`#cx-panel-${id}`)).toBeVisible();
  }
  // a family picked after typing stays open while the best match is unchanged
  await cat.locator('#dom-data').click();
  await expect(cat.locator('#dom-data')).toHaveAttribute('aria-selected', 'true');
  // clearing the task keeps the visitor's pick
  await cat.getByLabel('type a task').fill('');
  await expect(cat.locator('#dom-data')).toHaveAttribute('aria-selected', 'true');
});

test('CatalogExplorer: the tour types a task, lights its matches and opens the first; a click takes over', async ({ page }) => {
  const cat = page.locator('#toolkit');
  await cat.scrollIntoViewIfNeeded();
  await page.mouse.move(2, 2);
  await expect.poll(() => cat.locator('.cx-tab.is-hit').count(), { timeout: 8_000 }).toBeGreaterThan(0);
  await expect(cat.locator('.cx-find-in')).toHaveAttribute('placeholder', /▍$/);
  await expect(cat.getByRole('button', { name: 'Pause the catalog tour' })).toBeVisible();
  await cat.locator('#dom-data').click();
  await expect(cat.getByRole('button', { name: /resume tour/ })).toBeVisible();
  await page.mouse.move(2, 2);
  await page.waitForTimeout(3_000);
  await expect(cat.locator('#dom-data')).toHaveAttribute('aria-selected', 'true');
});

test("What's new: the domain-mapping item selects the domain in the catalog, every time it is followed", async ({ page }) => {
  const link = page.locator('#memory .mq-new-list a');
  await link.scrollIntoViewIfNeeded();
  await link.click();
  await expect(page.locator('#dom-domain')).toHaveAttribute('aria-selected', 'true');
  // pick another domain, then follow the same link again: the URL already says #dom-domain (no hashchange)
  await page.locator('#dom-qe').click();
  await expect(page.locator('#dom-qe')).toHaveAttribute('aria-selected', 'true');
  await link.scrollIntoViewIfNeeded();
  await link.click();
  await expect(page.locator('#dom-domain')).toHaveAttribute('aria-selected', 'true');
});

test('ExtendPack: the extension pitch renders scaffold, rules, and the compile chip', async ({
  page,
}) => {
  const xp = page.locator('#extend');
  await xp.scrollIntoViewIfNeeded();
  await expect(xp.getByRole('heading', { name: /Your domain\. Your pack\./ })).toBeVisible();
  await expectRevealed(xp.getByRole('heading', { name: /Your domain\. Your pack\./ }));
  // the pack layout: the manifest, then the {vendor}-{domain} router and {vendor}-{domain}-{role} workers
  await expect(xp.locator('.xp-row')).toHaveCount(4);
  await expect(xp.locator('.xp-dir').first()).toHaveText('wicked-pack.json');
  await expect(xp.locator('.xp-rule')).toHaveCount(3);
  // pick another pack: the scaffold retypes and each rule lights as its row lands
  await xp.getByRole('radio', { name: 'compliance' }).click();
  await expect(xp.locator('.xp-dir').nth(1)).toHaveText('skills/acme-compliance/');
  await expect(xp.locator('.xp-rule.is-lit')).toHaveCount(3);
  await expect(xp.getByRole('button', { name: /resume/ })).toBeVisible();
  // Interaction: copy the shipped conformance gate.
  await clickCopyChip(
    xp.getByRole('button', { name: 'Copy command: npx wicked-garden pack check .' }),
  );
});

test('SameGarden platform map: four planes render, garden is "you are here"', async ({ page }) => {
  const map = page.locator('#platform-map');
  await map.scrollIntoViewIfNeeded();
  await expect(map.locator('.sg-plane')).toHaveCount(4);
  // garden's own card never self-promotes — it renders as the here-marker
  // inside the capability plane.
  const capability = map.locator('.sg-plane--capability');
  await expect(capability).toContainText('wicked-garden');
  await expect(capability.locator('.sg-here-chip')).toContainText('you are here');
  // the other planes still link out
  await expect(
    map.locator('.sg-plane--foundation').getByRole('link', { name: /Visit wicked-estate/ }),
  ).toBeVisible();
});

test('InstallBench: renders both install paths; copy chip gives feedback', async ({ page }) => {
  const bench = page.locator('#install');
  await bench.scrollIntoViewIfNeeded();
  await expect(bench.getByRole('heading', { name: /One command/ })).toBeVisible();
  await expectRevealed(bench.getByRole('heading', { name: /One command/ }));

  // The direct path is the second tab; both panels share one reserved cell.
  const before = await bench.evaluate((el) => el.getBoundingClientRect().height);
  await bench.getByRole('tab', { name: 'just this plugin' }).click();
  expect(await bench.evaluate((el) => el.getBoundingClientRect().height)).toBe(before);
  const chip = bench.getByRole('button', {
    name: 'Copy command: claude plugins install wicked-garden',
  });
  await clickCopyChip(chip);
});

test('CopyChip: copying never moves or cuts the command', async ({ page }) => {
  for (const vp of [{ width: 1440, height: 700 }, { width: 360, height: 740 }]) {
    await page.setViewportSize(vp);
    for (const sel of ['#install .cc', '#hero .hs-foot .cc', '#graph .gx-patch .cc', '#extend .xp-cta .cc']) {
      const chip = page.locator(sel).first();
      await chip.evaluate((el) => el.scrollIntoView({ block: 'center', behavior: 'instant' as ScrollBehavior }));
      const box = () => chip.locator('.cc-cmd').evaluate((el) => {
        const r = el.getBoundingClientRect();
        return { x: Math.round(r.left), w: Math.round(r.width), h: Math.round(r.height), cut: el.scrollWidth > el.clientWidth + 1 };
      });
      const before = await box();
      expect(before.cut, `${sel} cut at rest at ${vp.width}`).toBe(false);
      await chip.click();
      await expect(chip).toContainText('copied');
      expect(await box(), `${sel} moved when copied at ${vp.width}`).toEqual(before);
    }
  }
});

test('CopyChip: click copies the command to the clipboard', async ({ page }) => {
  const chip = page
    .locator('#hero')
    .getByRole('button', { name: 'Copy command: npx wicked-installer' });
  await clickCopyChip(chip);
  await expect
    .poll(() => page.evaluate(() => navigator.clipboard.readText()))
    .toBe('npx wicked-installer');
});
