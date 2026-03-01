---
name: product-feedback
title: Product Feature Validation
description: Gather multi-stakeholder perspectives on a proposed feature
type: feature
difficulty: basic
estimated_minutes: 8
---

# Product Feature Validation

This scenario tests wicked-jam's ability to generate realistic user and stakeholder feedback on product ideas before investing in development.

## Setup

Create a product feature proposal:

```bash
# Create product planning directory
mkdir -p ~/test-wicked-jam/product-features
cd ~/test-wicked-jam/product-features

# Document a feature proposal
cat > feature-proposal.md <<'EOF'
# Feature Proposal: AI-Powered Search

## Description
Add natural language search to our project management tool.
Instead of: "filter:status=open assignee:me"
Users type: "show me my open tasks"

## Target Users
- 5000 existing users of our PM tool
- Mix of technical and non-technical
- Current search gets used 10x/day per user

## Investment
- 2 engineers x 6 weeks
- $20k for AI API costs (estimated)
- Maintenance: 20 hrs/month ongoing

## Question
Is this worth building?
EOF
```

## Steps

1. **Get Raw Perspectives Without Synthesis**
   ```bash
   /wicked-jam:perspectives "AI-powered natural language search for project management tool"
   ```

   Expected: 4-6 personas each provide their position, key concern, and what would change their mind. No synthesis or recommendation provided.

2. **Verify Perspective Structure**

   Check each persona includes:
   - **Position**: Their stance on the feature
   - **Key Concern**: What they worry about
   - **Would change mind if**: What evidence would shift their view

3. **Verify Perspective Diversity**

   Check for mix of viewpoints:
   - At least one supportive perspective
   - At least one skeptical perspective
   - Business vs. technical vs. user viewpoints
   - No obvious strawman arguments

4. **Run Full Brainstorm for Deeper Analysis**
   ```bash
   /wicked-jam:brainstorm "AI-powered search feature: worth 12 engineer-weeks?"
   ```

   Expected: Full session with rounds and synthesis that weighs tradeoffs

5. **Compare Outputs**

   Perspectives output should:
   - Present views without bias
   - Leave conclusion to user
   - Be faster/briefer

   Brainstorm output should:
   - Include persona discussion rounds
   - Synthesize a recommendation
   - Provide confidence-rated insights

## Expected Outcome

- `/perspectives` completes in under 90 seconds
- Perspectives reveal considerations you hadn't thought of
- `/brainstorm` provides deeper analysis with synthesis
- Both modes produce actionable insights
- Output helps decide: build, don't build, or investigate first

## Success Criteria

- [ ] `/perspectives` generates 4-6 relevant stakeholder personas
- [ ] Each perspective includes position, concern, and change condition
- [ ] No synthesis or recommendation provided in perspectives mode
- [ ] Perspectives include both supportive and skeptical views
- [ ] At least one persona represents end-user viewpoint
- [ ] At least one persona represents business/ROI concern
- [ ] `/brainstorm` mode provides synthesis with recommendation
- [ ] Insights surface non-obvious considerations (not just "pros and cons")

## Value Demonstrated

**Real-world value**: Product teams often skip user research or stakeholder alignment before building features, leading to wasted effort on features nobody wants. wicked-jam generates realistic stakeholder feedback in minutes, helping teams validate ideas before committing resources.

The `/perspectives` mode is perfect for self-directed thinking ("let me see different angles"), while `/brainstorm` mode provides a recommendation when you want guidance. This replaces the need for multiple stakeholder interviews or user research sessions at the validation stage, accelerating product decisions while still considering diverse viewpoints.
