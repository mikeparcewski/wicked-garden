// @ts-check
import { defineConfig } from 'astro/config';
import react from '@astrojs/react';
import tailwindcss from '@tailwindcss/vite';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

// The site's version stamp is injected at build time from the plugin's own
// manifest (.claude-plugin/plugin.json — the source of truth the release hook
// `sync-plugin-version.mjs` keeps in lockstep with package.json/npm), so the
// stamp can never re-stale the way a hardcoded string does (it sat at
// v12.29.1 while npm was at 12.31.0). Deliberately NOT an npm-registry fetch:
// that would make the build non-hermetic. (DT-7)
const plugin = JSON.parse(
  readFileSync(fileURLToPath(new URL('../.claude-plugin/plugin.json', import.meta.url)), 'utf8'),
);

// Shared chrome from the `wicked-web` package: local source when it sits beside
// this repo (../../wicked-web) for live dev, else the installed git package in CI.
// The real SKILL.md count under ../skills/** — computed at build time so the site's skill count
// can never drift from the catalog it describes.
const skillsDir = fileURLToPath(new URL('../skills', import.meta.url));
const skillCount = readdirSync(skillsDir, { recursive: true }).filter(
  (f) => String(f).split(/[\\/]/).pop() === 'SKILL.md',
).length;

const localUI = fileURLToPath(new URL('../../wicked-web/src', import.meta.url));
/** @type {Record<string, string>} */
const wickedWebAlias = existsSync(localUI) ? { 'wicked-web': localUI } : {};

/**
 * Deploy targets:
 *  - GitHub Pages project site (default): https://<user>.github.io/wicked-garden/
 *  - Override for a user/org page or custom domain via env:
 *      SITE_URL=https://wicked.dev BASE_PATH=/ npm run build
 * The deploy workflow sets these from repository metadata.
 */
const SITE = process.env.SITE_URL ?? 'https://wg.wickedagile.com';
const BASE = process.env.BASE_PATH ?? '/';

export default defineConfig({
  site: SITE,
  base: BASE,
  trailingSlash: 'ignore',
  integrations: [react()],
  vite: {
    plugins: [tailwindcss()],
    resolve: { alias: wickedWebAlias },
    define: {
      __WICKED_GARDEN_VERSION__: JSON.stringify(plugin.version),
      __WICKED_GARDEN_SKILLS__: JSON.stringify(skillCount),
    },
    optimizeDeps: {
      include: ['react-dom/client'],
    },
  },
});
