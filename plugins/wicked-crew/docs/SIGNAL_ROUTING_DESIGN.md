# Intent-Driven Delivery: Design Rules & Scoring System

Traditional delivery treats every change the same — fixed gates, manual triage, rigid approvals regardless of actual risk. Intent-driven delivery replaces this with a deterministic, risk-adjusted architecture where governance is proportional to what the change actually does, not what category it belongs to. Every change — whether a regulatory policy update, a CTA button swap, or a database migration — enters a unified signal pipeline and exits through a governance lane matched to its actual risk profile. Intent before code. Scored, not staged. Guardrails replace gates.

---

## 1. Governing Principles

Four rules govern the entire architecture. Every design decision traces back to one of these.

### The Convergence Principle

All signals — business intent, engineering constraints, quality risks, compliance flags, operational telemetry — become shared decision inputs before any planning occurs. Functional areas do not operate in isolation or hand off siloed outputs. The system maintains a single unified signal graph as the source of truth.

### The Scoring Principle

Risk and delivery complexity are not subjective opinions. They are codified into explicit numeric controls via standardized dimensions with defined weights. The scoring engine produces a deterministic risk index that removes ambiguity from routing decisions. If you cannot measure a risk factor, it cannot influence the route.

### The Branching Principle

The depth of required process (governance lane) and the breadth of required domain expertise are not predetermined by team structure or change category. They are dynamically selected to match the exact risk profile of the specific work item. A low-risk infrastructure patch gets less overhead than a high-risk UI change, regardless of what team owns the code.

### The Feedback Principle

The architecture is self-correcting. Mid-execution findings from any domain — a security scan that finds a new vulnerability, a load test that reveals connection pool exhaustion, a quality review that uncovers missing coverage — are treated as *new signals* that force re-convergence. The system re-scores and may re-route work to a different governance lane mid-flight.

---

## 2. Signal Taxonomy

Changes emit data across seven signal streams. Every stream feeds the scoring engine regardless of whether the change originated as a business process or a software delivery task.

| Stream | What It Captures | Examples |
|--------|-----------------|----------|
| **User & Experience** | Journey friction, sentiment, conversion signals | NPS drop, session replay anomalies, accessibility violations, support ticket spikes |
| **Application** | Runtime health and feature behavior | Error rates, API latency, feature flag health, contract violations, exceptions |
| **Performance** | Capacity and responsiveness indicators | p99 latency, SLO attainment, resource utilization, throughput, connection pool depth |
| **Test Execution** | Quality evidence from all test phases | Coverage gaps, flaky test rates, mutation scores, contract test results, staging failures |
| **Data** | Data integrity and flow signals | Schema drift, pipeline lag, data quality scores, lineage breaks, PII detection |
| **Environment** | Infrastructure and configuration state | Config drift, IaC compliance, resource saturation, dependency advisories |
| **Security** | Threat and compliance indicators | CVE advisories, policy violations, access anomalies, PII exposure, encryption gaps, audit failures |

### Signal Normalization

Raw signals arrive in different formats and scales. Before scoring, every signal is normalized into standard categories with confidence values (0.0-1.0). This creates an equitable baseline for comparing fundamentally different types of risk — a HIPAA compliance flag and a p99 latency spike become comparable inputs rather than apples and oranges.

---

## 3. The Scoring Engine

The scoring engine converts normalized signals into a single **Weighted Risk Index** that determines the governance lane. The evaluation pipeline has a fixed order:

```
Signal Normalization → Domain Adjusters → Hard Rules → Weighted Calculation
```

Domain adjusters modify dimension scores *before* any routing decision is made. Hard rules are evaluated against the adjusted scores. The weighted calculation runs only if no hard rule triggers.

### Phase 1: Domain Adjusters (Pre-Scoring)

The scoring dimensions capture the *intent* of the work. Domain adjusters capture the *physical location* of the work. Not all domains carry the same inherent risk — a one-line change to an identity policy is fundamentally different from a one-line CSS change, even if both score identically on every other dimension.

Domain adjusters apply two modifications to dimension scores before any routing logic runs:

**Impact Amplification** — Certain domains inherently amplify risk. When the system detects that a change touches these domains, it applies an additive bonus to the Impact dimension score.

| Domain Class | Amplification | Examples |
|-------------|:---:|---|
| Presentation / Content | None | CSS changes, copy updates, static assets |
| Internal services / APIs | Moderate | Internal API contracts, shared libraries, message schemas |
| Infrastructure / Identity / Compliance | High | IAM policies, encryption config, audit systems, core data models |

**Complexity Floors** — Regardless of how low individual dimensions score, certain domains enforce a minimum governance level. A one-line change to an IAM policy is never "trivial" from a governance perspective.

| Floor Level | Domains | Effect |
|:-----------:|---------|--------|
| None | Presentation, content, cosmetic | Governance level determined purely by scoring |
| Moderate | APIs, data pipelines, mobile, real-time systems | Minimum Standard Path; ensures design and test strategy phases |
| High | Core infrastructure, security/identity, compliance-regulated, shared platforms | Minimum Elevated Review with mandatory specialist engagement |

Domain adjusters are configured from two sources: static rules that encode known organizational risk policies, and dynamic configuration that extends these based on observed patterns and historical incident data.

**Interaction with hard rules:** Because domain adjusters run first, they can prevent low-risk hard rules from firing. A change that would otherwise match "Trivial + reversible" (Rule 5) may have its Impact or Complexity elevated by a domain adjuster, causing the hard rule conditions to no longer be satisfied. This is by design — domain floors are non-negotiable policy constraints.

### Phase 2: Hard Rules (Deterministic Overrides)

Hard rules are non-negotiable policy constraints that override the weighted calculation. They exist because certain combinations of dimensions have organizational consequences that transcend risk math.

Rules are evaluated in strict priority order (1 through 5). Evaluation stops at the first match. When multiple rules could apply, the higher-priority rule wins.

| Priority | Rule | Conditions | Route | Rationale |
|:--------:|------|-----------|-------|-----------|
| 1 | Incident remediation | Urgency >= 0.8 AND Impact >= 0.7 AND an active anomaly or incident signal is present | Remediation Loop | Active incidents bypass standard governance for rapid response |
| 2 | Regulatory escalation | Regulatory >= 0.85 | Elevated Review | Compliance-sensitive changes require explicit human sign-off |
| 3 | Irreversible + dangerous | Reversibility <= 0.2 AND (Risk >= 0.7 OR Complexity >= 0.8) | Elevated Review | Hard-to-undo changes with high risk need extra scrutiny |
| 4 | Urgent + safe | Urgency >= 0.8 AND Complexity <= 0.25 AND Risk <= 0.3 AND Confidence >= 0.8 | Auto-Execute | Known-safe urgent fixes should not wait for humans |
| 5 | Trivial + reversible | Complexity <= 0.2 AND Risk <= 0.2 AND Reversibility >= 0.8 | Fast Track | Low-risk, easily reversible changes skip unnecessary gates |

If no hard rule triggers, the weighted calculation runs.

**Design note on Rule 1:** The incident remediation rule requires three conditions, not two. Urgency and Impact alone are insufficient — a high-urgency, high-impact *new feature launch* is not an incident. The presence of an active anomaly or incident signal from the Operate domain distinguishes genuine incident response from urgent planned work.

### Phase 3: Weighted Risk Index (Fallback)

When no hard rule matches, eight dimensions combine into a single index using predefined weights:

| Dimension | Weight | Direction | What It Measures |
|-----------|:------:|:---------:|-----------------|
| **Complexity** | 0.24 | Direct | Structural difficulty: number of components, cross-cutting concerns, architectural novelty |
| **Risk** | 0.24 | Direct | Implementation risk: likelihood of defects, integration failures, or unintended side effects |
| **Regulatory** | 0.18 | Direct | Compliance sensitivity: HIPAA, SOC2, GDPR, PCI, or industry-specific requirements |
| **Strategic** | 0.10 | Direct | Organizational impact: migration scope, coordination across teams, architectural shifts |
| **Urgency** | 0.10 | Direct | Time pressure: SLA deadlines, incident remediation, market windows |
| **Impact** | 0.06 | Direct | Blast radius: how many services, users, or revenue streams are affected |
| **Reversibility** | 0.05 | Inverse | Undo difficulty: feature-flagged = high, schema migration = low. *Inverted*: low reversibility increases risk |
| **Confidence** | 0.03 | Inverse | Certainty in the approach: proven pattern = high, greenfield = low. *Inverted*: low confidence increases risk |

**Inverse dimensions** are transformed before weighting: `transformed = 1 - raw_value`. This means low reversibility (hard to undo) contributes *more* to the risk index, not less.

**The calculation:**

```
For each dimension with a score:
    transformed = (1 - value) if inverted, else value
    contribution = transformed × weight

Weighted Risk Index = sum(contributions) / sum(active_weights)
```

Only dimensions with actual scores participate. If a change has no regulatory component, that dimension is excluded from both numerator and denominator, preventing zero scores from artificially deflating the index.

**Design note on Urgency:** Urgency is a Direct dimension because time pressure genuinely increases delivery risk — rushed work has higher defect rates. The "Urgent + safe" hard rule (Priority 4) exists specifically to handle the case where urgency is high but all other risk indicators are low. When the hard rule fires, it overrides the weighted calculation entirely. When it does not fire (e.g., Confidence < 0.8), the elevated risk index from urgency is intentional: an urgent change where confidence is not high *should* receive additional scrutiny.

**Design note on Impact weight:** Impact carries the lowest Direct weight (0.06) because blast radius is better addressed through domain adjusters than through the general scoring formula. Domain adjusters amplify Impact for high-risk domains before the weighted calculation runs, making the effective contribution of Impact domain-dependent rather than uniform. A small base weight prevents double-counting when domain adjusters are active, while still contributing to the index when no adjuster applies.

---

## 4. Governance Lanes

The risk index maps to one of five governance lanes. Each lane defines the depth of process, the gates required, and the human involvement expected.

| Lane | Risk Index | Character | Human Involvement |
|------|:----------:|-----------|-------------------|
| **Auto-Execute** | Hard rule only | Known-safe automation. Dependency patches, config bumps, proven remediation patterns. | Post-hoc review only |
| **Fast Track** | <= 0.22 | Minimal friction for low-risk work. Feature-flagged changes, copy updates, styling. | Monitor outcomes |
| **Standard Path** | <= 0.58 | Full automation with complete traceability. Most feature work lives here. | Review artifacts, not gates |
| **Elevated Review** | > 0.58 or hard rule | Explicit human sign-off required. Regulatory, irreversible, or architecturally significant changes. | Approve at gates |
| **Remediation Loop** | Hard rule only | Active incident response. Automated diagnostics, remediation, and hardening with human review after stabilization. | Validate learnings post-incident |

### Lane Characteristics

**Auto-Execute** activates only when hard rules confirm the pattern is safe: high urgency, low complexity, low risk, high confidence, and a known remediation pattern. Full traceability is preserved — automation does not mean unmonitored.

**Fast Track** is governance right-sized to actual risk. A CTA button color change does not need an architecture review board. It gets visual regression validation and outcome monitoring — the minimum gates necessary for its risk level.

**Standard Path** is the default for most work. Quality contracts are designed before code, architecture drift is checked automatically, coverage thresholds are enforced, and contract tests validate integration boundaries. All automated; humans review the artifacts, not the gates.

**Elevated Review** adds explicit human decision points. A Security Lead validates threat models. A Compliance Officer confirms evidence coverage. An executive accepts residual risk. These are not rubber stamps — they are informed decisions supported by machine-generated evidence packages.

**Remediation Loop** is a parallel workflow mode rather than a governance depth level. It handles active incidents where the priority is stabilization, not process. The system diagnoses, remediates, and hardens — then presents the full learning package to a human for review. The human validates the fix and the permanent hardening (new tests, scoring model updates), not the triage.

---

## 5. Delivery Domains

Five functional domains collaborate to deliver work. Each domain has specific capabilities, produces specific artifacts, and feeds signals back into the scoring engine. Domain names and capabilities are illustrative — organizations may structure their domains differently while preserving the signal flow patterns described here.

### Intent & Strategy

Ingests raw signals to produce structured, testable demand. Receives feature requests, business goals, policy changes, and change proposals. Enriches them with historical context — which similar changes have failed, what edge cases burned the team before, what acceptance criteria are commonly missed. Outputs structured demand specs with testable criteria.

**Capabilities:** Signal ingestion and enrichment, value stream mapping, acceptance criteria generation, priority scoring, demand structuring, persona context from organizational memory.

**Gates:** Intent clarity threshold met. Value stream alignment confirmed. Testability validation passed. Stakeholder sign-off (Elevated Review only).

### Quality Design

Synthesizes risk-based test strategies before implementation exists. Does not wait for implementation to think about testing. Designs persona journeys, executable specifications, and coverage targets based on the structured demand and historical defect patterns.

**Capabilities:** Test strategy synthesis, persona journey generation, executable spec creation, coverage and gap analysis, defect spec generation, risk-based prioritization.

**Gates:** Coverage threshold met. Persona journeys validated. Executable specs generated. Risk matrix approved.

### Build & Craft

Scaffolds implementation using organizational patterns with real-time drift detection. Enforces consistency — the same state management approach, the same encryption library, the same contract test patterns. Flags deviations before they become drift.

**Capabilities:** Pattern-based scaffolding, architecture drift detection, implementation assistance, contract test generation, automated review, dependency validation.

**Gates:** Architecture drift check passed. Review approved. Contract tests green. Dependency scan clean.

### Security & Compliance

Defense-in-depth with proactive threat modeling. Not a gate at the end of the pipeline — an active participant that scans artifacts as they are produced, models threats specific to the change (not generic checklists), and packages evidence for audit readiness.

**Capabilities:** Threat modeling (STRIDE), software bill of materials generation, data classification, vulnerability feed integration, compliance evidence packaging, policy-as-code enforcement.

**Gates:** Threat model approved. SBOM signed. Static/dynamic analysis clean. Compliance attestation complete. Security lead sign-off (Elevated Review only).

### Operate & Evolve

Closed-loop feedback with automated remediation. Monitors production health, detects anomalies, executes proven runbooks, and feeds incident learnings back into the scoring engine so the system gets smarter with every event.

**Capabilities:** Anomaly detection, automated remediation runbooks, progressive canary promotion, SLO monitoring, incident-to-defect pipeline, experience intelligence.

**Gates:** Canary metrics stable. SLO thresholds met. Rollback capability confirmed. Runbook validation passed.

### Cross-Domain Signal Flow

Every domain both consumes and produces signals:

- **Intent** feeds structured demand to Quality Design, provides strategic context to the Scoring Engine, and receives outcome data from Operate.
- **Quality Design** receives demand from Intent, feeds executable contracts to Build, and provides coverage data to the Scoring Engine.
- **Build** receives quality contracts from Quality Design, reports drift signals to the Scoring Engine, and feeds artifacts to Security.
- **Security** receives artifacts from Build, feeds compliance status to the Scoring Engine, and provides threat context to Quality Design.
- **Operate** receives promotion candidates from Build, feeds incident data back to Quality Design and the Scoring Engine, and shares telemetry with Intent.

This creates a continuous loop: every delivery event enriches the system's understanding of risk, which calibrates future routing decisions.

---

## 6. The Adaptive Loop

The architecture is not a pipeline with a fixed sequence. It is an adaptive loop where the scoring engine continuously re-evaluates as new information emerges.

### How Re-Convergence Works

1. A change enters the system and receives an initial score and lane assignment.
2. Work proceeds through the assigned governance lane.
3. Domain work produces new signals: a security scan finds a dependency vulnerability, a load test reveals latency under concurrency, a quality review discovers missing coverage for an edge case.
4. New signals are injected into the unified signal graph.
5. The scoring engine re-evaluates. If the risk index crosses a lane threshold, the change is re-routed.
6. A change that started on the Fast Track can escalate to Standard Path or Elevated Review mid-flight if evidence warrants it.

### Escalation and De-Escalation

**Escalation** (upward re-routing) happens automatically when new signals raise the risk index above the current lane's threshold. No human approval is required to escalate — the system always defaults to the safest lane supported by evidence.

**De-escalation** (downward re-routing) requires stronger evidence than escalation, because under-governing is more dangerous than over-governing:

- De-escalation is only permitted when a re-score produces a risk index below the *lower* lane's threshold (not merely below the current lane's).
- De-escalation can only move one lane at a time. A change on Elevated Review can de-escalate to Standard Path, but not directly to Fast Track.
- De-escalation from Elevated Review to Standard Path requires explicit human authorization, because the original escalation to Elevated Review may have been triggered by a hard rule or domain floor that cannot be overridden by a lower risk index alone.
- De-escalation from Standard Path to Fast Track is automatic if the re-scored index supports it and no domain floor prevents it.

### How the System Learns

Every completed change produces learning artifacts:

- **Scoring calibration:** If a change was routed to Fast Track but caused a production incident, the scoring model adjusts. The specific signal pattern that led to under-scoring now carries a higher weight or triggers a new hard rule.
- **Domain memory:** Historical decisions, incident patterns, and defect rates are retained as organizational memory. When a similar change arrives, the system recalls: "Cart features have a 40% higher defect rate around session boundaries" or "Catalog structure changes that affect search facets need performance validation."
- **Test hardening:** Incidents generate permanent regression tests. A connection pool exhaustion at 2 AM becomes a load test that runs before every catalog update, forever.

The system does not simply execute — it observes, learns, and evolves. Every incident makes the scoring model more accurate. Every delivery cycle refines the governance calibration.

---

## 7. Context Categories

The scoring engine, delivery domains, and adaptive loop all rely on contextual information that falls into four categories. These categories govern how information is stored, retrieved, and weighted in future routing decisions.

| Category | What It Contains | Persistence |
|----------|-----------------|-------------|
| **Memory** | Past decisions, incident patterns, defect rates, team-specific learnings | Subject to retention policy: accessed frequently = retained indefinitely; unaccessed = decays over time (decay mechanism is implementation-defined) |
| **Knowledge** | Domain expertise, architecture constraints, regulatory requirements, organizational policies | Stable; updated when policies or architecture change |
| **Tooling** | Machine-generated artifacts: test specs, threat models, coverage reports, contract tests, evidence packages | Generated per change; archived after delivery for audit reference |
| **Human Interface** | Explicit human decisions: approvals, risk acceptance, experiment promotion, override rationale | Logged permanently for audit trail; never decays |

These categories also inform the adaptive loop: Memory and Knowledge shape initial scoring (historical patterns affect how dimensions are weighted), Tooling artifacts provide evidence for mid-flight re-scoring, and Human Interface decisions create permanent precedents that influence future hard rules and domain adjusters.

---

## 8. Design Constraints

### Proportionality

Governance overhead must be proportional to actual risk. A CSS color change and a database migration should not pass through the same gates. The scoring engine exists specifically to enforce this — more risk means more scrutiny, less risk means less friction, with no exceptions for "category-based" governance that treats all changes equally.

### Determinism

Given the same inputs, the scoring engine must produce the same output. Hard rules are evaluated in a fixed priority order. Weights are predefined, not negotiated per-change. Domain adjusters apply consistently. This eliminates the "it depends on who's reviewing" problem.

### Transparency

Every routing decision must be explainable. The system must be able to answer: "Why did this change get routed to Elevated Review?" with a specific trace: which domain adjusters applied, which hard rules triggered (or which weighted dimensions contributed most), and what the risk index was. No black boxes.

### Graceful Escalation

The system defaults to the safest reasonable lane, not the fastest. When confidence is low or signals are ambiguous, the scoring engine should route to a higher governance lane rather than a lower one. Under-governing is more dangerous than over-governing; over-governing is merely slow.

### Human Authority

Automation accelerates but does not replace human judgment on irreversible, high-stakes decisions. The system generates evidence packages, surfaces risks, and recommends actions. Humans approve or override. The Remediation Loop automates response but requires human validation of permanent changes (new tests, scoring adjustments, architectural hardening).

### Continuous Calibration

The scoring model is never "done." Every production incident is a calibration event. Every change that was under- or over-governed is a signal that weights, thresholds, or hard rules need adjustment. The system maintains a feedback loop between outcomes and scoring parameters.
