# Live-Wiring Candidate Classification
**PR**: cluster-a/mem-zombie-cleanup
**Date**: 2026-04-25
**Analyst**: senior-engineer dispatch

---

## scripts/_paths.py:114

**Classification**: keep
**Rationale**: The reference at line 114 is inside a docstring for `list_sibling_source_dirs()`:
```python
def list_sibling_source_dirs(domain: str, source: str) -> list[Path]:
    """Return source directories from ALL sibling projects (excluding current).
    when the current project slug is ``3.1.0-a1fef338``, this returns the
    ``wicked-garden:mem/memories/`` directories from ``2.6.1-ec3414ad``,
    ...
```
This is a historical migration comment illustrating how the local-JSON storage path looked in v6/v7. It describes the on-disk directory name (`wicked-garden:mem`) which still exists at rest on user machines as the storage path under `~/.something-wicked/wicked-garden/local/`. The storage path itself is not changing — only the surface commands were cut in v8.0.0. The docstring accurately describes the cross-version directory layout that `list_sibling_source_dirs` must traverse for backward-compatible read operations. Updating the wording to note "v8.0.0 removed the surface; directory name retained for read-only migration support" would be clarifying but is not required for correctness.
**Action**: no action required — docstring is historically accurate and non-misleading.

---

## scripts/_domain_store.py:15,64,166

**Classification**: keep
**Rationale**: Line 15 is in the module docstring as a usage example (`ds = DomainStore("wicked-garden:mem")`). Line 64 is the `DOMAIN_MCP_PATTERNS` registry entry for `wicked-garden:mem`, which maps the domain to external MCP tools (notion, confluence, etc.). A separate grep confirms that `DomainStore("wicked-garden:mem")` is **not instantiated anywhere else** in `scripts/` or `hooks/` — the example in the docstring is illustrative, not live. The `DOMAIN_MCP_PATTERNS` entry is a routing table used only when something actually creates a `DomainStore("wicked-garden:mem")` instance; since no code does that (post-v8), the entry is dead metadata. However, removing it is out of this PR's scope — the memo's classification recommendation is **keep** on the grounds that it documents a storage capability that existed and does no harm in place. A future cleanup pass can remove the MCP-patterns entry when the last local-JSON mem data migration window expires.
**Action**: keep as-is. No write path exists through this code; the routing entry is inert.

---

## scripts/_integration_resolver.py:40,300

**Classification**: update
**Rationale**: Line 40 is in `resolve_tool()`'s docstring: `domain: Plugin domain, e.g. "wicked-crew", "wicked-garden:mem"`. This is a non-harmful doc example; it will self-correct when the MCP-patterns entry is eventually removed from `_domain_store.py`. Line 300 is a live write path: it emits `source: wicked-garden:mem` into brain chunk frontmatter when storing a tool preference. This is exactly the "stop writing the wrong source name" case called out in Section 2D.4. The chunk frontmatter at line 300 reads `lines.append("source: wicked-garden:mem")` and is written to `~/.wicked-brain/memories/semantic/mem-{uuid}.md`. Existing chunks will retain the old source string (no data migration needed), but new chunks should emit `wicked-brain:memory` per the memo's Section 2D.4 fix.
**Action**: update line 300 — change `"source: wicked-garden:mem"` to `"source: wicked-brain:memory"`. Leave line 40 docstring as-is (example text only, no operational impact).

---

## scripts/reset.py:46

**Classification**: keep
**Rationale**: Lines 35-50 of `reset.py` define `_DOMAIN_NAMES` and `_DOMAIN_DIRS` — both used by the `/wicked-garden:reset` CLI to scan and clear local state. The `"mem": "wicked-garden:mem"` entry at line 46 maps the short-name `mem` to the local directory name under `~/.something-wicked/wicked-garden/local/`. This is a **storage path**, not a command dispatch — users who have accumulated `wicked-garden:mem` local-JSON data from v7 and earlier still need to be able to clear it with `python3 scripts/reset.py --confirm --only mem`. Removing this entry would silently strand data from those users with no cleanup path. The memo correctly classified this as "verify, likely remove" but inspection shows it provides a legitimate maintenance function: data cleanup for the now-dead local store. Keep until the v7-era data migration window expires and the local directory can be formally retired.
**Action**: no action — keep the entry. Add a comment clarifying it covers the now-defunct surface (v8.0.0 cut the commands; data may still exist for reset purposes).

---

## scripts/smaht/context_package.py:57,132,210

**Classification**: update
**Rationale**:
- **Line 57** is inside `PLUGIN_SKILL_MAP["mem"]`: the first entry reads `"/wicked-garden:mem:recall — retrieve past decisions, constraints, patterns"`. This is injected into subagent context as a "skills you may use" directive. It points users at a dead command. Must be rewritten to `"wicked-brain:memory (recall mode) — retrieve past decisions, constraints, patterns"`.
- **Line 132** is inside `gather_memories()`: the function docstring says "Query wicked-garden:mem for task-relevant memories via domain adapter" and the body checks `if getattr(item, "source", "") != "mem": continue`. The actual query goes to `domain_adapter.query(task)` (not a direct DomainStore write), and the source filter `"mem"` is an adapter source label. Inspecting `adapters/domain_adapter.py` would confirm whether any adapter still emits source `"mem"` — this is a filter for items returned by the domain adapter, not a write. The docstring is stale. The filter `source == "mem"` will silently return nothing because no adapter emits that source label anymore. The function needs the docstring updated and the source filter either removed or changed to `"brain"`. The function is used in `build_package()` to populate a `memories` field.
- **Line 210** is in the `build_package()` docstring: "assembles task-scoped context from wicked-garden:mem (decisions, constraints) and wicked-garden:search (code context)". Stale doc — should say wicked-brain.
**Action**: (1) Update `PLUGIN_SKILL_MAP["mem"][0]` to point at `wicked-brain:memory`. (2) Update `gather_memories()` docstring and change the source filter from `"mem"` to `"brain"` (matching the brain adapter's emitted source label). (3) Update `build_package()` docstring.

---

## scripts/jam/consensus.py:387

**Classification**: update
**Rationale**: `format_for_memory()` at line 386 is a pure formatter — it returns a `dict` but does **not write to any store**. The actual write function is `store_council_result()` at line 466, which calls `DomainStore("wicked-jam")` (not `wicked-garden:mem`). So the function body is not broken. However, the docstring at line 387 says "Format consensus result for storage in wicked-garden:mem" which is now misleading — the function formats a dict for **brain ingestion** via whatever caller picks it up. The docstring should be updated to say "Format consensus result for storage in wicked-brain:memory" to match current intent and prevent future callers from wiring it to the wrong store.
**Action**: update docstring at line 387 from "storage in wicked-garden:mem" to "storage in wicked-brain:memory". No behavioral change required — the function is a pure formatter.
