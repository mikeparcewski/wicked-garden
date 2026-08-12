import { test, expect } from '@playwright/test';
import { expectRevealed } from './utils';

/**
 * The qe-domain bands — the mechanics absorbed from the retired
 * wicked-testing site (wt.wickedagile.com redirects to /#qe):
 *   1. the reveal-reviewer flip — a self-graded PASS sent to an independent
 *      reviewer comes back contradicted (QeWall's report card),
 *   2. the acceptance-wall role-lighting — click Writer/Executor/Reviewer to
 *      light a role and read its isolation copy (QeWall's stage), and
 *   3. the fleet filter tabs — 40 specialists tabbed by surface, auto-cycling
 *      until clicked (QeFleet).
 */

test.beforeEach(async ({ page }) => {
  await page.goto('/');
});

test('QeWall: the reveal-reviewer flip contradicts a self-graded PASS', async ({ page }) => {
  const fig = page.locator('.qw-fig');
  await fig.scrollIntoViewIfNeeded();
  await expectRevealed(fig);

  // resting state: both cells read PASS, the reviewer verdict is pending
  await expect(fig).toHaveAttribute('data-revealed', 'false');
  await expect(fig.locator('.qw-mark--rev')).toHaveText('PASS');
  await expect(fig).toContainText('awaiting review…');

  // send it across the wall — the independent read contradicts the self-grade
  const btn = fig.getByRole('button', { name: /Send it to an independent reviewer/ });
  await btn.click();
  await expect(fig).toHaveAttribute('data-revealed', 'true');
  await expect(fig.locator('.qw-mark--rev')).toHaveText('FAIL');
  await expect(fig).toContainText('caught a real bug');
  await expect(fig.locator('.qw-delta')).toContainText('80%+');

  // and back
  await fig.getByRole('button', { name: /Reset/ }).click();
  await expect(fig.locator('.qw-mark--rev')).toHaveText('PASS');
});

test('QeWall: acceptance-wall role-lighting swaps the isolation copy', async ({ page }) => {
  const stage = page.locator('.qw-stage');
  await stage.scrollIntoViewIfNeeded();
  await expect(stage.locator('.qw-role')).toHaveCount(3);

  // the reviewer is lit by default — the wall is its story
  const reviewer = stage.locator('[data-role="reviewer"]');
  await expect(reviewer).toHaveClass(/is-lit/);
  await expect(reviewer).toContainText('never sees who did the work');

  // light the writer — the lit copy swaps in, the reviewer dims
  const writer = stage.locator('[data-role="writer"]');
  await writer.click();
  await expect(writer).toHaveClass(/is-lit/);
  await expect(writer).toContainText('designs the exam but never sits it');
  await expect(reviewer).not.toHaveClass(/is-lit/);

  // per-role tool boundaries from the skills' allowed-tools frontmatter
  await expect(writer.locator('.qw-role-tool')).toHaveText(['Read', 'Grep', 'Glob', 'Skill']);
  await expect(reviewer.locator('.qw-role-tool')).toHaveText(['Read']);
  await expect(stage.locator('[data-role="executor"] .qw-role-tool')).toHaveText([
    'Read',
    'Write',
    'Bash',
  ]);
});

test('QeWall: the evidence channel plays and the wall click pauses it', async ({ page }) => {
  const stage = page.locator('.qw-stage');
  await stage.scrollIntoViewIfNeeded();

  // playing by default (no reduced-motion in this project)
  await expect(stage).toHaveClass(/is-playing/);
  await expect(stage.locator('.qw-chip--pass')).toHaveCount(4);
  await expect(stage.locator('.qw-chip--block')).toHaveCount(4);

  // the dashed wall is the play/pause control
  await stage.locator('.qw-wall').click();
  await expect(stage).not.toHaveClass(/is-playing/);
  await stage.locator('.qw-wall').click();
  await expect(stage).toHaveClass(/is-playing/);
});

test('QeFleet: 40 specialists render and the tabs auto-cycle until clicked', async ({ page }) => {
  const fleet = page.locator('#fleet');
  await fleet.scrollIntoViewIfNeeded();
  await expect(fleet.getByRole('heading', { name: /Forty specialists/ })).toBeVisible();
  await expect(fleet.locator('.qf-agent')).toHaveCount(40);
  await expect(fleet.getByRole('tab')).toHaveCount(6); // all + five surfaces

  // auto-demo: within one cycle (2.2s) a surface tab lights on its own
  await expect(fleet.locator('.qf-afford')).toContainText('auto-cycling');
  await expect
    .poll(
      async () =>
        fleet.locator('.qf-btn.is-on:not([data-surf="all"])').count(),
      { timeout: 10_000, message: 'auto-cycle should light a surface tab' },
    )
    .toBeGreaterThan(0);
});

test('QeFleet: clicking a surface takes control and filters the roster', async ({ page }) => {
  const fleet = page.locator('#fleet');
  await fleet.scrollIntoViewIfNeeded();

  // /review carries the acceptance reviewer + 5 peers = 6 specialists
  const reviewTab = fleet.getByRole('tab', { name: /\/review/ });
  await expect(reviewTab).toContainText('6');
  await reviewTab.click();
  await expect(reviewTab).toHaveClass(/is-on/);
  await expect(reviewTab).toHaveAttribute('aria-selected', 'true');
  await expect(fleet.locator('.qf-afford')).toContainText('driving');

  const grid = fleet.locator('.qf-grid');
  await expect(grid).toHaveClass(/is-filtered/);
  await expect(grid.locator('.qf-agent.is-match')).toHaveCount(6);
  await expect(grid.locator('.qf-agent.is-match').first()).toContainText(
    'qe-acceptance-test-reviewer',
  );

  // the click killed the auto-cycle — the selection must hold past a cycle tick
  await page.waitForTimeout(2600);
  await expect(reviewTab).toHaveClass(/is-on/);

  // back to the full roster
  await fleet.getByRole('tab', { name: /^all/ }).click();
  await expect(grid).not.toHaveClass(/is-filtered/);
});

test('qe band: the wall copy grounds the contract (fork isolation, evidence dir)', async ({
  page,
}) => {
  const qe = page.locator('#qe');
  await qe.scrollIntoViewIfNeeded();
  await expect(qe.getByRole('heading', { name: /No agent grades its own homework/ })).toBeVisible();
  await expect(qe.locator('.qw-foot')).toContainText('.wicked-qe/evidence/');
  await expect(qe.locator('.qw-foot')).toContainText('context: fork');
  await expect(qe.locator('.qw-foot')).toContainText('allowed-tools: Read');
  await expect(
    qe.getByRole('button', { name: 'Copy command: wicked-garden-qe' }),
  ).toBeVisible();
});
