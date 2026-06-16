// @ts-check
import { defineConfig } from 'astro/config';
import react from '@astrojs/react';
import tailwindcss from '@tailwindcss/vite';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

// Shared chrome from the `wicked-web` package: local source when it sits beside
// this repo (../../wicked-web) for live dev, else the installed git package in CI.
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
const SITE = process.env.SITE_URL ?? 'https://mikeparcewski.github.io';
const BASE = process.env.BASE_PATH ?? '/wicked-garden';

export default defineConfig({
  site: SITE,
  base: BASE,
  trailingSlash: 'ignore',
  integrations: [react()],
  vite: {
    plugins: [tailwindcss()],
    resolve: { alias: wickedWebAlias },
    optimizeDeps: {
      include: ['react-dom/client'],
    },
  },
});
