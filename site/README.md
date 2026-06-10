# wicked-site

The marketing brochure for **wickedagile / wicked garden** — the curated,
open-source toolkit for AI-native engineers, with wicked-garden as the umbrella
and the wicked-\* tools as its beds and layers.

A fast, interactive, light/dark single-page site: kinetic hero, an animated
manifesto, **the Garden Tour** (a scrollytelling walk — one stop per tool, with
capability/use-case panels and one-line installs), and **the Potting Bench**
(a standalone kit builder: toggle beds, the install script writes itself).
Key words grow animated vines instead of highlighter swipes.

## Stack

- **[Astro 5](https://astro.build)** — static output, near-zero JS by default
- **React 19 islands** — only the interactive bits ship JS (`client:load` / `client:visible`)
- **Tailwind CSS v4** — via `@tailwindcss/vite`, class-based dark mode
- **[Motion](https://motion.dev)** — animation for the React islands
- **Archivo (expanded) / Hanken Grotesk / JetBrains Mono** — self-hosted via Fontsource;
  brand palette documented in [`docs/BRAND.md`](docs/BRAND.md)

## Develop

```bash
npm install
npm run dev        # http://localhost:4321/wicked-site/
npm run build      # static output → dist/
npm run preview    # serve the production build locally
```

> The dev/preview URL includes the `/wicked-site/` base path (see below).

## Editing content

All copy lives in **one file**: [`src/data/projects.ts`](src/data/projects.ts).

- `ROLES` — the four garden roles (The gate / The floor / The layers / Solo beds)
- `PROJECTS` — each tool's `role`, `kicker`, `tagline`, **`outcome`** (the headline
  result), `blurb`, `points`, `install`, `repo`, `badges`
- `TOUR` — the eight Garden Tour stops (one per tool): kicker, marker-swiped
  headline, narrative, unlock caption, and whether the stop is pre-planted
  (`locked`) or `optin`

Add, remove, or re-role a tool there and the tour and footer update
automatically — counts included. Planted-kit state persists in `localStorage`
under `wicked-kit`.

## Deploy (GitHub Pages)

A workflow at [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) builds and
publishes on every push to `main`.

1. Push this repo to GitHub.
2. **Settings → Pages → Build and deployment → Source: GitHub Actions.**
3. Push to `main` (or run the workflow manually).

The workflow derives `site` and `base` from the repo automatically, so it works on a
fork named anything. The defaults assume a **project page** served at
`https://<user>.github.io/<repo>/`.

**Other targets** — override the two env vars (locally or in CI):

| Target | `SITE_URL` | `BASE_PATH` |
|---|---|---|
| Project page (default) | `https://<user>.github.io` | `/<repo>` |
| User/Org page (`<user>.github.io` repo) | `https://<user>.github.io` | `/` |
| Custom domain | `https://your.domain` | `/` |

```bash
SITE_URL=https://wicked.dev BASE_PATH=/ npm run build
```

## Structure

```
src/
  data/projects.ts        ← single source of content
  layouts/Base.astro      ← <head>, fonts, meta/OG, no-flash theme script
  components/
    Header.astro Footer.astro
    react/                ← islands: ThemeToggle, Hero, Manifesto, GardenTour,
                            GardenBench, Reveal, Marker (word-vines), CopyChip
  styles/global.css       ← design tokens (light/dark), Tailwind theme, effects
  pages/index.astro       ← composes the sections
```

## Accessibility

Light/dark with a no-flash inline script, `prefers-reduced-motion` honored across
every animation, focus-visible rings, semantic landmarks, and AA-tuned color contrast
(small colored text uses darker `--ct-*` variants in light mode).

MIT.
