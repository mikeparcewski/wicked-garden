# wicked-web

Shared chrome for the **wicked-\*** family sites — one place to update the look so every site stays consistent.

Exports (raw Astro/CSS source; the consuming site compiles them):

- `wicked-web/layouts/Base.astro` — document shell: `<head>`, fonts, favicon, global stylesheet, no-flash theme init, `<slot/>`, the scroll-wheel script.
- `wicked-web/components/Topbar.astro` — fixed nav header + ecosystem dropdown + theme toggle.
- `wicked-web/components/Footer.astro` — family footer (link categories, brand block, strip).
- `wicked-web/components/SameGarden.astro` — "From the same garden" cross-promo grid. Pass `current="wicked-<name>"`; that card is excluded so a site never promotes itself.
- `wicked-web/styles/tokens.css`, `wicked-web/styles/global.css` — theme tokens + global background grid.
- `wicked-web/scripts/scroll-wheel.js` — wheel-to-snap streamliner.

Component props worth knowing:
- `Topbar`: `pkg` (secondary "<logo> / <pkg>" label, omit on the umbrella site) · `repo` (GitHub-icon link → that page's repo).
- `Footer`: `repo` (GitHub-chiclet link → that page's repo).
- `Base`: `title` · `description` · `bodyClass` (e.g. garden's `has-grain`) · `favicon` (default `/favicon.svg`; pass a base-aware path on sites under a project base — see gotchas).
- `SameGarden`: `current` (this site's package name).

## Use it (per site)

```jsonc
// package.json
"dependencies": { "wicked-web": "github:mikeparcewski/wicked-web" }
```

```js
// astro.config.mjs — local source while developing, the git package in CI
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
const localUI = fileURLToPath(new URL('../wicked-web/src', import.meta.url));
const alias = existsSync(localUI) ? { 'wicked-web': localUI } : {};
export default defineConfig({ /* ... */ vite: { resolve: { alias } } });
```

```astro
---
import Base from 'wicked-web/layouts/Base.astro';
import Topbar from 'wicked-web/components/Topbar.astro';
import Footer from 'wicked-web/components/Footer.astro';
---
<Base title="…" description="…">
  <Topbar />
  <!-- site content -->
  <Footer />
</Base>
```

Edit a component here → if `../wicked-web` sits beside the site, dev picks it up live. Push here + the sites rebuild → everyone gets the update (CI installs from `github:mikeparcewski/wicked-web`).

## Tailwind / React sites (garden, estate)

Plain-Astro sites (wickedagile, interactive) import the shared `Base` directly. Tailwind/React sites keep their **own** `global.css` (it needs `@import "tailwindcss"` + `@theme`, which can't live in the shared plain-CSS file) but still use the shared `Base` + chrome:

```astro
import Base from 'wicked-web/layouts/Base.astro';
import '../styles/global.css';   // site's Tailwind entry — shared Base does NOT import it
```

Their `global.css` should **not** redefine the family tokens — those come from the shared `tokens.css` (loaded by `Base`). Define only site-specific extensions (e.g. garden's `--c-*` role colors, grain) and the `@theme` mapping. Map `@theme` fonts to the Google family names the shared `Base` loads: `"Archivo"`, `"Hanken Grotesk"`, `"JetBrains Mono"`.

## Releasing a change (IMPORTANT)

Git dependencies are **pinned by commit in each site's `package-lock.json`**. After you push `wicked-web`, a site will NOT pick up the change in CI until you bump its pin:

```bash
cd <site> && npm install github:mikeparcewski/wicked-web   # updates the pinned commit
git commit -am "chore: pick up wicked-web change" && git push  # triggers that site's deploy
```

So a shared change isn't "live everywhere" until every consuming site is reinstalled + redeployed.

## Adding a new family site

1. Add one entry to `SITES` in `SameGarden.astro` (name, href, tagline, blurb, tags) — every site's cross-promo picks it up automatically (it excludes its own via `current`).
2. Add the package to `Footer.astro`'s category list + the `Topbar` ecosystem dropdown.
3. New site consumes the shared `Base`/`Topbar`/`Footer`/`SameGarden` and passes `pkg`/`repo`/`current`.

## Conventions & gotchas

- **Theme is `data-theme="light|dark"` on `<html>`** (NOT a `.dark` class). The Topbar toggle + Base no-flash init drive it via `localStorage 'wa-theme'`. Tailwind sites key their dark variant off it: `@custom-variant dark (&:where([data-theme="dark"], [data-theme="dark"] *))`. Family default is **light**.
- **No `import.meta.env` or regex literals in the shared `Base.astro` frontmatter.** When a site imports `Base` via the alias, the **Astro 4** compiler mis-parses these and treats the whole template as JS ("Unterminated string literal"). Pass anything base-dependent (e.g. the favicon path) in as a prop, computed in the *site's* own frontmatter where it's safe.
- **The shared `tokens.css`/`global.css` live in `@layer base`** — do NOT add unlayered rules to them. Tailwind v4 utilities sit in `@layer utilities`, and unlayered CSS beats *any* layer, so an unlayered shared reset/`html` rule will silently clobber the Tailwind sites' `py-*`/`mx-auto`/etc. and collapse their layouts (plain-CSS sites like wickedagile won't show it — verify the Tailwind sites' mid-page sections after any shared-CSS change).
- **Shared components must be plain CSS on the family tokens** (`var(--canvas)`, `var(--ink)`, …) with a scoped `<style is:global>` — never Tailwind classes — so they also render on the plain-Astro sites.
- **Self-contained widths**: don't rely on a global `.wrap`; sites with their own token CSS don't define one. Footer scopes its own `.footer .wrap`.
- **CI Node version**: Astro 6 sites need **Node ≥ 22** in their Pages workflow (Astro 4 sites are fine on 20). Symptom if wrong: "Node.js 20 is not supported by Astro".
- **Sites under a project base** (e.g. garden at `/wicked-garden/`): pass a base-aware `favicon` to `Base`, computed in the site's frontmatter:
  ```astro
  const favicon = `${import.meta.env.BASE_URL}/favicon.svg`.replace(/\/{2,}/g, "/");
  ```
  Sites at the domain root can omit it (default `/favicon.svg`). Each site needs a real `public/favicon.svg` (the shared Base references it).
