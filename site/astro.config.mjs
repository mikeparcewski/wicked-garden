// @ts-check
import { defineConfig } from 'astro/config';
import react from '@astrojs/react';
import tailwindcss from '@tailwindcss/vite';

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
  },
});
