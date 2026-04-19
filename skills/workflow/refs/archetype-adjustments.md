# Archetype Adjustments

11 project archetypes with detection keywords and scoring adjustments.
Archetypes adjust impact scoring and inject relevant signals based on what
actually matters for the project type.

---

## Archetype Detection

An archetype is detected when **at least 2** of its keywords match the input
text. Single-keyword matches do not trigger an archetype (prevents false
positives like "scoring" alone triggering infrastructure-framework).

Confidence = min(matched_count / (total_keywords * 0.3), 1.0)

Multiple archetypes can be detected simultaneously. The highest-confidence
archetype is the `primary_archetype`.

---

## Adjustment Format

| Field | Meaning |
|-------|---------|
| `impact_bonus` | Added to impact score before composite calculation |
| `inject_signals` | Signals auto-added if not present (with given confidence) |
| `min_complexity` | Floor for complexity score — prevents underscoring |
| `description` | Why this archetype matters for scoring |

---

## Archetype Table

### content-heavy

| Field | Value |
|-------|-------|
| impact_bonus | +1 |
| inject_signals | `product: 0.3` |
| min_complexity | 2 |
| description | Content-heavy: messaging consistency and factual accuracy matter |

**Detection keywords**: content, copy, messaging, blog, cms, landing page,
marketing, seo, editorial, article, headline, brand, tone, voice, paragraph,
section copy, fact*, consistency, wording

---

### ui-heavy

| Field | Value |
|-------|-------|
| impact_bonus | +1 |
| inject_signals | `ux: 0.3` |
| min_complexity | 2 |
| description | UI-heavy: design consistency and user experience require review |

**Detection keywords**: component, design system, css, layout, responsive,
animation, theme, style, visual, frontend, react, vue, angular, dashboard,
widget, button, form, modal, sidebar, navigation, menu, look and feel, differentiation

---

### api-backend

| Field | Value |
|-------|-------|
| impact_bonus | +1 |
| inject_signals | _(none)_ |
| min_complexity | 2 |
| description | API/Backend: integration surface and contract stability matter |

**Detection keywords**: api, rest, graphql, endpoint, service, server, backend,
database, query, orm, grpc, websocket, microservice, gateway, proxy, contract

---

### infrastructure-framework

| Field | Value |
|-------|-------|
| impact_bonus | +2 |
| inject_signals | `architecture: 0.3` |
| min_complexity | 3 |
| description | Infrastructure/Framework: core execution path changes have broad impact |

**Detection keywords**: plugin, framework, build system, ci/cd, scaffold, hook,
middleware, engine, core, execution, routing, dispatch, orchestrat*, phase,
workflow, configuration, tooling, cli, command, agent, prompt engineering,
behavior, core path, execution path, foundational

---

### data-pipeline

| Field | Value |
|-------|-------|
| impact_bonus | +1 |
| inject_signals | `data: 0.3` |
| min_complexity | 2 |
| description | Data pipeline: data quality, lineage, and downstream effects matter |

**Detection keywords**: etl, pipeline, data flow, transform, warehouse, lake,
batch, stream, ingest, extract, load, lineage, dbt, airflow, spark

---

### mobile-app

| Field | Value |
|-------|-------|
| impact_bonus | +1 |
| inject_signals | `ux: 0.3` |
| min_complexity | 2 |
| description | Mobile app: platform constraints, UX patterns, and release cycles matter |

**Detection keywords**: ios, android, mobile, react native, flutter, swift,
kotlin, app store, play store, push notification, offline, gesture

---

### ml-ai

| Field | Value |
|-------|-------|
| impact_bonus | +1 |
| inject_signals | `data: 0.3` |
| min_complexity | 3 |
| description | ML/AI: model quality, training data, and evaluation rigor matter |

**Detection keywords**: model, training, inference, embedding, vector, llm,
fine-tune, prompt, rag, evaluation, benchmark, dataset, feature engineering,
hyperparameter

---

### compliance-regulated

| Field | Value |
|-------|-------|
| impact_bonus | +2 |
| inject_signals | `compliance: 0.5, security: 0.3` |
| min_complexity | 3 |
| description | Compliance/Regulated: audit trails, policy adherence, and risk documentation matter |

**Detection keywords**: hipaa, soc2, gdpr, pci, audit, compliance, regulation,
phi, pii, data protection, retention, consent, privacy

---

### monorepo-platform

| Field | Value |
|-------|-------|
| impact_bonus | +2 |
| inject_signals | `architecture: 0.3` |
| min_complexity | 3 |
| description | Monorepo/Platform: cross-package impact, shared dependencies, and versioning matter |

**Detection keywords**: monorepo, workspace, package, shared, library, dependency,
nx, turborepo, lerna, cross-package, internal package, versioning

---

### real-time

| Field | Value |
|-------|-------|
| impact_bonus | +1 |
| inject_signals | `performance: 0.3` |
| min_complexity | 2 |
| description | Real-time: latency, concurrency, and state synchronization matter |

**Detection keywords**: websocket, real-time, realtime, streaming, push,
event-driven, pubsub, message queue, kafka, rabbitmq, socket, live update

---

### text-as-code

| Field | Value |
|-------|-------|
| impact_bonus | +2 |
| inject_signals | `architecture: 0.3, text-as-code: 0.7` |
| min_complexity | 3 |
| description | Text-as-code: commands/agents/skills/hooks are behavioral programs — instruction changes affect crew routing, gate enforcement, and QE coverage |

**Detection keywords**: _(detected via text-as-code signal category rather than its own keyword list — see signal-keywords.md)_

---

## Application Order

1. Detect all matching archetypes from input text
2. Sort by confidence (highest first)
3. Apply adjustments from each detected archetype:
   - `impact_bonus` is applied once per archetype (additive)
   - `inject_signals` is merged into signal_confidences (max wins)
   - `min_complexity` takes the maximum floor across all archetypes
4. After all archetype adjustments, re-run specialist selection with updated signals
