---
description: Live-fire production incident response — mitigate first, RCA second
argument-hint: "[INC-id or symptom]"
phase_relevance: ["*"]
archetype_relevance: ["incident"]
---

# /wicked-garden:archetype:incident

Run the incident archetype: triage → investigate → mitigate → resolve → followup. Produces mitigation + RCA + followup list.

Invoke `wicked-garden:archetype` skill with archetype=incident. Loads `refs/incident.md`. Mitigate gate is HARD — do not skip past it. Time-box investigate to 15 min during SEV-1.
