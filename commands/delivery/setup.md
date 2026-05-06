---
description: |
  Use when setting up delivery metrics for the first time — cost model, sprint cadence, and report
  commentary sensitivity. NOT for generating reports (use delivery:report) or reviewing process health (use delivery:process-health).
argument-hint: "[--reset]"
allowed-tools: ["Read", "Write", "AskUserQuestion"]
phase_relevance: ["build", "review", "operate"]
archetype_relevance: ["*"]
---

# /wicked-garden:delivery:setup

Interactive setup for delivery metrics. Defaults, sensitivity presets, and the complexity-cost scaler live in `scripts/delivery/setup_defaults.py`.

## Question Mode

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/setup/detect_state.py" question-mode
```

`INTERACTIVE` → use the questioning tool below. `PLAIN_TEXT` → present numbered options, **STOP**, wait. Echo the chosen option back before acting.

## Instructions

### 1. Resolve Storage Path and Check for Existing Configuration

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/resolve_path.py wicked-delivery
```

Use the output as `DELIVERY_ROOT`. Read `{DELIVERY_ROOT}/cost_model.json` and `{DELIVERY_ROOT}/settings.json` if they exist. With `--reset`, ignore existing values. Otherwise if either file exists, show the current config and confirm reconfiguration.

### 2. Cost Model Setup

Cost estimation is opt-in. If declined, leave `cost_model.json` untouched. Use AskUserQuestion (or numbered text in PLAIN_TEXT mode) for each of:

- **Q1 — Enable cost estimation?** "Yes — configure costs" → continue. "No — skip cost model" / "Keep current" (only if file exists) → skip to section 3.
- **Q2 — Currency?** "USD", "EUR", "GBP", "Other" (let them type).
- **Q3 — Priority cost model?** Defaults via `scripts/delivery/setup_defaults.py cost-defaults`. Labels: "AI token costs" (`ai_tokens`), "Developer hours" (`dev_hours`), "Story points" (`story_points`), "Custom" (collect each P0–P3). Show the chosen P0–P3 values, confirm "Accept these values? (Y/n, or provide custom values)".
- **Q4 — Add complexity-based costs?** "Yes — add complexity costs" / "No — priority only". If yes, scale 0–7 from priority costs (linear: ~20% of P3 to ~150% of P0):

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/delivery/setup_defaults.py" scale-complexity '{"P0":<v>,"P1":<v>,"P2":<v>,"P3":<v>}'
```

Show and confirm. Write `{DELIVERY_ROOT}/cost_model.json` as `{"currency": "...", "priority_costs": {...}, "complexity_costs": {...}}` (omit `complexity_costs` if user declined).

### 3. Commentary Sensitivity

Use AskUserQuestion for **Q5 — Sensitivity?** Options: "Conservative", "Balanced (Recommended)", "Aggressive", "Custom" (collect each threshold individually). Preset values live in `setup_defaults.py::SENSITIVITY_PRESETS`.

### 4. Metrics Window

Use AskUserQuestion for **Q6 — Rolling window for throughput?** Options: "7 days" (`rolling_window_days=7`), "14 days (Recommended)" (`14`), "30 days" (`30`).

### 5. Sprint & Aging

Use AskUserQuestion for **Q7 — Aging threshold?** Options: "3 days" (`aging_threshold_days=3`), "7 days (Recommended)" (`7`), "14 days" (`14`).

### 6. Write Settings

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/delivery/setup_defaults.py" build-settings <conservative|balanced|aggressive> --rolling-window-days <N> --aging-threshold-days <N>
```

For "Custom" sensitivity, build the same envelope but substitute user-supplied threshold values. Write the result to `{DELIVERY_ROOT}/settings.json` (create the directory if needed).

### 7. Show Summary

```markdown
## Delivery Setup Complete

**Cost Model**: {priority costs, complexity costs, currency — or "disabled (no cost_model.json)"}
**Commentary**: {preset} · cooldown {minutes} min · completion {pct}%, cycle time p95 {pct}%, throughput {pct}%
**Metrics**: rolling window {days}d · aging threshold {days}d
**Files**: `cost_model.json` {state} · `settings.json` {state}

Reconfigure later: `/wicked-garden:delivery:setup --reset`
```
