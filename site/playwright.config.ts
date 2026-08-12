import { defineConfig, devices } from '@playwright/test';
const PORT = Number(process.env.E2E_PORT ?? 4333);
export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  // Local cap: a saturated dev machine (parallel suites/builds) starves the
  // single-process preview server and flakes navigations. CI keeps defaults.
  workers: process.env.CI ? undefined : 4,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : [['list']],
  use: { baseURL: `http://127.0.0.1:${PORT}`, trace: 'on-first-retry' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: `npm run preview -- --port ${PORT}`,
    url: `http://127.0.0.1:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
    // Astro 7 auto-daemonizes `astro preview` when it detects an agentic
    // environment (via am-i-vibing), which makes the spawned process exit
    // early and breaks Playwright's webServer lifecycle. Setting this env
    // (the same guard Astro's own daemon child uses) forces foreground mode.
    env: { ASTRO_PREVIEW_BACKGROUND: '1' },
  },
});
