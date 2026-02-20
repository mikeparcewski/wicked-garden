---
name: new-developer-onboarding
title: New Developer Onboarding via Delivery Reporting
description: Use delivery reports to orient a new developer to team velocity, blockers, and project health
type: workflow
difficulty: basic
estimated_minutes: 8
---

# New Developer Onboarding via Delivery Reporting

This scenario validates that wicked-delivery helps new developers quickly understand team health, delivery patterns, and current blockers using the `/wicked-delivery:report` command. Rather than navigating unfamiliar codebases blind, new developers can read the delivery picture first.

## Setup

Create a realistic project export that a new developer would receive from their team lead:

```bash
# Create test directory
mkdir -p /tmp/wicked-delivery-onboarding

# Create a sprint export in CSV format (simulating a GitHub Issues or Jira export)
cat > /tmp/wicked-delivery-onboarding/team-status.csv <<'EOF'
id,title,status,priority,assignee,labels,created_at,updated_at,closed_at
101,Set up CI pipeline,done,P1,alice,infrastructure,2024-11-01,2024-11-03,2024-11-03
102,Implement user auth,done,P0,bob,feature,2024-11-01,2024-11-05,2024-11-05
103,Add rate limiting,in_progress,P1,alice,infrastructure,2024-11-05,2024-11-12,
104,Migrate legacy endpoints,in_progress,P1,carol,tech-debt,2024-11-04,2024-11-13,
105,Write API documentation,todo,P2,unassigned,docs,2024-11-06,2024-11-06,
106,Integrate payment provider,blocked,P0,bob,feature,2024-11-02,2024-11-13,
107,Add search functionality,todo,P2,unassigned,feature,2024-11-08,2024-11-08,
108,Fix session timeout bug,done,P0,carol,bug,2024-11-07,2024-11-09,2024-11-09
EOF

echo "Setup complete. Export at /tmp/wicked-delivery-onboarding/team-status.csv"
```

## Steps

### 1. Configure Delivery Metrics (Optional First-Time Setup)

If this is a first run, configure the cost model and cadence:

```
/wicked-delivery:setup
```

**Expected Output**:
- Interactive prompts for cost model type (skip or configure)
- Commentary sensitivity selection (Balanced recommended)
- Rolling window selection (14 days recommended)
- Aging threshold selection (7 days recommended)
- Settings written to `~/.something-wicked/wicked-delivery/settings.json`

Skip this step if settings already exist.

### 2. Generate a Delivery Report for the New Developer

Run the report command against the sprint export:

```
/wicked-delivery:report /tmp/wicked-delivery-onboarding/team-status.csv
```

**Expected Output**:
- Three persona reports generated: Delivery Lead, Engineering Lead, Product Lead
- Each report analyzes the same data from a different stakeholder lens
- Dry Boston-style commentary on any obvious patterns (lopsided assignments, aging items)

**Delivery Lead perspective should highlight**:
- Sprint completion rate (3/8 = 37% done)
- 1 blocked P0 task (payment provider integration)
- 2 unassigned items (documentation, search)
- Aging items flagged (tasks untouched for 7+ days)

**Engineering Lead perspective should highlight**:
- Tech debt item in progress (legacy endpoint migration)
- Capacity: two engineers with open items nearing sprint end
- Risk from P0 block affecting a feature dependency

**Product Lead perspective should highlight**:
- P0 feature blocked (payment provider) — high user impact
- Unassigned documentation gap
- Two P2 features not yet started

### 3. Get a Comprehensive View

Run with `--all` to also get QE, Architecture, and DevSecOps perspectives:

```
/wicked-delivery:report /tmp/wicked-delivery-onboarding/team-status.csv --all
```

**Expected Output**:
- Six persona reports generated
- QE Lead: test coverage gaps, defect density from bug count
- Architecture Lead: technical debt load vs. feature work ratio
- DevSecOps Lead: infrastructure tasks, security-adjacent concerns (auth, rate limiting)

### 4. Focus on What Matters Most to a New Developer

Run a focused analysis on just the delivery and product perspectives:

```
/wicked-delivery:report /tmp/wicked-delivery-onboarding/team-status.csv --personas delivery-lead,product-lead
```

**Expected Output**:
- Two-persona report: leaner output suitable for a quick read
- Delivery Lead and Product Lead sections only
- Same data, reduced noise

### 5. Save Output for Reference

Run with output directory to save the reports:

```
/wicked-delivery:report /tmp/wicked-delivery-onboarding/team-status.csv --output /tmp/wicked-delivery-onboarding/reports/
```

**Expected Output**:
- Report files written to specified directory
- Manifest file listing generated reports
- Confirmation of file paths

## Expected Outcome

- New developer understands current team delivery health in minutes
- Blockers surfaced immediately without reading every ticket
- Multiple stakeholder perspectives reveal different angles on the same data
- Reports are professional enough to share with a team lead or manager
- Plugin works standalone with a simple CSV export — no special tooling required

## Success Criteria

- [ ] `/wicked-delivery:setup` completes and writes settings to `~/.something-wicked/wicked-delivery/`
- [ ] `/wicked-delivery:report` accepts CSV file path and processes it without errors
- [ ] Default run generates 3 persona reports (Delivery Lead, Engineering Lead, Product Lead)
- [ ] `--all` flag generates 6 persona reports
- [ ] `--personas` flag limits output to specified personas
- [ ] `--output` flag writes reports to a directory with a manifest
- [ ] Blocked P0 task surfaced as a critical finding
- [ ] Unassigned items identified
- [ ] Aging items flagged based on settings thresholds
- [ ] Report content is professional and stakeholder-appropriate

## Value Demonstrated

A new developer joining a team typically spends their first days asking colleagues for context: "What are we working on? What's blocked? Where should I focus?" wicked-delivery's reporting capability answers these questions in minutes by analyzing existing project exports.

The multi-persona report gives a new developer:
1. **Team health at a glance** — completion rate, blockers, aging items
2. **Stakeholder framing** — understands what a delivery lead, engineering lead, and product lead each care about
3. **Actionable context** — knows which P0 blocker to ask about, which unassigned items they could pick up
4. **No special setup** — works with any CSV export from Jira, GitHub Issues, Linear, or Asana

## Cleanup

```bash
rm -rf /tmp/wicked-delivery-onboarding
```
