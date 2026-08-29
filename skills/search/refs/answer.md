# Answer — cited synthesis from the estate stores

The user-facing "ask the record" verb (supersedes the retired
`wicked-brain:query`). Produce a **grounded, cited** answer from what the <!-- historical -->
knowledge + memory stores actually contain — never from model memory alone.
This is the agent-side application of estate's embedded method card
`skill://cited-answer/SKILL.md` (DEC-R: the engine ranks, you write the
prose and attach the citations).

**Arguments**: `question` (required); `--scope-prefix <prefix>` (optional —
narrow the memory side; default `""` = everything); `--budget <tokens>`
(optional, default 2000 per store).

## Procedure

1. **Fetch the evidence** — one backend call returns both stores' hits:

   ```bash
   sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
     "${CLAUDE_PLUGIN_ROOT}/scripts/mem/estate_memory.py" sources '{"query":"<question>"}'
   ```

   The result carries `knowledge` items (each with a `body_snippet` and its
   `source` citation — a file path or URL recorded at ingest) and
   `memories` items (each with `content`, `scope`, `tier`, `memory_id`).

2. **Filter for relevance.** Keep only items that actually bear on the
   question; scores are hints, not verdicts. Ignore near-duplicate chunks
   (a doc title chunk next to its body chunk cites the same `source`).

3. **Synthesize — from the items ONLY.** Compose the answer strictly from
   the recalled content. Quote or paraphrase; after each claim, cite where
   it came from:
   - knowledge chunk → cite its `source` (e.g. `[docs/adr/0005.md]`)
   - memory → cite its scope (e.g. `[memory: project:wicked-garden]`)

   End with a `Sources:` list — every distinct `source` / scope used, so
   the reader can verify each claim.

   When a returned item quotes an estate **SymbolId that no longer resolves**
   in the graph (ids minted before the 2026-08 id-scheme migration may be
   dangling), fall back to the estate MCP `SearchEntity` tool by bare name to
   find the symbol's current node.

4. **Handle the miss honestly.** If nothing relevant came back (estate logs
   the miss), say the record doesn't answer this — offer to `ingest` the
   relevant document or fall back to code search. NEVER pad a thin result
   with ungrounded model knowledge; if you add background context anyway,
   label it explicitly as *not from the record*.

5. **Degrade visibly.** `{"ok": false}` means estate is unreachable — report
   that instead of answering, so a missing engine never masquerades as an
   empty record.

## Falsifiers (what makes this NOT a cited answer)

- A claim in the answer that no returned item supports.
- A dropped citation — the reader must be able to verify every claim.
- Mixing record content and model background without labeling which is which.

## Examples

```
answer "why did we re-home the code graph to estate?"
answer "what were the loom cutover gotchas?" --scope-prefix project:wicked-garden
```
