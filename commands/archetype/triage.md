---
description: Classify a prompt into a work-shape archetype and route to its playbook
argument-hint: "[prompt]"
phase_relevance: ["*"]
archetype_relevance: ["triage"]
---

# /wicked-garden:archetype:triage

Run the triage archetype: classify and route. Detect the work shape, then hand off.

Invoke the `wicked-garden:archetype` skill with archetype=triage. The skill loads `refs/triage.md` and runs the classify phase. When the prompt is empty, run the detector against the conversation context.
