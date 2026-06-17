---
description: Port a legacy codebase to a new stack — discover/extract/blueprint/transform/parity/cutover
argument-hint: "[modernization target, e.g. 'port this AngularJS app to Angular']"
phase_relevance: ["*"]
archetype_relevance: ["modernize"]
---

# /wicked-garden:archetype:modernize

Run the modernize archetype: discover → extract → blueprint → transform → parity → cutover. Produces a modernization blueprint + a re-derivable parity proof. This is legacy→new-stack porting, NOT in-place shape change (that is `migrate`).

Invoke `wicked-garden:archetype` skill with archetype=modernize. Loads `refs/modernize.md`. The `discover` phase resolves the legacy stack class via `.claude-plugin/stack-registry.json` (reader: `scripts/crew/stack_registry.py`) — on an unknown/`planned`/`none` stack it emits a capability-gap task and STOPS rather than fabricating a port. Composes the general `code-modernization` skills (assess/extract-rules/reimagine/map/transform/harden); transform follows `engineering:large-scale-migration` (MAP→TRANSFORM→GATE, deterministic-before-AI). Cutover gate is HARD — parity proved + independent attestation before each ramp.
