---
name: maturity-model
description: |
  Five-level maturity assessment model for agentic systems from prototype to optimized production.
  Use when: "agent maturity", "production readiness", "how mature is my agent", "agent assessment"
---

# Agentic System Maturity Model

Framework for assessing and advancing the maturity of agentic systems across five levels.

## The Five Levels

### Level 0: Prototype
**Definition:** Proof of concept, demonstrates core functionality.

**Characteristics:**
- Single agent or simple multi-agent setup
- Hardcoded prompts and logic
- No error handling
- No observability
- No safety guardrails
- Works in happy path only

**Appropriate for:** Experiments, demos, early exploration

### Level 1: Functional
**Definition:** Works reliably for basic scenarios, handles common errors.

**Characteristics:**
- Multiple specialized agents
- Basic error handling (try/catch)
- Simple logging
- Timeout mechanisms
- Manual testing only
- Configuration externalized

**Appropriate for:** Internal tools, limited user testing

### Level 2: Reliable
**Definition:** Production-ready for limited scale, monitored and tested.

**Characteristics:**
- Comprehensive error handling
- Structured logging and basic tracing
- Automated testing (unit + integration)
- Human-in-the-loop for high-stakes actions
- Basic safety guardrails
- Incident response process

**Appropriate for:** Production with limited users, internal production use

### Level 3: Production
**Definition:** Scaled production system, handles load and failures gracefully.

**Characteristics:**
- Scales horizontally
- Advanced observability (logs, metrics, traces)
- Comprehensive safety system
- Automated testing and deployment
- SLOs and SLA tracking
- Cost monitoring and optimization

**Appropriate for:** Large-scale production, external users

### Level 4: Optimized
**Definition:** Continuously improving, data-driven optimization.

**Characteristics:**
- A/B testing of prompts and strategies
- Automated performance optimization
- Self-healing capabilities
- Advanced cost optimization
- Real-time quality monitoring
- Feedback loops for improvement

**Appropriate for:** Mature, business-critical systems

## Maturity Dimensions

Assess maturity across these dimensions:

### 1. Reliability
- **L0:** Works sometimes
- **L1:** Works for common cases
- **L2:** Handles errors gracefully
- **L3:** Self-recovers from failures
- **L4:** Predicts and prevents failures

### 2. Observability
- **L0:** No logging
- **L1:** Print statements
- **L2:** Structured logs + basic metrics
- **L3:** Distributed tracing + dashboards
- **L4:** Real-time analytics + predictive monitoring

### 3. Safety
- **L0:** No guardrails
- **L1:** Basic input validation
- **L2:** Human-in-the-loop for risky actions
- **L3:** Comprehensive safety system
- **L4:** ML-powered anomaly detection

### 4. Testing
- **L0:** Manual only
- **L1:** Some unit tests
- **L2:** Automated test suite (70%+ coverage)
- **L3:** Integration + e2e + load testing
- **L4:** Continuous testing + mutation testing

### 5. Scalability
- **L0:** Single instance
- **L1:** Handles 10s of requests
- **L2:** Handles 100s of requests
- **L3:** Handles 1000s of requests
- **L4:** Auto-scales based on load

### 6. Cost
- **L0:** No tracking
- **L1:** Manual tracking
- **L2:** Automated tracking
- **L3:** Per-request cost monitoring
- **L4:** Automated optimization

## Quick Self-Assessment

Rate your system (0-4) on each dimension:

```
Reliability:     [ ]
Observability:   [ ]
Safety:          [ ]
Testing:         [ ]
Scalability:     [ ]
Cost:            [ ]

Average Score:   [ ]
```

**Overall Maturity Level:**
- Average 0-0.5: Level 0 (Prototype)
- Average 0.5-1.5: Level 1 (Functional)
- Average 1.5-2.5: Level 2 (Reliable)
- Average 2.5-3.5: Level 3 (Production)
- Average 3.5-4.0: Level 4 (Optimized)

## Anti-Patterns by Level

**L0-L1 Mistakes:**
- Deploying prototype to production
- No error handling
- Hardcoded secrets

**L1-L2 Mistakes:**
- No testing before production
- Print statements in production
- No monitoring

**L2-L3 Mistakes:**
- Single instance in production
- No cost tracking
- Manual deployments at scale

**L3-L4 Mistakes:**
- Not investing in automation
- Ignoring user feedback
- No continuous improvement culture

## When to Use

Trigger phrases indicating you need this skill:
- "Is my agentic system production-ready?"
- "What's missing before we can scale?"
- "How mature is our agentic system?"
- "What should we build next?"
- "Are we ready to launch?"

## References

- `refs/assessment-rubric.md` - Detailed scoring rubric, must-have checklists, exit criteria, and progression guidance for each dimension and level
