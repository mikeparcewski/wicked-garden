---
name: requirements-elicitation
title: Requirements Elicitation from Vague Brief
description: Transform an ambiguous product request into clear, testable user stories
type: requirements
difficulty: basic
estimated_minutes: 10
---

# Requirements Elicitation from Vague Brief

This scenario tests wicked-product's ability to extract clear requirements from an ambiguous product brief, generating well-formed user stories with testable acceptance criteria.

## Setup

Create a realistic but vague product brief:

```bash
# Create test project
mkdir -p ~/test-wicked-product/mobile-payments
cd ~/test-wicked-product/mobile-payments

# Create a vague product brief (intentionally incomplete)
cat > brief.md <<'EOF'
# Mobile Payment Feature

## Background
Our e-commerce app needs mobile payments. Customers have been asking for it.

## What We Want
- Apple Pay
- Google Pay
- Maybe Samsung Pay?

## Timeline
Q2 launch ideally

## Notes from Stakeholder Meeting
- Security is important
- Should work like competitors
- Marketing wants it for the Spring campaign
EOF
```

## Steps

1. **Run Requirements Elicitation**
   ```bash
   /wicked-product:elicit brief.md
   ```

   **Expected**: The requirements-analyst agent should:
   - Identify gaps in the brief (missing personas, undefined "work like competitors")
   - Ask clarifying questions or note assumptions
   - Generate user stories with specific personas

2. **Verify User Story Quality**

   Check that each user story follows the format:
   ```
   As a [specific persona]
   I want [specific capability]
   So that [measurable benefit]
   ```

   Stories should NOT be vague like:
   - "As a user, I want payments to work"
   - "As a customer, I want good UX"

3. **Verify Acceptance Criteria**

   Each story should have Given/When/Then criteria:
   ```
   Given [context]
   When [action]
   Then [observable outcome]
   ```

   Check for:
   - Happy path scenario
   - At least one error scenario
   - Edge case considerations

4. **Check for Open Questions**

   The output should surface things that need stakeholder input:
   - What happens if payment fails?
   - Which currencies supported?
   - Refund handling?
   - What does "work like competitors" mean specifically?

5. **Review Priority and Complexity**

   Stories should have:
   - Priority (P0/P1/P2)
   - Complexity estimate (S/M/L/XL)
   - Dependencies identified

## Expected Outcome

- 5-8 user stories covering core payment flows
- Each story has 2-4 acceptance criteria
- Open questions list surfaces gaps in brief
- Assumptions are documented
- Stories are specific enough to estimate and test

## Success Criteria

- [ ] User stories have specific personas (not generic "user")
- [ ] Each story has at least 2 acceptance criteria
- [ ] At least one error/edge case per story
- [ ] Open questions list identifies 3+ gaps in original brief
- [ ] Security requirements mentioned (given the brief mentioned it)
- [ ] Dependencies mapped between stories
- [ ] Assumptions explicitly stated
- [ ] Output is actionable for engineering team

## Value Demonstrated

**Real-world value**: Product teams often receive vague requirements like "add mobile payments" and must translate them into engineering tasks. Without structured elicitation, critical details get missed until implementation, causing rework and scope creep.

wicked-product's `/elicit` command acts like a skilled BA (business analyst), asking the questions that prevent downstream problems. The structured output (user stories with Given/When/Then acceptance criteria) becomes directly usable by engineering and QE teams, reducing the translation layer between product and engineering.

This replaces multiple rounds of back-and-forth between product and engineering, while ensuring nothing falls through the cracks.
