# README Validation Rules

Machine-checkable rules for validating plugin READMEs against the style guide.

## Required Checks (Quick Mode)

These checks run in `/wg-check` quick mode:

### R1: README Exists
- File `README.md` must exist in plugin root
- Severity: ERROR

### R2: Has Tagline
- First non-empty, non-heading line after the h1 must be present
- Must not start with `#`, `|`, `` ` ``, or `>`
- Severity: ERROR

### R3: Quick Start Section
- Must contain `## Quick Start` heading
- Must have at least one code block under it
- Severity: ERROR

### R4: Commands Section
- Must contain `## Commands` heading
- Severity: ERROR

### R5: Integration Table
- Must contain `## Integration` heading
- Table must have 3 columns: Plugin, What It Unlocks, Without It
- Check: `grep -c "Without It" README.md` should be ≥1
- Severity: ERROR

### R6: Code Examples
- Must have at least one fenced code block (```)
- Severity: WARNING

### R7: No Template Placeholders
- Must not contain `{path}`, `{verb}`, `{source}` as unresolved placeholders
- Check: `grep -E '\{(path|verb|source)\}' README.md`
- Exception: placeholders inside markdown comments (`<!-- -->`) are allowed
- Severity: WARNING

## Conditional Checks

These are informational — flagged but not blocking:

### C1: When to Use What
- RECOMMEND if plugin has 3+ commands in Commands table
- Check: count rows in Commands table, suggest if ≥3

### C2: Workflows Before Commands
- If both `## Workflows` (or similar heading) and `## Commands` exist, Workflows should appear first
- Check: line number of Workflows heading < line number of Commands heading

### C3: Data API Section
- RECOMMEND if plugin exposes data via the Control Plane (CP)
- Check: domain is listed in CP manifest (`python3 scripts/cp.py manifest`)

### C4: Output Examples
- RECOMMEND at least one output example (code block showing expected output, not just input commands)
- Heuristic: code blocks that don't start with `/`, `#`, `$`, or common command prefixes

## Tone Checks (Manual Review)

These require human or AI judgment — used in `--full` mode:

### T1: Tagline Specificity
- Tagline makes a specific claim, not a category description
- BAD pattern: "A {noun} plugin for {action}"
- GOOD pattern: "{Specific outcome or capability} — {concrete example}"

### T2: No Hedging
- Search for: "might", "could potentially", "may help", "tries to"
- These weaken the voice

### T3: Active Voice in Integration Table
- "What It Unlocks" column uses active verbs implying directionality
- BAD: "Memory integration"
- GOOD: "Decisions persist across sessions via automatic storage"

## Validation Script

```bash
#!/bin/bash
# Quick README style guide validation
# Usage: bash validate_readme.sh plugins/wicked-foo

path="$1"
readme="$path/README.md"
errors=0
warnings=0

# R1: Exists
if [[ ! -f "$readme" ]]; then
  echo "ERROR [R1]: Missing README.md"
  exit 1
fi

# R2: Tagline
tagline=$(awk '/^# /{found=1; next} found && /^[^#|`>]/ && NF{print; exit}' "$readme")
if [[ -z "$tagline" ]]; then
  echo "ERROR [R2]: No tagline after h1"
  ((errors++))
fi

# R3: Quick Start
if ! grep -q "## Quick Start" "$readme"; then
  echo "ERROR [R3]: Missing ## Quick Start"
  ((errors++))
fi

# R4: Commands
if ! grep -q "## Commands" "$readme"; then
  echo "ERROR [R4]: Missing ## Commands"
  ((errors++))
fi

# R5: Integration with 3 columns
if ! grep -q "## Integration" "$readme"; then
  echo "ERROR [R5]: Missing ## Integration"
  ((errors++))
elif ! grep -q "Without It" "$readme"; then
  echo "ERROR [R5]: Integration table missing 'Without It' column"
  ((errors++))
fi

# R6: Code examples
if ! grep -q '```' "$readme"; then
  echo "WARN [R6]: No code examples found"
  ((warnings++))
fi

# R7: Template placeholders
if grep -E '\{(path|verb|source)\}' "$readme" | grep -v '<!--' > /dev/null 2>&1; then
  echo "WARN [R7]: Unresolved template placeholders found"
  ((warnings++))
fi

# Summary
if [[ $errors -eq 0 ]]; then
  echo "PASS: $(basename $path) ($warnings warnings)"
else
  echo "FAIL: $(basename $path) ($errors errors, $warnings warnings)"
fi
```
