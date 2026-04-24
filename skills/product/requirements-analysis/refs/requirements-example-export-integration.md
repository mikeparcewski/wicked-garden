# Requirements Output: Minimal Example & Integration Points

Minimal format example and integration points for requirements analysis output.

## Example: Data Export Feature (Minimal Format)

```markdown
# Requirements: CSV Export for Reports

## Summary
Enable managers to export report data to CSV for offline analysis in Excel.

## User Stories

### US-EXPORT-001: Export Report Data

**As a** manager
**I want to** export report data to CSV
**So that** I can analyze trends offline in Excel

**Priority**: P1
**Complexity**: M

**Acceptance Criteria**:
1. Given report data exists, When I click export, Then CSV downloads with all data
2. Given large dataset (10k+ rows), When I export, Then async job with email notification
3. Given no data in report, When I click export, Then message "No data to export"
4. Given CSV contains special characters, When I export, Then properly escaped for Excel

### US-EXPORT-002: Custom Date Range Export

**As a** manager
**I want to** select date range for export
**So that** I can focus on specific time periods

**Priority**: P2
**Complexity**: S

**Acceptance Criteria**:
1. Given date range selected, When I export, Then only data in range included
2. Given invalid date range (start > end), When I try export, Then validation error

## Out of Scope
- PDF export format
- Scheduled/recurring exports
- Custom column selection
- Multiple file format options (Excel, JSON, XML)

## Open Questions
- [ ] Max row limit for synchronous export? (suggest 10k)
- [ ] Column headers customizable?
- [ ] Include metadata (export date, user, filters)?
```

## Integration Points

### With native tasks
Store requirements as native tasks:
```
TaskCreate(
  subject="US-AUTH-001",
  description="$(cat requirements.md)",
  metadata={
    "event_type": "task",
    "chain_id": "auth.clarify",
    "source_agent": "requirements-analyst",
    "phase": "clarify",
    "priority": "P0",
    "initiative": "auth"
  }
)
```

### With wicked-brain:memory
Store for pattern recall:
```
Skill(skill="wicked-brain:memory", args="store \"auth-requirements-2026\" \"$(cat requirements.md)\"")
```

### With Wicked QE
Requirements feed test scenarios:
```
Requirements -> User Stories -> Acceptance Criteria -> Test Scenarios
```
