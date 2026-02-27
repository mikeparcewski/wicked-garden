# Sentiment Analysis Patterns

Common patterns and indicators for sentiment classification.

## Language Patterns

### Strong Positive
- **Delight**: "I love this", "This is amazing", "Perfect solution"
- **Gratitude**: "Thank you so much", "You saved me hours"
- **Advocacy**: "I recommend this to everyone", "Best tool I've used"
- **Surprise**: "Wow!", "I didn't expect this to work so well"

Example:
```
"This feature is absolutely brilliant! Saved me hours of work.
I'm recommending it to my whole team."

→ Sentiment: POSITIVE (STRONG)
```

### Moderate Positive
- **Satisfaction**: "This works well", "Good solution", "Helpful feature"
- **Improvement**: "Better than before", "Nice upgrade"
- **Acknowledgment**: "Appreciate the update", "Thanks for fixing"

Example:
```
"The new dashboard is much better. Makes finding reports easier."

→ Sentiment: POSITIVE (MODERATE)
```

### Mild Positive
- **Acceptance**: "It's fine", "Works as expected", "Does the job"
- **Neutral praise**: "Nice to have", "Useful in some cases"

Example:
```
"Export feature is decent. Gets the job done."

→ Sentiment: POSITIVE (MILD)
```

### Strong Negative
- **Frustration**: "This is terrible", "Completely broken", "Unusable"
- **Anger**: "I'm furious", "This is unacceptable"
- **Desperation**: "Please fix this ASAP", "About to cancel"
- **Churn signals**: "Looking at alternatives", "Switching to competitor"

Example:
```
"This is COMPLETELY BROKEN! I've lost hours of work.
If this isn't fixed soon, we're switching to [Competitor]."

→ Sentiment: NEGATIVE (STRONG)
→ Urgency: IMMEDIATE (churn risk)
```

### Moderate Negative
- **Complaints**: "This is frustrating", "Doesn't work as expected"
- **Confusion**: "I don't understand how to...", "This is confusing"
- **Slowness**: "Too slow", "Takes forever to load"

Example:
```
"The upload process is really slow and confusing.
Not sure what format is expected."

→ Sentiment: NEGATIVE (MODERATE)
```

### Mild Negative
- **Minor issues**: "Small bug", "Could be better"
- **Suggestions**: "Would be nice if...", "Consider improving"

Example:
```
"Minor issue with date formatting. Not a big deal but could be clearer."

→ Sentiment: NEGATIVE (MILD)
```

### Mixed Sentiment
- **Qualified praise**: "I like X but Y is broken"
- **Tradeoffs**: "Good for A, bad for B"
- **Context-dependent**: "Works on desktop, broken on mobile"

Example:
```
"Love the new features, but the mobile experience is terrible.
Desktop version is great though."

→ Sentiment: MIXED (positive desktop, negative mobile)
```

## Emotional Indicators

### Intensity Markers
- **Emphasis**: !!!, CAPS, bold, multiple adjectives
- **Repetition**: "very very slow", "again and again"
- **Profanity**: (indicates strong frustration)
- **Time expressions**: "always", "never", "constantly"

### Urgency Signals
- "ASAP", "urgent", "critical"
- "can't work", "blocking", "showstopper"
- "about to cancel", "looking at alternatives"
- Time constraints: "need by Friday", "deadline approaching"

### Satisfaction Signals
- Emoticons: :), :D, ❤️
- Exclamation marks: "Great!"
- Gratitude: "thank you", "appreciate"
- Recommendation: "telling everyone about this"

## Context Clues

### Business Impact
- Revenue mentions: "costing us money", "losing sales"
- Productivity: "wasting hours", "manual workaround"
- Scale: "affects entire team", "all our customers"

### User Sophistication
- Power user: Detailed technical feedback, feature requests
- New user: Onboarding issues, basic confusion
- Admin: Team management, permissions, configuration

### Segment Patterns
- Enterprise: Compliance, security, scale concerns
- SMB: Price sensitivity, ease of use, support quality
- Startup: Speed, integrations, modern features

## Edge Cases

### Sarcasm (Hard to Detect)
```
"Oh great, another bug. Just what I needed today."

→ Likely NEGATIVE despite "great"
→ Context: "another", "just what I needed" (sarcastic)
```

### Feature Requests (Often Neutral)
```
"Would love to see export to PDF feature."

→ Sentiment: NEUTRAL (request, not complaint)
→ But note "would love" shows positive attitude
```

### Bug Reports (Context-Dependent)
```
# Frustrated
"This bug is driving me crazy! Please fix!"
→ NEGATIVE (STRONG)

# Helpful
"Found a small bug in the export. Steps to reproduce: ..."
→ NEUTRAL or POSITIVE (MILD) - constructive, helpful tone
```

## Analysis Tips

1. **Read full context**: Don't just keyword match
2. **Consider tone**: "I guess it works" vs "It works great!"
3. **Watch for qualifiers**: "but", "however", "although"
4. **Note segment**: Enterprise expectations differ from startup
5. **Check recency**: Old complaint might be fixed
6. **Look for patterns**: Multiple people, same issue = signal

## False Positives to Avoid

- **Quoting others**: "Some people say it's slow" ≠ user thinks it's slow
- **Hypotheticals**: "If this breaks, it would be terrible" ≠ it's broken
- **Questions**: "Is this slow for everyone?" ≠ complaint
- **Feature requests**: "Add dark mode" ≠ current version is bad
