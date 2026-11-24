# Extending the catalog — shipping a third-party pack

Garden is **the** catalog, not a closed product: the built-in domains follow a
naming contract anyone can follow, and the runtime discovers conformant
third-party **packs** without a garden PR. Your fintech-risk domain, your
games-QA fleet, your compliance cast — they sit beside the built-ins, under
the same evidence discipline.

This is the complete pack-author guide. Everything here is executable today;
the sections at the end state plainly which parts of the contract are still
minimal.

## What a pack is

A directory (npm package, git checkout, or plain folder) with:

```
acme-seo-pack/
├── wicked-pack.json                      # the manifest (see schema)
└── skills/
    ├── acme-seo/SKILL.md                 # ONE router per domain (user-invocable)
    ├── acme-seo-keyword-analyst/SKILL.md # fork worker (context: fork)
    ├── acme-seo-content-auditor/SKILL.md # fork worker (context: fork)
    └── acme-seo-content-auditor/refs/…   # tier-3 refs (optional)
```

Schema: [`schemas/wicked-pack.schema.json`](../schemas/wicked-pack.schema.json).
A complete working example (used as garden's own e2e fixture):
[`tests/fixtures/packs/acme-seo/`](../tests/fixtures/packs/acme-seo/).

### The manifest

```json
{
  "spec": 1,
  "name": "acme-seo",
  "vendor": "acme",
  "version": "0.1.0",
  "description": "ACME's SEO domain pack.",
  "skills_dir": "skills",
  "domains": [
    {
      "name": "seo",
      "specialist": {
        "role": "seo-engineering",
        "description": "SEO specialist — keyword strategy and evidence-backed audits.",
        "enhances": ["design", "build", "review"]
      },
      "produces": [
        { "archetype": "review", "produces": ["seo-audit"], "gate": "vault" }
      ]
    }
  ],
  "peers": { "wicked-garden": ">=12.0.0", "wicked-vault": ">=0.8.0" },
  "provenance": { "source": "https://github.com/acme/acme-seo-pack", "publisher": "acme" }
}
```

## The rules (the same ones the built-ins follow)

1. **One router per domain.** A single user-invocable skill named
   `{vendor}-{domain}` fronts the domain; sub-capabilities are *actions* of
   the router, never sibling top-level skills. ≤ 200-line body.
2. **Workers are `{vendor}-{domain}-{role}`** with `context: fork` in
   frontmatter — isolated subagent contexts with their own tool boundaries.
3. **Your prefix is your vendor name.** `wicked-*` (and `wicked-garden-*`)
   is reserved for the first-party catalog; the conformance gate rejects
   squatting, and the resolver indexes garden first so a pack can never
   shadow a first-party name.
4. **kebab-case, ≤ 64 chars; three-tier disclosure** — frontmatter ~100
   words, SKILL.md ≤ 200 lines (fork workers exempt — they load into an
   isolated context), refs/ 200–300 lines each.
5. **NOT-THIS-WHEN reciprocity.** If two of your skills are twins
   (executor vs advisor), each names the other in a `NOT THIS WHEN:` block —
   the gate enforces reciprocity inside your pack.
6. **Evidence via vault.** Your pack's "done" goes through the same gate:
   record evidence with `wicked-vault record … --actor <doer>` and let the
   produces-gate re-derive it. A pack never ships its own gate logic
   (`"gate": "vault"` is the only backend).
7. **Events** (if you emit them): 4-segment
   `wicked.<domain>.<noun>.<past-verb>` — bus SPEC.md is the authority.

### Spec 2: editors and blocks

Manifest `spec: 2` keeps every spec-1 field and adds two arrays. A spec-1 pack stays valid as it is.

- `editors[]`: artifact editors the pack ships. Each one is **one self-contained HTML file** inside the
  pack (`entry`), pinned by its `sha256`, with an `id`, a plain-words `title`, its own `version`, the
  `protocol` versions it speaks, the artifact `kinds` it opens, the `sizes` it supports (`inline` is
  required), and the `permissions` it asks for, each with a `why` shown at install. An optional
  `limits.bundleBytes` may only be lower than the host's cap (5 MiB). With `editors` present, `domains`
  is optional: an editor-only pack ships no skills.
- `blocks[]`: the block that **produces** the pack's kind: an `id`, a `label`, a `preset` JSON file
  inside the pack, the `produces_kind`, and the pack `skills` it uses (approved together at install).

`wicked` and `wicked-*` editor and block ids are refused in every pack: first-party editors ship inside
wicked-studio and first-party blocks are core presets. Example (garden's own spec-2 fixture):
[`tests/fixtures/packs/acme-terms/`](../tests/fixtures/packs/acme-terms/).

### Author an editor: the terms checker

[`acme-terms`](../tests/fixtures/packs/acme-terms/) is a complete example: a terms-check domain with
both its router and checker skills, a block that produces a document, and an editor for `document`
and `rfp-response` artifacts. Its editor reads the content, lists banned-term hits, contributes checks,
and points at the sentence you select. **Replace everywhere** replaces the terms in one saved version.
The sample keeps its skills and block so authors can see how these parts fit together.

Start in a new directory with the same scaffold used to build the sample:

```bash
wicked-garden run scripts/editor/scaffold.py --vendor acme --id acme-terms --title "Terms checker" --kinds document,rfp-response --permissions artifact.read,selection.chip,artifact.write,checks.contribute --out ./terms-editor
```

This writes `wicked-pack.json`, `editors/acme-terms/index.html`, and a README. The scaffold speaks
`wicked.editor/2` and `/1` to an older host. It supplies the handshake, MessagePort request/reply
handling, ping, size changes, theme, key forwarding and typing behavior. Keep that plumbing; replace
the viewer's `render()` and the sections marked `YOUR EDITOR`. Keep the manifest's `surfaces` and the
entry's `SURFACES` declaration in agreement when changing the card, options or full-screen UI.

In the sample's [entry](../tests/fixtures/packs/acme-terms/editors/acme-terms/index.html), follow the
read, render, point and save paths:

1. Request `artifact.read` after the handshake and retain the returned content and version. Render the
   document text as well as the hits so a document with no banned terms still shows what it opened.
   Use DOM nodes and `textContent` for artifact text; parsing HTML must not execute its scripts.
2. Find the banned terms and send `checks.contribute` for the hits. Build the list from the content
   the host supplied, with anchors back to its sentences.
3. With `selection.chip` granted, send `selection.set` with the selected sentence's anchor. The host
   turns that selection into a composer chip; the permission is named `selection.chip`.
4. Mark the **Replace everywhere** button `data-wicked-save` so conformance can exercise the actual
   save control. Its `addEventListener` handler builds the replacement content and makes one
   `version.write` request against the read version, using the `artifact.write` permission. One click
   saves one version; the control is disabled when there are no terms to replace. Keep typing
   separate from this action, and report a refused save visibly.

#### The policy crew serves

The entry is one self-contained HTML file with inline style and script. Crew inserts its WebRTC guard
prelude into each executable inline script and serves a third-party editor with a `script-src` that
contains exactly the hashes of those prefixed scripts. A second, inline-only policy prevents loading
an external script even when it has a matching integrity hash. Both policies apply together. Crew
refuses more than 200 inline scripts; this sample uses **one**.

Use `addEventListener` for controls. Inline `on*` event handlers, `javascript:` URLs, script text built
at run time, `eval` and `new Function` cannot run under this policy. Keep all executable script text in
the shipped entry. The frame has `connect-src 'none'`, `frame-src 'none'`, `child-src 'none'`, no workers,
no form submissions and no base URL changes. It cannot load a child frame from a URL or contact the
network. Images in the editor must use `data:` or `blob:`; fonts must use `data:`. Pack check also
refuses outside script, stylesheet and frame references. Request host operations over the granted
MessagePort API.

Garden's conformance runner serves the candidate exactly this way (the prelude, the hash-only and inline-only
script policies, no URL frames, the 200-script limit), so what passes conformance runs the same after install.
Any script the browser refuses in the editor's frame, or in a document inside it, fails case `9-liveness`
(`r1-handshake` for a run plugin). Cases 10 and 11 measure focus and animation from an isolated world, so an
editor cannot answer them by replacing DOM functions.

#### Describe the editor's card

Each `editors[]` entry can declare a one-line `description` and a `visuals` object. The sample uses:

```json
{
  "description": "Find banned terms, point at their sentences, and replace them in one saved version.",
  "visuals": {
    "icon": "editors/acme-terms/icon.svg",
    "color": "#224a5e"
  }
}
```

| Field | Authoring rule |
|---|---|
| `description` | A string; whitespace is collapsed to one line. Keep that line at most 160 characters. |
| `visuals.icon` | A pack-relative `.svg`, `.png` or `.webp` image, at most 16 KiB. |
| `visuals.color` | A six-digit hex color such as `#224a5e`. |
| `visuals.preview` | A pack-relative image filename, or an object with `light` and/or `dark` filenames; each image is at most 200 KiB. |
| `visuals.live` | A boolean; `true` allows a live preview. |

Image names match `^[A-Za-z0-9][A-Za-z0-9._/-]{0,120}$`, contain no `..` segment, and resolve inside
the pack root. Every directory on the way and the image itself must be a real entry, never a symlink;
the file's content must match its extension. Paths are relative to the manifest, so keep them unchanged
when copying an editor into another pack. These fields are cosmetic: malformed values produce warning
`PK089` and the pack still passes. Valid fields remain usable when another cosmetic field is bad.
Garden stages accepted image files with the entry. Crew does not put them on studio's Plugins page for a pack
editor yet: it drops both fields until mikeparcewski/wicked-crew#1702 lands (the editor installs either way).

#### Pin, check, and run conformance

After every entry edit, update its pinned hash, then check the pack and exercise it in Chromium:

```bash
wicked-garden run scripts/editor/pin.py ./terms-editor
npx wicked-garden pack check ./terms-editor --json
wicked-garden run scripts/editor/conformance.py --pack ./terms-editor --studio-dist /path/to/wicked-studio/dist --json
```

The conformance runner needs Python Playwright, its Chromium browser, and a built wicked-studio dist
containing the conformance host page. The `--studio-dist` route runs against that local build. An
existing crew host can instead be selected with `--host-url <crew-origin>`. A missing browser is a
failure, never a passing report. Inspect every case, including the save, content display, keyboard,
theme and surface checks. Re-run pin, pack check and conformance after changing the entry; the saved
hash names its exact bytes and grants are tied to that build.

To verify the checked-in sample, use the same commands with
`tests/fixtures/packs/acme-terms` as the pack directory. Pack check should report no warnings.

#### Install the whole pack: editor, skills and block

A pack that also ships skills or blocks installs through one consent. The plan
(`--dry-run`) lists:
- the editor's permissions;
- every skill, with the name crew adds it as (`wicked-garden-<skill dir>`, so a worker invokes it as
  `wicked-garden:<skill dir>`);
- every block, with its preset's phases.

The approved install stages the skills tree and each block's preset beside the editor. It hands crew
the approved skill and block lists, and crew adds them in the same install, or refuses and installs
nothing. A block preset's `phases` must be catalog phases (the sample uses `critique`); crew refuses
any other phase and names the options. A skill or preset file edited after the plan refuses the
approved install, so the operator is asked again.

```bash
wicked-garden run scripts/editor/install.py --dir tests/fixtures/packs/acme-terms --crew-url <crew-origin> --dry-run
wicked-garden run scripts/editor/install.py --dir tests/fixtures/packs/acme-terms --crew-url <crew-origin> \
  --target <the choices[].id you approved, e.g. daemon_Ab3…> --json
```

Pass the plan's choice id as `--target`: it carries the digest of what you reviewed, and that is what
refuses a pack changed since. A bare `--target daemon` installs whatever the pack holds when it runs.

This needs a crew with the skills and blocks approval step (mikeparcewski/wicked-crew#1703). An
older crew refuses such a pack with HTTP 501 `pack_ships_skills_or_blocks`. On an older crew,
install the editor by itself, as below.

#### Install the editor-only pack

The scaffolded `terms-editor` directory above is already editor-only. To install the sample's editor
by itself, copy its `editors/` directory (including `icon.svg`) into a new pack, and use a manifest
containing its editor declaration and pack identity without `domains`, `skills_dir` or `blocks`.
For example, run this Python from the garden checkout:

```python
import json
from pathlib import Path
import shutil

source = Path("tests/fixtures/packs/acme-terms")
target = Path("acme-terms-editor")
target.mkdir()  # Refuse to overwrite an existing pack.
shutil.copytree(source / "editors", target / "editors")
manifest = json.loads((source / "wicked-pack.json").read_text(encoding="utf-8"))
editor_only = {key: manifest[key] for key in ("spec", "name", "vendor", "version", "description", "editors")}
editor_only["name"] = "acme-terms-editor"
(target / "wicked-pack.json").write_text(json.dumps(editor_only, indent=2) + "\n", encoding="utf-8")
```

Run pack check and conformance on that copy, then inspect the install plan and install it into your
chosen existing crew host:

```bash
wicked-garden run scripts/editor/install.py --dir ./acme-terms-editor --crew-url <crew-origin> --dry-run
wicked-garden run scripts/editor/install.py --dir ./acme-terms-editor --crew-url <crew-origin> --json
```

The installer stages the manifest, entry, accepted declared images, the skills tree and block presets
(when the pack has them) and README when present under
`<root>/<name>/current/`, where the root is `--install-root`, else `$WICKED_EDITOR_INSTALL_ROOT`, else
`$WICKED_HOME/editors`, else `~/.wicked/editors`. Crew re-runs pack check and conformance against the staged copy
before recording the editor; a refusal restores the previous installation. `--target daemon-off`
installs it disabled. Manage it in studio Settings → Developer → Editor plugins. For a governed build,
use Settings → Developer → Create an editor plugin: the `editor-plugin` workflow presents its install
consent, and the approved install step applies the plan.

## Validate: the shipped conformance gate

```bash
npx wicked-garden pack check ./acme-seo-pack          # human output
npx wicked-garden pack check ./acme-seo-pack --json   # CI
```

Exit 0 = conformant (warnings allowed), 1 = errors. The gate checks the
manifest, router/worker shape, naming, disclosure tiers, NOT-THIS-WHEN
reciprocity, produces contracts (archetype names must exist in garden's
catalog), peer-floor syntax, and for spec 2 every editor (inside the pack, one `.html` file, its
hash, its size, nothing loaded from outside it, kinds, sizes, permissions) and block (preset file,
produced kind, pack skills), plus cosmetic card-field warnings (PK089): each rule has an actionable message. It runs anywhere Python ≥ 3.10 exists; no garden install
required (`scripts/pack/check.py` ships in the npm package).

## Install + register

Registration is what makes the runtime *see* the pack. Any of:

```bash
# acquire + install + validate + register in one step (wicked-installer —
# the same code path garden's own `pack install` delegates to):
npx wicked-installer pack add acme-seo-pack          # npm package name
npx wicked-installer pack add ./acme-seo-pack        # local directory

# or register an on-disk pack directly with garden:
npx wicked-garden pack register ./acme-seo-pack --source https://github.com/acme/acme-seo-pack

# see what the runtime sees:
npx wicked-garden pack list --json
npx wicked-garden pack unregister acme-seo
```

Registration is **fail-closed**: a pack that fails the conformance gate does
not register (`--force` exists, on your own head). Discovery itself also
picks packs up from, in priority order:

1. `WICKED_PACK_PATH` (pathsep-separated pack roots or dirs of packs),
2. the registered-pack file (`~/.something-wicked/wicked-garden/packs/registered.json`),
3. Claude Code plugin dirs (`~/.claude/plugins/*`, `~/.claude/plugins/cache/*/*`)
   containing a `wicked-pack.json`,
4. `<project>/.wicked/packs/*`.

So a pack shipped **as a Claude Code plugin** is discovered automatically —
the harness loads your skills, garden registers your routing. A pack that is
not a plugin needs its skills visible to the harness some other way
(`~/.claude/skills/`, which `wicked-installer pack add` handles for Claude
Code today).

## What registration gets you

- **Catalog**: `pack list` surfaces the pack, its domains, specialists,
  produces contracts, and provenance. No garden file is edited — 
  `components.json`/`specialist.json` stay first-party-only and the sync
  tooling ignores packs by design.
- **Crew routing** (the specialist seam): workers resolve through
  `scripts/crew/specialist_resolver.py` by full name
  (`acme-seo-keyword-analyst`), bare role (`keyword-analyst`), with the
  specialist domain `{vendor}-{domain}` (`acme-seo`). Specialist-engagement
  tracking (the SubagentStop hook) accepts pack domains that declare a
  `specialist` block.
- **Steering data**: declared `produces` contracts are validated and exposed
  (`_pack_registry.pack_produces()`); see honesty notes below.
- **Peer floors**: checked at SessionStart (cheap, fail-open) and on demand
  via `npx wicked-garden pack floors`.

## Honesty notes — where the contract is still minimal

The parts above are implemented and e2e-tested
(`tests/packs/test_e2e_toy_pack.py`). Three parts are deliberately minimal;
their current state, plainly:

**Trust & provenance (minimal).** Packs *declare* provenance; registration
*records* it plus a sha256 of the manifest and a content hash of the skills
tree. That detects post-registration drift — it does **not** prove
authorship. There is no signing, no central marketplace listing, and no
review process. Skills carry shell: **install packs only from sources you
trust**, exactly as you would an npm dependency. A signed/marketplace model
is future work (wicked-installer's `registry.json` is the named seam).

**Produces-contracts (data layer implemented; steering attach designed).**
Your declared produces are validated (PK040/PK041), surfaced in the catalog,
and the gate engine consumes a produces id directly — running
`loom gate <produces-id>` (i.e. `wicked-vault cross-check --phase seo-audit`)
against evidence your workers record works today, and your router should
instruct exactly that (see the fixture router). What does *not* happen yet:
the archetype steering engine (`scripts/crew/archetypes_v11.py`) does not
automatically append pack produces to an archetype's gate set when your
domain is engaged. That attach point is the named seam:
`archetypes_v11.steering_directives()` merging
`_pack_registry.pack_produces()` into each matched archetype's
`produces` list — filtered by *engaged* specialist domains (the
specialist-engagement ledger), because attaching unconditionally would
gate every `review` on every installed pack's contract. Until that
lands, pack gates are explicit-invocation, not auto-steered.

**Peer floors (implemented, deliberately fail-open).** Floors are syntax-
checked by the gate, compared at SessionStart against garden's own version
(zero subprocesses), and fully probed by `pack floors` (`--version` probes
for binary peers like `wicked-vault`). Violations *warn*; nothing blocks.
An unprobeable peer reports `unknown`, never a violation.

## Checklist before you publish

- [ ] `npx wicked-garden pack check .` exits 0
- [ ] every worker declares `context: fork`; the router does not
- [ ] evidence-writing workers record via `wicked-vault record … --actor <worker-name>`
- [ ] `peers` floors reflect what you actually tested against
- [ ] `provenance.source` points at the canonical repo
- [ ] ship `wicked-pack.json` at the package root (npm: include it in `files`)
