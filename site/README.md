# wicked-site

The marketing brochure for **wicked-garden** — the curated, open-source toolkit
for what AI coding agents can't do alone. wicked-garden is the gate and curated
toolkit (not the ecosystem umbrella — that's wickedagile); the site presents the
wicked-\* tools it composes as its beds and layers.

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
npm run dev        # http://localhost:4321/wicked-garden/
npm run build      # static output → dist/
npm run preview    # serve the production build locally
```

> The dev/preview URL includes the `/wicked-garden/` base path (see below).

## Editing content

The page's data lives in [`src/data/garden.ts`](src/data/garden.ts) (the hero claims, the gate's
conditions, the QE fleet, the catalog's skill families, the peers, the example packs, What's new);
each section's own words live in its island under `src/components/react/`. Counts are measured at
build time (`astro.config.mjs`: the SKILL.md count, the version, the work-shapes), never typed.
The messaging source of truth is the program's COPY and CAPABILITIES docs (rules N1-N10).

## Deploy (GitHub Pages)

Deploy is **human-gated**. The workflow at
[`.github/workflows/pages.yml`](.github/workflows/pages.yml) is dormant by design:
`workflow_dispatch` only — it does **not** auto-run on push or merge. Go-live is
triggered by hand when the site is ready.

1. Push this repo to GitHub.
2. **Settings → Pages → Build and deployment → Source: GitHub Actions.**
3. Trigger the **Deploy site to GitHub Pages** workflow manually (Actions → Run workflow).

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
  data/garden.ts          ← the page's data
  components/react/       ← one island per frame (HeroStamp, ProveGate, GraphStage, QeWall, QeFleet,
                            PanelVote, MemoryQueue, CatalogExplorer, ExtendPack, InstallBench),
                            plus CopyChip, PlayToggle, Reveal and useAutoplay
  scripts/                ← snap-guard (section snapping and the wheel), story-token, section-enter
  styles/site.css         ← the frames and stages; global.css ← tokens, trellis, Tailwind theme
  pages/index.astro       ← composes the sections (chrome from wicked-web)
```

## Accessibility

Light/dark with a no-flash inline script, `prefers-reduced-motion` honored across
every animation, focus-visible rings, semantic landmarks, and AA-tuned color contrast
(small colored text uses darker `--ct-*` variants in light mode).

MIT.
