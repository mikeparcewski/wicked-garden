---
name: refactoring-strategy
title: Legacy Code Refactoring Strategy
description: Explore approaches to refactoring risky legacy code
type: workflow
difficulty: advanced
estimated_minutes: 12
---

# Legacy Code Refactoring Strategy

This scenario tests wicked-jam's ability to help navigate complex refactoring decisions where multiple competing concerns (risk, value, time, maintainability) must be balanced.

## Setup

Create a realistic legacy code scenario:

```bash
# Create refactoring planning directory
mkdir -p ~/test-wicked-jam/refactoring
cd ~/test-wicked-jam/refactoring

# Create a problematic legacy code sample
cat > legacy_payment_service.py <<'EOF'
# Legacy payment processing service
# Written in 2018, touches 50+ files
# No tests, handles $2M/month in transactions
# Known issues:
# - Error handling swallows exceptions silently
# - Hardcoded credentials in multiple places
# - 2000-line God class
# - Threading bugs cause occasional double-charges
# - No logging for debugging payment failures

class PaymentProcessor:
    def __init__(self):
        self.api_key = "sk_live_hardcoded123"  # Security issue
        self.retry_count = 5

    def process_payment(self, amount, customer_id, card_token):
        # 500 lines of spaghetti code...
        try:
            # Actual payment processing logic
            pass
        except:
            pass  # Silent failure!

    # ... 1500 more lines ...
EOF

# Document the refactoring question
cat > refactoring-question.md <<'EOF'
# Legacy Payment Service Refactoring

## Context
- 2000-line payment processor written in 2018
- No tests, processes $2M/month
- Known bugs: threading issues, silent failures, hardcoded credentials
- Touches 50+ files across codebase
- Team of 3 developers, 2 months available

## Question
How should we approach refactoring this?
Options:
1. Big bang rewrite (risky but clean)
2. Strangler fig pattern (gradual replacement)
3. Incremental refactoring with tests (slow but safe)
4. Leave it alone, wrap it with new code (technical debt)

## Constraints
- Cannot stop processing payments (24/7 uptime required)
- No dedicated QA, only production testing available
- Team has 8 weeks before next major feature deadline
- Security audit scheduled in 3 months (hardcoded creds must be fixed)
EOF
```

## Steps

1. **Run Brainstorm with Custom Personas**
   ```bash
   /wicked-jam:brainstorm "refactoring strategy for legacy payment processor" --personas "Security,Tester,Maintainer,Architect,Risk-Manager" --rounds 3
   ```

   Expected: Session with specified personas runs 3 discussion rounds

2. **Verify Custom Persona Handling**

   Check that:
   - Session includes the 5 requested personas (or explains why fewer)
   - Personas match the names provided
   - If names don't match archetype pool exactly, system adapts intelligently

3. **Verify Round Progression**

   Check that 3 rounds occur:
   - **Round 1**: Initial stances (each persona's preferred approach)
   - **Round 2**: Personas challenge or build on each other's ideas
   - **Round 3**: Convergence toward a hybrid approach or acknowledge tensions

4. **Verify Complex Tradeoff Handling**

   Check synthesis addresses:
   - Risk vs. reward tradeoffs
   - Time constraints (8 weeks)
   - Safety requirements (24/7 uptime, $2M/month)
   - Multiple stakeholder concerns
   - No simple "right answer"

5. **Verify Open Questions Capture Uncertainty**

   Check that synthesis includes:
   - Honest acknowledgment of unknowns
   - Questions that need investigation before deciding
   - Tensions that won't fully resolve

6. **Test Quick Gut-Check**
   ```bash
   /wicked-jam:jam "should we rewrite the payment processor or refactor incrementally?"
   ```

   Expected: Quick take with 4 personas, brief recommendation

## Expected Outcome

- Session runs all 3 requested rounds
- Personas engage with the specific context (payment processing, uptime requirements)
- Round 3 shows evolution from initial stances to nuanced hybrid approaches
- Synthesis acknowledges complexity (not oversimplified)
- Action items include "investigate X first" not just "do Y"
- Confidence levels reflect genuine uncertainty on speculative points

## Success Criteria

- [ ] Custom persona list is respected (--personas flag works)
- [ ] Custom round count is respected (--rounds 3 flag works)
- [ ] Round 1 shows initial positions from each persona
- [ ] Round 2 shows personas referencing/responding to each other
- [ ] Round 3 shows convergence or acknowledgment of unresolved tensions
- [ ] Synthesis includes at least one LOW confidence insight (acknowledging uncertainty)
- [ ] Open questions include investigative actions, not just decisions
- [ ] Security persona addresses hardcoded credentials issue
- [ ] Risk persona addresses $2M/month uptime concern
- [ ] No "silver bullet" recommendation (acknowledges tradeoffs)

## Value Demonstrated

**Real-world value**: Refactoring legacy code is notoriously difficult because it requires balancing competing concerns: safety, speed, technical debt, business continuity, and team capacity. wicked-jam simulates a technical decision-making meeting with diverse experts who surface risks and considerations that solo developers might miss.

The multi-round discussion format mirrors how real teams evolve from initial positions to nuanced hybrid strategies. The confidence-rated synthesis helps separate clear consensus (e.g., "add tests first") from speculative ideas (e.g., "strangler pattern might work"). This replaces the need for lengthy architecture review meetings while still capturing diverse expert perspectives, helping teams make safer refactoring decisions.

The ability to specify custom personas ensures the right expertise is at the table for domain-specific problems.
