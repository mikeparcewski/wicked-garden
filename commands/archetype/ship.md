---
description: Roll out an already-built change with widening blast radius
argument-hint: "[release / change ref]"
phase_relevance: ["*"]
archetype_relevance: ["ship"]
---

# /wicked-garden:archetype:ship

Run the ship archetype: canary → ramp → full → soak. Produces a rollout verdict + SLO snapshot.

Invoke `wicked-garden:archetype` skill with archetype=ship. Loads `refs/ship.md`. Each phase boundary is a discrete ramp gate. Auto-pass under clean SLOs; auto-rollback under degraded SLOs.
