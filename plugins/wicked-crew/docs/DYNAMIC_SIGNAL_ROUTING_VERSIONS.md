# Dynamic Signal Routing: 4 Architecture Versions (Comparison + Best Pick)

Generated: 2026-02-23 UTC

## Goal
Compare four logical architecture versions for how **business + engineering signals** converge into **scoring, impact processing, and branching**, then select the strongest overview.

---

## Version 1 — Linear Pipeline (Simple Narrative)

```mermaid
flowchart LR
  A[Business + Engineering Inputs] --> B[Signal Detection]
  B --> C[Scoring\nImpact/Reversibility/Novelty]
  C --> D[Complexity Band\n0-2 / 3-4 / 5-7]
  D --> E[Branching\nFast/Expanded/Full]
  E --> F[Delivery + Gates]
```

**Pros**
- Easiest to read quickly.
- Good for executive one-slide storytelling.

**Cons**
- Weak plugin-level accountability.
- Feedback loops and adaptive re-branching are underrepresented.

---

## Version 2 — Plugin Swimlanes (Responsibility Clarity)

```mermaid
flowchart TB
  subgraph Crew[wicked-crew]
    C1[Signal Normalization]
    C2[Scoring + Complexity]
    C3[Branch Selection]
  end

  subgraph QE[wicked-qe]
    Q1[Change Tracking]
    Q2[Risk + Coverage Findings]
  end

  subgraph Eng[wicked-engineering]
    E1[Architecture/Design Inputs]
    E2[Review Findings]
  end

  subgraph Others[Platform/Product/Jam/Data/Delivery]
    O1[Specialist Evidence]
  end

  Q1 --> C1
  E1 --> C1
  C3 --> O1
  O1 --> Q2
  O1 --> E2
  Q2 --> C2
  E2 --> C2
```

**Pros**
- Strong ownership model per plugin.
- Good for implementation teams.

**Cons**
- Less explicit on branching thresholds and gate semantics.
- Harder for non-technical stakeholders.

---

## Version 3 — Decision Tree First (Branching Emphasis)

```mermaid
flowchart TD
  A[Unified Signal Set] --> B[Compute Complexity 0-7]
  B --> C{Score Band?}
  C -->|0-2| D[Fast Track\nclarify -> build -> review]
  C -->|3-4| E[Expanded Track\n+ design + test-strategy]
  C -->|5-7| F[Full Track\n+ ideate + test + full gates]
  D --> G[Outcome + Evidence]
  E --> G
  F --> G
  G --> H{New Risk Signals?}
  H -->|Yes| A
  H -->|No| I[Complete]
```

**Pros**
- Best view of branch behavior.
- Very strong for governance discussions.

**Cons**
- Signal source and role boundaries are abstracted away.
- Scoring dimensions are compressed into one step.

---

## Version 4 — Convergence Hub + Scoring Internals + Adaptive Loop (**Best Overall**)

The canonical Version 4 diagram is maintained in [`DYNAMIC_SIGNAL_ROUTING_ARCHITECTURE.md`](DYNAMIC_SIGNAL_ROUTING_ARCHITECTURE.md) (Section 1) to avoid duplication drift. See that file for the full Mermaid diagram with detailed node labels, plugin responsibility view, and branching semantics.

**Pros**
- Most complete representation of convergence, scoring internals, branching, routing, and feedback.
- Balances executive and engineering readability.
- Preserves the systemic "adaptive control loop" that matters for dynamic routing.

**Cons**
- Denser than V1/V3.

---

## Comparison Matrix

| Criterion | V1 | V2 | V3 | V4 |
|---|---:|---:|---:|---:|
| Executive readability | 5 | 3 | 4 | 4 |
| Plugin responsibility clarity | 2 | 5 | 2 | 4 |
| Scoring transparency | 2 | 3 | 3 | 5 |
| Branching clarity | 3 | 2 | 5 | 5 |
| Feedback/adaptation clarity | 1 | 3 | 4 | 5 |
| **Overall** | **13** | **16** | **18** | **23** |

## Recommendation
Use **Version 4** as the canonical architecture diagram.
- It is the best single overview for design, implementation, and governance.
- It explicitly shows the convergence of business + engineering signals into a numeric scoring-and-branching control process.
- It preserves the adaptive feedback mechanism required by dynamic routing.
