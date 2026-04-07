---
description: Interactive memory review - browse, understand, and manage stored memories
argument-hint: "[--type decision|episodic|procedural|preference] [--project <name>] [--stale]"
---

# /wicked-garden:mem:review

Browse and review all stored memories from local chunk files, grouped by tier with age and metadata.

## Arguments

Parse the arguments from: $ARGUMENTS

- `--type`: Filter by memory type (episodic, decision, procedural, preference)
- `--tier`: Filter by tier (working, episodic, semantic)
- `--stale`: Show only memories older than 30 days with low access
- `--limit`: Maximum memories to display (default: 30)

## Execution

### Step 1: List all memory chunks

Use Glob to find all memory chunk files:

- `$HOME/.wicked-brain/memories/working/mem-*.md`
- `$HOME/.wicked-brain/memories/episodic/mem-*.md`
- `$HOME/.wicked-brain/memories/semantic/mem-*.md`

### Step 2: Read and parse chunk files

Use the Read tool to read each chunk file (up to the --limit). Parse the YAML frontmatter to extract:
- `title`
- `memory_type`
- `memory_tier`
- `tags`
- `importance`
- `indexed_at` (for computing age)

### Step 3: Apply filters

- If `--type` specified, keep only memories matching that type
- If `--tier` specified, keep only memories in that tier
- If `--stale` specified, keep only memories where `indexed_at` is more than 30 days ago

### Step 4: Group and display

Group memories by tier (semantic first, then episodic, then working). For each memory display:

- **ID** (from filename)
- **Title**
- **Type** and **importance**
- **Tags** (comma-separated)
- **Age** (computed from indexed_at, e.g. "15 days ago", "3 months ago")
- **Content preview** (first 80 chars of body after frontmatter)

### Step 5: Summary

At the end, display:
- Total memories found
- Breakdown by tier
- Breakdown by type
- Oldest and newest memory dates
- Suggestion to run `/wicked-garden:mem:forget` for stale items or `/wicked-garden:mem:consolidate` to synthesize
