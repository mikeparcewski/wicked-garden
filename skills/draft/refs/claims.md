# Claims discipline — the citation convention

The grounded floor of the `wicked-garden-draft` skill. Re-derived by `scripts/draft/claims_scan.py`
over the VISIBLE text of the deliverable.

## What is a claim

Any statement a reader could check against the repository: a version or requirement
(`Node ≥ 22`), a number (`within 2 s`, `94 %`, `3 active`), a URL or domain, a quote, a named
capability ("desktop notifications when a run needs you"), a licence, a supported platform.
The scan judges numbers and URLs mechanically; you judge the rest by the same rule.

## How to cite (any ONE of these makes a block "cited")

1. **`data-source` on the element or its block** — the primary form; invisible in print and
   safe under wicked-interactive's instrumentation (only `data-wid` is theirs):
   ```html
   <li data-source="README.md:23-24">Human gates: approve · steer · reject</li>
   <section class="page page-2" data-source=".product/REQ-001-application-overview.md:82 README.md:60">
   ```
   Several sources: separate with spaces or commas. `path[:line[-line]]`, repo-relative.
2. **An inline repo path in the same block** — `Requires Node ≥ 22 (package.json:72)`.
3. **A footnote marker (`[3]`, `†`) AND a visible Sources block** — a `Sources` / `References`
   heading (or an element with `data-sources`) followed by the repo paths.

Give the reader a visible **Sources** strip as well (form 3's block, or a footer line listing
the paths): the invisible attribute proves the claim; the strip lets a human check it.

## URLs and domains

- Every `https://…` and every bare domain (`ws.wickedagile.com`) is a claim. With `--repo`,
  the scan requires the address to appear in some file of the snapshot (`unsourced-url`
  otherwise); without a repo it requires a `data-source` (`uncited-url`).
- Existence is not meaning. RAID.md documents `ws.wickedagile.com` as the **marketing /
  deep-dive site**; calling it "the live wicked-studio instance" is an invented claim the scan
  cannot see — read the source line and characterise the link the way the source does.

## Mocks, illustrations, sample data

A hero "command center" with `impl/auth-layer running · 3 active · 1 needs you` is fine ONLY
when the reader is told it is not real:

```html
<div class="hero-mockup" data-illustrative>
  <div class="mockup-caption">Illustrative — sample runs, not measured data</div>
  …
</div>
```

- `data-illustrative` (or `data-mock`) on the container, AND a visible label inside it
  containing "illustrative", "example", "mock", "sample" or "hypothetical".
- A label that lives only in an HTML comment is the F-RECON-009 defect: `mock-label-hidden`.
- A container with the attribute and no visible label: `mock-unlabelled`.

## Placeholders

Never in the deliverable. `[PLACEHOLDER: …]`, `TODO`, `TBD`, `FIXME`, `lorem ipsum`,
`{{variable}}`, `[INSERT …]`, `[Company name here]` are all `placeholder` findings when visible.
The gap goes in your reply/notes: *"No customer quote or third-party audit exists in the
repository — the validation section was omitted rather than filled with a placeholder."*

## What the scan deliberately ignores

- Section ordinals written with a leading zero (`01`, `02`), copyright years (`© 2026`).
- Numbers inside a cited path or URL (`server.ts:1097`, `/v2/docs`).
- Text in comments, `<script>`, `<style>`, `hidden` elements — a reader never sees it.
- Prose claims without numbers or URLs (the model's job: cite them the same way).
