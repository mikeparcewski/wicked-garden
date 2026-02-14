---
name: archetype-scoring
title: Archetype-Aware Complexity Scoring
description: Verify scoring adjusts based on project type, not just keywords
type: workflow
difficulty: intermediate
estimated_minutes: 10
---

# Archetype-Aware Complexity Scoring

This scenario validates that smart_decisioning.py adjusts complexity scores based on the TYPE of project being changed. Different project types have different quality dimensions -- a content site needs messaging consistency review, infrastructure changes need higher impact scoring, and custom archetypes can be defined dynamically.

## Setup

No special setup needed. Uses smart_decisioning.py directly.

```bash
# Verify smart_decisioning.py is available
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/smart_decisioning.py" --json "test" > /dev/null 2>&1
```

## Steps

### 1. Baseline: Simple description without archetype context

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/smart_decisioning.py" --json "Update the scoring logic"
```

Expected: Low complexity (0-1) because no file references, no integration keywords.

### 2. Infrastructure-framework archetype via keywords

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/smart_decisioning.py" --json "Modify the plugin scoring engine, execution workflow, and dispatch routing for all crew commands"
```

Expected:
1. Detects "infrastructure-framework" archetype from keywords (scoring, engine, execution, workflow, dispatch, routing, plugin, command)
2. Impact boosted by +2 (core execution path changes)
3. Architecture signal injected
4. Complexity >= 3 (min_complexity floor)

### 3. External archetype hints override keyword detection

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/smart_decisioning.py" --json \
  --archetype-hints '{"infrastructure-framework": {"confidence": 0.9, "impact_bonus": 2, "inject_signals": {"architecture": 0.3}, "min_complexity": 3, "description": "Core execution paths"}}' \
  "Fix a small bug"
```

Expected:
1. Even "Fix a small bug" scores >= 3 when infrastructure-framework hint provided
2. Architecture signal injected despite no architecture keywords in text
3. Impact bonus applied from hint

### 4. Custom dynamic archetype

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/smart_decisioning.py" --json \
  --archetype-hints '{"marketing-landing-page": {"confidence": 0.85, "impact_bonus": 1, "inject_signals": {"product": 0.4, "ux": 0.4}, "min_complexity": 2, "description": "Brand consistency and conversion matter"}}' \
  "Update hero section copy and CTA button colors"
```

Expected:
1. Custom "marketing-landing-page" archetype registered dynamically
2. Product and UX signals injected
3. wicked-product specialist recommended (REQUIRED tier)
4. Complexity >= 2 (min_complexity floor)

### 5. Holistic multi-archetype merging

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/smart_decisioning.py" --json \
  --archetype-hints '{"infrastructure-framework": {"confidence": 0.8, "impact_bonus": 2, "min_complexity": 3, "description": "Core paths"}, "compliance-regulated": {"confidence": 0.7, "impact_bonus": 2, "inject_signals": {"compliance": 0.5, "security": 0.3}, "min_complexity": 3, "description": "Audit requirements"}}' \
  "Update authentication middleware"
```

Expected:
1. Both archetypes detected
2. MAX impact_bonus applied (2, from either)
3. Compliance AND security signals injected from compliance-regulated
4. Architecture signal injected from infrastructure-framework
5. Complexity >= 3

### 6. Invalid hints handled gracefully

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/smart_decisioning.py" --json \
  --archetype-hints '{"bad": "not-a-dict"}' \
  "Normal project description"
```

Expected:
1. Warning logged about invalid hint
2. Analysis completes without error
3. Falls back to keyword-only detection

### 7. Backward compatibility: no hints

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/smart_decisioning.py" --json "Fix a typo in the README"
```

Expected:
1. No archetypes detected (or minimal keyword match)
2. Complexity 0 (same as before archetype feature)
3. No archetype adjustments applied

## Expected Outcome

### Scoring reflects project type
- Infrastructure changes score 3+ even without file references
- Content/UI changes get appropriate specialist recommendations
- Custom archetypes work for project-specific quality dimensions

### Holistic assessment
- Multiple archetypes merge using MAX adjustments
- Signals from all archetypes are unioned
- Min complexity is the highest floor from any detected archetype

### Backward compatible
- No hints = original keyword-only behavior preserved
- Invalid hints are gracefully skipped

## Success Criteria

### Archetype Detection
- [ ] Infrastructure-framework keywords detected from "scoring", "engine", "execution", etc.
- [ ] External hints override keyword detection confidence
- [ ] Custom archetypes accepted and applied

### Scoring Adjustments
- [ ] Impact bonus applied correctly (0-3 cap)
- [ ] Min complexity floor enforced
- [ ] Signal injection adds signals not already present

### Holistic Merging
- [ ] MAX impact_bonus from all archetypes, not just primary
- [ ] UNION of injected signals from all archetypes
- [ ] MAX min_complexity floor from all archetypes

### Edge Cases
- [ ] Invalid hints logged and skipped
- [ ] No hints = original behavior
- [ ] Empty description still works

## Value Demonstrated

Without archetype-aware scoring, a project modifying core infrastructure gets the same complexity score as a typo fix if neither mentions specific files. This leads to under-resourcing critical changes. With archetypes, scoring understands that "quality" means different things for different project types -- messaging consistency for content, design coherence for UI, reliability for infrastructure, audit trails for compliance -- and adjusts accordingly.
