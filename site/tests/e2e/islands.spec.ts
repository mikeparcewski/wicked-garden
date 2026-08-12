import { test, expect } from '@playwright/test';
import { expectRevealed, clickCopyChip } from './utils';

/**
 * Smoke coverage for the React islands mounted on index.astro (all
 * client:load): HeroStamp, Toolbox, ProveGate, CapabilityGrid, ExtendPack,
 * InstallBench, CopyChip — plus the shared SameGarden platform map. The two
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
});

test('hero renders headline, capability-plane stats, and install command', async ({ page }) => {
  await expect(page).toHaveTitle(/wicked-garden/);
  await expect(page.locator('h1')).toContainText('The tools your coding agent');
  await expect(page.locator('.gd-hero-stats')).toContainText('141');
  await expect(page.locator('.gd-hero-stats')).toContainText('40');
  await expect(page.locator('#hero .kicker').first()).toContainText('capability plane');
  await expect(
    page.locator('#hero').getByRole('button', { name: 'Copy command: npx wicked-installer' }),
  ).toBeVisible();
});

test('HeroStamp: renders and pinning a claim shows its verdict', async ({ page }) => {
  const card = page.locator('.hs-card');
  await card.scrollIntoViewIfNeeded();
  await expect(card).toBeVisible();
  await expect(card.getByRole('tab')).toHaveCount(4);

  // Interaction: pick claim 2 ("reviewed — safe to merge" → RE-DERIVED).
  const pip = card.getByRole('tab', { name: /^claim 2/ });
  await pip.click();
  await expect(pip).toHaveAttribute('aria-selected', 'true');
  await expect(card.locator('.hs-afford')).toContainText('driving');
  await expect(card.locator('.hs-claim')).toContainText('reviewed');
  // asserting → stamped after ~1.1s; the pinned claim keeps its stamp.
  await expect(card.locator('.hs-mark')).toContainText('RE-DERIVED');
});

test('Toolbox: renders six tools and clicking one pins its demo + command', async ({ page }) => {
  const box = page.locator('#toolbox');
  await box.scrollIntoViewIfNeeded();
  const rail = box.getByRole('tablist', { name: 'garden tools' });
  await expect(rail.getByRole('tab')).toHaveCount(6);

  // Interaction: pin the "patch" tool — stops auto-play, swaps the stage.
  const patchTab = rail.getByRole('tab', { name: /patch/ });
  await patchTab.click();
  await expect(patchTab).toHaveAttribute('aria-selected', 'true');
  await expect(box.locator('.tb-afford')).toContainText('driving');
  await expect(box.locator('.tb-stage-name')).toHaveText('patch');
  await expect(box.locator('.tb-stage')).toContainText('wicked-garden-engineering');

  // Resume auto-play — affordance flips back.
  await box.getByRole('button', { name: /resume auto-play/ }).click();
  await expect(box.locator('.tb-afford')).toContainText('auto-playing');
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

  // Break the vault condition → the gate FAILS CLOSED (never a vacuous pass).
  const vault = machine.getByRole('switch', { name: /vault backend present/ });
  await vault.click();
  await expect(vault).toHaveAttribute('aria-checked', 'false');
  await lever.click();
  await expect(machine.locator('.pg-mark-word')).toHaveText('FAILS CLOSED');
});

test('CapabilityGrid: 14 domain cards + 4 peers render; qe card deep-links to the wall', async ({
  page,
}) => {
  const grid = page.locator('#toolkit');
  await grid.scrollIntoViewIfNeeded();
  await expect(grid.getByRole('heading', { name: /Six tools were the sample/ })).toBeVisible();
  await expect(grid.locator('.cg-card')).toHaveCount(14);
  await expect(grid.locator('.cg-peer')).toHaveCount(4);
  await expect(grid.locator('.cg-peer').first()).toContainText('wicked-estate');
  // The island is presentational — its dynamic behavior is the scroll-triggered
  // reveal. Assert the fade-in actually completed (opacity → 1).
  await expectRevealed(grid.locator('.cg-grid'));
  await expect(grid.locator('.cg-card').first()).toContainText('skills');
  // The qe domain card is the doorway to the absorbed wall band.
  const qeCard = grid.locator('.cg-card--qe');
  await expect(qeCard).toHaveAttribute('href', '#qe');
  await expect(qeCard).toContainText('quality engineering');
  await expect(qeCard).toContainText('42 skills');
});

test('ExtendPack: the extension pitch renders scaffold, rules, and the compile chip', async ({
  page,
}) => {
  const xp = page.locator('#extend');
  await xp.scrollIntoViewIfNeeded();
  await expect(xp.getByRole('heading', { name: /Your domain\. Your pack\./ })).toBeVisible();
  await expectRevealed(xp.getByRole('heading', { name: /Your domain\. Your pack\./ }));
  // the {vendor}-{domain}-{role} scaffold rows
  await expect(xp.locator('.xp-row')).toHaveCount(3);
  await expect(xp.locator('.xp-dir').first()).toContainText('acme-fintech/');
  await expect(xp.locator('.xp-rule')).toHaveCount(3);
  // Interaction: copy the prove-compile command (the garden-free gate).
  await clickCopyChip(
    xp.getByRole('button', { name: /Copy command: wicked-garden-prove compile/ }),
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

  // Interaction: copy the direct-install command.
  const chip = bench.getByRole('button', {
    name: 'Copy command: claude plugins install wicked-garden',
  });
  await clickCopyChip(chip);
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
