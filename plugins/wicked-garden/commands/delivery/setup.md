---
description: Configure delivery metrics — cost model, commentary sensitivity, and sprint cadence
argument-hint: "[--reset]"
allowed-tools: ["Read", "Write", "AskUserQuestion"]
---

# /wicked-garden:delivery-setup

Interactive setup for delivery metrics configuration.

## Instructions

### 1. Check for Existing Configuration

Read existing files if they exist:
- `~/.something-wicked/wicked-delivery/cost_model.json`
- `~/.something-wicked/wicked-delivery/settings.json`

If `--reset` is passed, skip loading existing values and start fresh.

If either file exists and `--reset` is NOT passed, show current configuration and ask if the user wants to reconfigure.

### 2. Cost Model Setup

Ask the user about cost estimation. This is opt-in — if they decline, no cost_model.json is created (or existing one is left alone).

Use AskUserQuestion:

**Question 1**: "Do you want to enable cost estimation for delivery metrics?"
- "Yes — configure costs" → proceed to cost questions
- "No — skip cost model" → skip to section 3
- "Keep current" (only if cost_model.json exists) → skip to section 3

**If enabling cost estimation:**

**Question 2**: "What currency for cost tracking?"
- "USD" → currency = "USD"
- "EUR" → currency = "EUR"
- "GBP" → currency = "GBP"
- Other → let them type

**Question 3**: "How would you describe your priority cost model?"
- "AI token costs" → suggest P0=2.50, P1=1.50, P2=0.75, P3=0.40 (estimated AI compute per task)
- "Developer hours" → suggest P0=8.0, P1=4.0, P2=2.0, P3=1.0 (estimated dev hours per priority)
- "Story points" → suggest P0=13, P1=8, P2=5, P3=3 (fibonacci-ish)
- "Custom" → ask for each priority value

Show the suggested values and ask for confirmation:
```
Priority costs ({currency}):
  P0 (Critical): {value}
  P1 (High):     {value}
  P2 (Medium):   {value}
  P3 (Low):      {value}

Accept these values? (Y/n, or provide custom values)
```

**Question 4**: "Do you want complexity-based costs too?"
- "Yes — add complexity costs" → ask for scale or use defaults based on their cost model type
- "No — priority only" → skip complexity costs

If yes, generate complexity costs scaled proportionally to their priority model:
- Scale: complexity 0-7 maps linearly from ~20% of P3 cost to ~150% of P0 cost
- Show and confirm

Write `~/.something-wicked/wicked-delivery/cost_model.json`:
```json
{
  "currency": "{currency}",
  "priority_costs": {
    "P0": {value},
    "P1": {value},
    "P2": {value},
    "P3": {value}
  },
  "complexity_costs": {
    "0": {value},
    "1": {value},
    "2": {value},
    "3": {value},
    "4": {value},
    "5": {value},
    "6": {value},
    "7": {value}
  }
}
```

### 3. Commentary Sensitivity

Use AskUserQuestion:

**Question**: "How sensitive should delivery commentary be?"
- "Conservative" → Higher thresholds, fewer alerts (completion 20%, cycle time 40%, throughput 30%, cooldown 30min)
- "Balanced (Recommended)" → Default thresholds (completion 10%, cycle time 25%, throughput 20%, cooldown 15min)
- "Aggressive" → Lower thresholds, more frequent insights (completion 5%, cycle time 15%, throughput 10%, cooldown 10min)
- "Custom" → ask for each threshold individually

### 4. Metrics Window

Use AskUserQuestion:

**Question**: "What rolling window for throughput calculation?"
- "7 days" → rolling_window_days = 7 (weekly sprints or fast-moving teams)
- "14 days (Recommended)" → rolling_window_days = 14 (two-week sprints)
- "30 days" → rolling_window_days = 30 (monthly cadence)

### 5. Sprint & Aging

Use AskUserQuestion:

**Question**: "When should a backlog item be considered 'aging'?"
- "3 days" → aging_threshold_days = 3 (fast-paced teams)
- "7 days (Recommended)" → aging_threshold_days = 7 (standard)
- "14 days" → aging_threshold_days = 14 (longer cycles)

### 6. Write Settings

Create `~/.something-wicked/wicked-delivery/` directory if it doesn't exist.

Write `~/.something-wicked/wicked-delivery/settings.json`:
```json
{
  "rolling_window_days": {value},
  "aging_threshold_days": {value},
  "commentary": {
    "sensitivity": "{preset_name}",
    "cooldown_minutes": {value},
    "thresholds": {
      "completion_rate": {value},
      "cycle_time_p95": {value},
      "throughput": {value},
      "aging_low": {value},
      "aging_high": {value}
    }
  }
}
```

Sensitivity presets for threshold values:

| Preset | Completion | Cycle Time p95 | Throughput | Aging Low/High | Cooldown |
|--------|-----------|----------------|------------|----------------|----------|
| conservative | 0.20 | 0.40 | 0.30 | 15/30 | 30 |
| balanced | 0.10 | 0.25 | 0.20 | 10/20 | 15 |
| aggressive | 0.05 | 0.15 | 0.10 | 5/15 | 10 |

### 7. Show Summary

Display the full configuration:

```markdown
## Delivery Setup Complete

### Cost Model
{If configured: show priority costs, complexity costs, currency}
{If skipped: "Cost estimation disabled (no cost_model.json)"}

### Commentary
- **Sensitivity**: {preset}
- **Cooldown**: {minutes} minutes
- **Thresholds**: completion {pct}%, cycle time p95 {pct}%, throughput {pct}%

### Metrics
- **Rolling window**: {days} days
- **Aging threshold**: {days} days

### Files
- `~/.something-wicked/wicked-delivery/cost_model.json` {created/updated/unchanged}
- `~/.something-wicked/wicked-delivery/settings.json` {created/updated}

To reconfigure later: `/wicked-garden:delivery-setup --reset`
```
