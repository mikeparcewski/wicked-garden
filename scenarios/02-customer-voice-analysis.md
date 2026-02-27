---
name: customer-voice-analysis
title: Customer Feedback Theme Extraction
description: Aggregate and analyze customer feedback to identify actionable themes
type: research
difficulty: intermediate
estimated_minutes: 12
---

# Customer Feedback Theme Extraction

This scenario tests wicked-product's customer voice capabilities: aggregating feedback from multiple sources, extracting themes, and generating actionable recommendations.

## Setup

Create simulated customer feedback from multiple channels:

```bash
# Create test project
mkdir -p ~/test-wicked-product/customer-voice/feedback
cd ~/test-wicked-product/customer-voice

# Simulate support tickets
cat > feedback/support-tickets.md <<'EOF'
# Recent Support Tickets

## TICKET-001 (2026-01-20)
**From**: enterprise-customer@bigcorp.com
**Severity**: High
The export to PDF feature takes over 5 minutes for reports with more than 100 rows. This is blocking our monthly reporting cycle. We need this fixed ASAP.

## TICKET-002 (2026-01-18)
**From**: sarah.m@startup.io
**Severity**: Medium
Would love keyboard shortcuts for common actions. I use the app 6+ hours a day and clicking through menus is slow.

## TICKET-003 (2026-01-15)
**From**: ops@retailco.com
**Severity**: High
PDF exports are incredibly slow. We have to start them before lunch and hope they finish by end of day. This is ridiculous for a "productivity" tool.

## TICKET-004 (2026-01-14)
**From**: michael@agency.co
**Severity**: Low
The dark mode is nice but some text is hard to read. Specifically in the sidebar where the contrast seems low.
EOF

# Simulate NPS survey responses
cat > feedback/nps-responses.md <<'EOF'
# NPS Survey Responses (Jan 2026)

## Score: 3 (Detractor)
"Export is too slow. I've switched to [Competitor] for anything involving large datasets."

## Score: 8 (Promoter)
"Love the product overall. Main complaint is no mobile app - I often need to check things from my phone."

## Score: 6 (Passive)
"Good tool but the learning curve is steep. Took my team 2 weeks to get comfortable. Better onboarding would help."

## Score: 4 (Detractor)
"Performance has gotten worse over the past 6 months. Especially exports and bulk operations."

## Score: 9 (Promoter)
"Great for my workflow. Keyboard shortcuts would make it perfect - I hate reaching for the mouse."

## Score: 5 (Passive)
"Decent but nothing special. Export feature needs work - it's embarrassingly slow."
EOF

# Simulate feature request board
cat > feedback/feature-requests.md <<'EOF'
# Feature Request Board

## Keyboard Shortcuts (142 votes)
Users want Vim-style or configurable keyboard shortcuts for power users.
Top comment: "I would pay double for keyboard navigation"

## Mobile App (98 votes)
Native iOS/Android app for viewing and basic editing on the go.
Top comment: "Even read-only access would be huge"

## Faster Exports (87 votes)
PDF and CSV exports time out on large datasets.
Top comment: "Had to write a Python script to do what your export button should do"

## Better Onboarding (45 votes)
Interactive tutorials, templates, and getting-started guides.
Top comment: "Watched 3 YouTube videos before I could do basic tasks"
EOF
```

## Steps

1. **Aggregate Feedback**
   ```bash
   /wicked-product:listen feedback/
   ```

   **Expected**: Should scan all feedback sources and report:
   - Total feedback items
   - Sources discovered
   - Date range
   - Quick sentiment overview

2. **Analyze Themes and Sentiment**
   ```bash
   /wicked-product:analyze --theme "performance"
   ```

   **Expected**:
   - Identify "export performance" as critical theme
   - Calculate sentiment (mostly negative for this theme)
   - Show supporting quotes
   - Quantify impact (multiple customers, high severity)

3. **Generate Recommendations**
   ```bash
   /wicked-product:synthesize --priority high
   ```

   **Expected prioritized recommendations**:
   1. Fix export performance (clear business impact)
   2. Add keyboard shortcuts (high engagement signal)
   3. Mobile app (strong demand, competitive gap)
   4. Onboarding improvements (reduces support burden)

4. **Verify Theme Grouping**

   Check that related feedback is grouped:
   - "PDF export slow" + "exports time out" + "performance worse" = ONE theme
   - Not counted as separate issues

5. **Check Business Impact Language**

   Recommendations should include:
   - Customer quotes that resonate with leadership
   - Quantified impact (votes, severity, churn risk)
   - Not just "customers want X" but "X is causing Y business problem"

## Expected Outcome

- Clear theme hierarchy (not just a list of every complaint)
- Prioritization based on impact, not just volume
- Actionable recommendations, not just analysis
- Business case for top priorities

## Success Criteria

- [ ] Listen aggregates from all 3 feedback sources
- [ ] Analyze correctly groups "export slow" feedback (3+ mentions)
- [ ] Sentiment analysis identifies export as negative/critical
- [ ] Synthesize produces prioritized list (not alphabetical or arbitrary)
- [ ] Export performance ranks as #1 priority (clear signal)
- [ ] Customer quotes included as evidence
- [ ] Recommendations are actionable (not "improve performance")
- [ ] Churn risk mentioned (detractor explicitly cited competitor)

## Value Demonstrated

**Real-world value**: Product teams drown in feedback from support tickets, NPS surveys, feature requests, social media, and sales calls. Without synthesis, every customer complaint feels urgent, leading to reactive roadmaps driven by the loudest voice.

wicked-product's customer voice workflow (listen -> analyze -> synthesize) transforms scattered feedback into prioritized insights. The theme grouping prevents double-counting (one issue mentioned 5 times isn't 5 issues), and the business impact framing helps PMs communicate priorities to leadership.

This replaces expensive Voice of Customer (VoC) tools and manual spreadsheet analysis, while providing the evidence-based prioritization that data-driven product teams need.
