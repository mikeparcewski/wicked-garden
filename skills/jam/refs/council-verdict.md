---
phase_relevance: ["clarify", "design"]
archetype_relevance: ["*"]
---
# Acting on the Council Verdict (caller side)

This ref guides the PARENT after the `wicked-garden-jam-council` fork returns.
It is caller-side policy — the council worker produces the verdict; the caller
decides what to do with it.

## Verdict heuristics

The council returns a synthesised verdict plus per-model raw votes. v11
archetypes decide what to do with the result; the council itself does
not gate. Heuristics for the caller:

- **Unanimous APPROVE / REJECT with all confidences ≥ 0.7** — proceed with
  the verdict.
- **Split verdict (3-1 or closer) OR any confidence < 0.6** — surface the
  raw votes to the user and pause for human adjudication. The disagreement
  carries information that the synthesised verdict erases.
- **High-stakes archetypes (`migrate`, `incident`, anything with
  `hard:cutover` / `hard:mitigate`)** — always show the raw votes
  alongside the verdict; never auto-proceed on a synth-only summary.

A v6-era helper (deleted in v11.0.0) encoded these rules in code as part
of the universal-pipeline machinery. v11 deleted the gate it fed into;
the heuristics above are the same shape, applied inline by the agent.

## Raw per-model votes (Issue #584) — output contract

Default output carries both the synthesised verdict AND a `raw_votes` list so
callers can see per-model nuance even on unanimous verdicts. The envelope is
assembled via `scripts/jam/consensus.py::build_council_output(votes, synthesized)`
— it returns `{"synthesized": {...}, "raw_votes": [{"model", "verdict", "confidence", "rationale"}, ...]}`
where each `rationale` is the model's own one-liner (or the first 240 chars of
its response) and missing confidences stay `null`, not `0.0`.

Operator override: `WG_COUNCIL_OUTPUT=both|synth|raw` (default `both`). Use
`synth` for the legacy single-key shape; use `raw` when tooling only wants the
unvarnished per-model layer.
