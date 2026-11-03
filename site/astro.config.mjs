// @ts-check
import { defineConfig } from 'astro/config';
import react from '@astrojs/react';
import tailwindcss from '@tailwindcss/vite';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
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

// The QE specialist skills (skills/qe-*/SKILL.md; a qe-* dir without one is not a skill): garden.ts checks that its fleet list names exactly these dirs
// while the build renders the page, so the site's specialist count is measured from source too (N9).
const qeDirs = readdirSync(skillsDir, { withFileTypes: true })
  .filter((d) => d.isDirectory() && d.name.startsWith('qe-') && existsSync(join(skillsDir, d.name, 'SKILL.md')))
  .map((d) => d.name)
  .sort();
if (!qeDirs.length) throw new Error('skills/ has no qe-* specialist dirs; the site checks its QE fleet against them at build time');

// The work-shape count, from the archetype catalog the classifier routes to (N9: measured, never typed).
const archetypes = JSON.parse(
  readFileSync(fileURLToPath(new URL('../.claude-plugin/archetypes.json', import.meta.url)), 'utf8'),
);
const workShapeCount = Object.keys(archetypes.archetypes ?? {}).length;
if (!workShapeCount) throw new Error('archetypes.json lists no work-shapes; the site counts them at build time');

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
  // compressHTML deletes the newline before an inline tag, which fuses the word before it to the tag's
  // text ("Memory</b>and"). Keep the whitespace the source has.
  compressHTML: false,
  integrations: [react()],
  vite: {
    // Safari before 16.4 ignores media-query range syntax (`width <= 760px`), so the minifier must keep min-width and
    // max-width: the CSS targets name the oldest browsers the site supports (wicked-web#63, wickedagile#71).
    build: { cssTarget: ['chrome100', 'edge100', 'firefox100', 'safari14'] },
    plugins: [tailwindcss()],
    resolve: { alias: wickedWebAlias },
    define: {
      __WICKED_GARDEN_VERSION__: JSON.stringify(plugin.version),
      __WICKED_GARDEN_SKILLS__: JSON.stringify(skillCount),
      __WICKED_GARDEN_WORK_SHAPES__: JSON.stringify(workShapeCount),
      __WICKED_GARDEN_QE_DIRS__: JSON.stringify(qeDirs),
    },
    optimizeDeps: {
      include: ['react-dom/client'],
    },
  },
});
