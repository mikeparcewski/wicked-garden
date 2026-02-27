# Customer Journey Mapping

Map feedback to customer lifecycle stages for holistic insights.

## Journey Stages

```
Awareness → Evaluation → Onboarding → Adoption → Retention → Advocacy
```

## Stage Definitions

### 1. Awareness
**What**: Customer first hears about product
**Feedback Sources**:
- Marketing site feedback
- Social media mentions
- Comparison posts ("X vs Y")

**Key Metrics**:
- First impression sentiment
- Clarity of value proposition
- Competitive positioning

**Pain Points to Watch**:
- "Didn't understand what this does"
- "Confused about pricing"
- "Not clear how this differs from [competitor]"

---

### 2. Evaluation
**What**: Customer trying to decide if product fits needs
**Feedback Sources**:
- Trial feedback
- Demo requests
- Sales conversations

**Key Metrics**:
- Trial conversion sentiment
- Feature gap mentions
- Comparison to alternatives

**Pain Points to Watch**:
- "Missing feature X that competitor has"
- "Trial period too short to evaluate"
- "Couldn't test with my data"

---

### 3. Onboarding
**What**: Customer setting up and learning product
**Feedback Sources**:
- Setup support tickets
- Getting started documentation feedback
- Early usage confusion

**Key Metrics**:
- Time to first value
- Setup difficulty mentions
- Documentation clarity

**Pain Points to Watch**:
- "Setup is too complex"
- "Couldn't figure out how to [basic task]"
- "Documentation missing key steps"
- "Integration didn't work as expected"

---

### 4. Adoption
**What**: Customer expanding usage, becoming proficient
**Feedback Sources**:
- Feature requests
- Usage pattern feedback
- Training requests

**Key Metrics**:
- Feature discovery rate
- Power user emergence
- Team expansion requests

**Pain Points to Watch**:
- "Didn't know this feature existed"
- "Can't do [advanced task]"
- "Need more training resources"

---

### 5. Retention
**What**: Customer continues using, renews subscription
**Feedback Sources**:
- Renewal conversations
- Churn interviews
- Ongoing support tickets

**Key Metrics**:
- Renewal sentiment
- Churn reasons
- Competitive switching

**Pain Points to Watch**:
- "Thinking about switching to [competitor]"
- "Not seeing enough value for price"
- "Support quality declined"
- "Missing features I need"

---

### 6. Advocacy
**What**: Customer recommends product to others
**Feedback Sources**:
- Reviews and testimonials
- Referrals
- Case studies
- Social sharing

**Key Metrics**:
- NPS score
- Referral rate
- Public praise

**Signals to Amplify**:
- "I recommended this to my team"
- "Wrote a blog post about how we use this"
- "Can't imagine working without this"

## Journey Analysis Output

```markdown
## Customer Journey Insights

### Awareness → Evaluation
- **Strength**: Clear value proposition (78% positive sentiment)
- **Pain Point**: Pricing confusion (12 mentions)
- **Opportunity**: Clearer comparison to competitors

### Evaluation → Onboarding
- **Strength**: Easy trial signup (92% positive)
- **Pain Point**: Trial period too short (18 mentions)
- **Drop-off Risk**: Integration setup complexity

### Onboarding → Adoption
- **Strength**: Good documentation (65% positive)
- **Pain Point**: Advanced features hidden (23 mentions)
- **Opportunity**: Better feature discovery

### Adoption → Retention
- **Strength**: Core features solid (70% satisfaction)
- **Pain Point**: Missing bulk operations (45 mentions)
- **Risk**: Competitive pressure on mobile experience

### Retention → Advocacy
- **Strength**: Strong promoters (NPS 42)
- **Opportunity**: Make sharing easier, case study program
```

## Drop-off Analysis

Identify where customers struggle or leave:

```python
def analyze_dropoff(stage: str, feedback: list) -> dict:
    """
    Analyze customer friction at specific journey stage.

    Returns:
        {
            "stage": "onboarding",
            "dropoff_signals": 15,  # mentions of difficulty/confusion
            "top_blockers": ["setup complexity", "unclear docs"],
            "sentiment": "negative (42%)",
            "recommendation": "Simplify setup wizard, add video walkthrough"
        }
    """
```

## Cross-Stage Patterns

Look for issues that span multiple stages:

- **Onboarding → Adoption**: Feature discovery problems
- **Adoption → Retention**: Scalability concerns
- **Evaluation → Retention**: Unmet expectations

## Mapping Feedback to Stages

Use keywords and context:

```python
# Stage classification keywords
STAGE_KEYWORDS = {
    "awareness": ["heard about", "saw ad", "comparison"],
    "evaluation": ["trial", "demo", "considering"],
    "onboarding": ["setup", "getting started", "first time"],
    "adoption": ["how do I", "advanced", "power user"],
    "retention": ["renewal", "pricing", "value"],
    "advocacy": ["recommend", "love", "testimonial"]
}
```

## Strategic Insights

Journey analysis reveals:
1. **Biggest drop-off stage**: Where to focus improvement
2. **Smoothest transitions**: What's working well
3. **Segment differences**: Enterprise vs SMB journey variations
4. **Lifecycle value**: When customers see most value
