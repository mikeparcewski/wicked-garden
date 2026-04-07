---
description: Archive or delete a memory
argument-hint: "<memory_id> [--hard]"
---

# /wicked-garden:mem:forget

Remove a memory from the brain. By default performs a hard delete (removes chunk file and brain index entry).

## Arguments

Parse the arguments from: $ARGUMENTS

- `memory_id` (required): The memory ID (e.g. `mem-abc123` or full path `memories/episodic/mem-abc123`)
- `--hard`: Hard delete (default behavior, kept for backward compatibility)

## Execution

### Step 1: Locate the chunk file

If only the short ID was given (e.g. `mem-abc123`), search for the chunk file:

```bash
find "$HOME/.wicked-brain/memories" -name "{memory_id}.md" 2>/dev/null
```

Or use Glob to find: `$HOME/.wicked-brain/memories/*/mem-{id}.md`

### Step 2: Confirm the memory exists

Use the Read tool to read the chunk file and display its title, type, and content summary so the user can confirm this is the right memory.

### Step 3: Remove from brain index

```bash
curl -s -X POST http://localhost:4242/api \
  -H "Content-Type: application/json" \
  -d '{"action":"remove","params":{"id":"memories/{tier}/{memory_id}"}}'
```

The `id` must match the path used during indexing (e.g. `memories/episodic/mem-abc123`).

### Step 4: Delete the chunk file

Use Bash to remove the file:

```bash
rm "$HOME/.wicked-brain/memories/{tier}/{memory_id}.md"
```

### Step 5: Handle errors

- If chunk file not found: report "Memory {id} not found" and list available memory IDs from `$HOME/.wicked-brain/memories/`
- If brain API unreachable: delete the chunk file anyway but warn that the brain index may be stale. Suggest running `wicked-brain:lint` to clean up.

## Output

Confirm deletion with:
- Memory ID and title
- Brain index removal status
- Chunk file deletion status
