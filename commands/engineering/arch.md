---
description: |
  Use when reviewing an existing system's architecture — evaluating component boundaries, coupling, layer
  violations, or recommending design patterns. Outputs ADR-style analysis with trade-offs.
  NOT for greenfield design (use the architecture skill) or code-level review (use engineering:review).
argument-hint: "[component or system] [--scope module|service|system]"
phase_relevance: ["design", "build"]
archetype_relevance: ["*"]
---

# /wicked-garden:engineering:arch

Architecture analysis of a component, service, or system. Evaluates boundaries, coupling, communication patterns, data architecture; flags scope-creep / unauthorized architectural changes when reviewing diffs. Use `engineering:arch` for component/system-level review; use `engineering:review` for code-level review.

## 1. Map structure + parse scope

Determine `--scope` (module|service|system; infer if absent). Map directory layout, entry points, dependencies, data flow.

## 2. Dispatch

```
Task(subagent_type="wicked-garden:engineering:system-designer",   # --scope module|service
     prompt="""Component: {name}  Structure: {layout}  Key files: {list}
Evaluate boundaries + responsibilities, interface contracts, dependency mgmt, coupling/cohesion.
If reviewing a diff, flag unauthorized architectural changes (new boundaries, swapped comm patterns, new deps) and scope creep.
Return strengths, concerns, recommendations, and trade-off table.""")

Task(subagent_type="wicked-garden:engineering:solution-architect",   # --scope system
     prompt="""System: {name}  Components: {list}
Evaluate decomposition, communication patterns, data architecture, scalability, operational concerns.
If reviewing a diff, flag unauthorized architectural changes + scope creep.
Return overview, strengths, concerns, strategic recommendations, trade-off table.""")
```
