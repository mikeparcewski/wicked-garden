# ADR 0003 — Two required peers (the gate), three opt-in layers

- **Status:** Accepted — executed.
- **Date:** 2026-06-09
- **Supersedes:** the v12 stance in `docs/required-peers.md` ("five peers are required infrastructure").

## Context

v12 made all five peers (`wicked-testing`, `wicked-vault`, `wicked-brain`, `wicked-bus`, `wicked-loom`) **required** — `/wicked-garden:setup` blocked without any one, and the SessionStart bootstrap nagged "REQUIRED but not installed" for each.

A third-party review pass (a skeptic persona + a `jam:council` panel of external models — codex/gpt-5.5 and opencode/claude-haiku) converged, independently, on one verdict: **the all-or-nothing five-peer requirement contradicts the "gap-filler that gets out of the way" pitch and is the single biggest adoption blocker.** "A gap-filler should feel additive; this sounds like infrastructure." "A single required peer would unlock solo adoption; bundle the other four as opt-in layers and you'd see 10× more install attempts."

The author's counter-point matters too: **garden's goal is a curated toolkit**, and stripping to one tool deletes the concept. So the resolution is not "cut to one tool" — it's "keep the breadth, fix the coupling."

## Decision

Split the peers by what actually needs them:

- **Required — the evidence gate:** `wicked-vault` + `wicked-loom`. The toolkit's central promise is *re-derived, fail-closed "done."* A gate that can't re-derive evidence is the one thing we refuse to fake, so setup **blocks** without these two. Trading adoption for honesty here is deliberate.
- **Opt-in layers:** `wicked-testing` (acceptance-testing tool), `wicked-brain` (memory + search — the *what*), `wicked-understanding` (repo playbooks — the *how*; `skills`-standard, added in v12.16), `wicked-bus` (audit trail). Each unlocks one capability; none is a prerequisite for the others or for the gate. Setup **recommends** them and continues; bootstrap surfaces them informationally.

This is the toolkit stance: **breadth you adopt incrementally**, not a five-thing prerequisite wall.

## Why this is safe

- The produces-gate already routes only through vault+loom; it never needed testing/brain/bus.
- `wicked-bus` emission was already fire-and-forget / fail-open.
- `wicked-brain` absence already degrades (structural search falls back to codegraph; memory features simply go dark).
- Runtime resilience + the kill-switches (`WICKED_VAULT_BIN=""`, `WICKED_LOOM_CUTOVER=off`) are unchanged — they still fail closed, never vacuous-pass.

## Changes

- `commands/setup.md` — testing/brain/bus sections → "Recommended (opt-in layer)", non-blocking (Skip & continue); vault/loom → "Required — the evidence gate", still blocking. Added a "two required, three opt-in" framing note.
- `hooks/scripts/bootstrap.py` — brain/bus notes reworded "REQUIRED but not installed" → "optional layer not installed"; removed the brain "[Action Required] … cannot function … do NOT proceed" escalation. vault/loom notes unchanged.
- `docs/required-peers.md` rewritten to the 2-required/3-opt-in model; README/ETHOS/plugin.json/marketplace.json/repo description reframed; positioning shifted from "minimal gap-filler" to **"curated toolkit"** (breadth is the point; the coupling was the problem).

## Consequences

- Solo developers can install garden + the gate (two `npx`/`npm` steps) and get value immediately, adding layers as needed.
- The honesty guarantee is preserved exactly where it's load-bearing (the gate).
- Honest cost: a user who skips brain/bus/testing gets a smaller toolkit — which is the point of opt-in. Docs say so plainly rather than pretending everything is mandatory.
