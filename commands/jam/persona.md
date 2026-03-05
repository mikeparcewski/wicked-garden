---
description: View a specific persona's contributions across all rounds of a jam session
argument-hint: "<persona-name> [--session-id ID] [--json]"
---

# /wicked-garden:jam:persona

Retrieve all contributions from a specific persona across every round of a brainstorm session. Useful for quoting a particular expert's position, understanding how their view evolved across rounds, or identifying perspectives the synthesis may have compressed.

Persona name matching is case-insensitive. Use the persona's display name as it appeared in the session (e.g., "Technical Architect", "Cost Optimizer", "Security Reviewer").

Without `--session-id`, searches the most recent session.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jam/jam.py" persona $ARGUMENTS
```

After running the script, present the output. If entries are returned, add a brief note about how many rounds the persona participated in and whether their position shifted between rounds (you can infer this from the raw_text content).

If no match is found, list the personas that did participate (by running `jam.py transcript --json` and extracting unique `persona_name` values) so the user can correct their query.
