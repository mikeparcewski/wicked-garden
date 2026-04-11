---
description: Mockup and wireframe generation — ASCII wireframes, HTML/CSS previews, or component specs for developer handoff
argument-hint: "<description-or-target> [--format ascii|html|spec] [--fidelity low|medium|high]"
---

# /wicked-garden:product:mockup

Generate wireframes, design mockups, and component specifications. Produces output
at the right fidelity — quick ASCII sketches for ideation, HTML/CSS previews for
stakeholder review, or annotated specs for developer handoff.

## Usage

```bash
# Generate a wireframe from a description
/wicked-garden:product:mockup "dashboard with sidebar navigation and card grid"

# Generate from existing requirements
/wicked-garden:product:mockup outcome.md

# Specify format explicitly
/wicked-garden:product:mockup "login form" --format html

# Low-fidelity ASCII for quick ideation
/wicked-garden:product:mockup "checkout flow" --fidelity low

# Component spec for handoff
/wicked-garden:product:mockup src/components/Card --format spec
```

## Instructions

### 1. Parse Arguments

Extract `<description-or-target>`, `--format` (ascii/html/spec), and `--fidelity` (low/medium/high).

Auto-select format if not specified:
- `--fidelity low` or no flag on a description → ascii
- `--fidelity high` or stakeholder context → html
- File path target → spec (showing current + improvements)

### 2. Gather Context

- If a description: use as the design brief
- If a file path: read it to understand the current component/page structure
- Check wicked-garden:mem for existing design tokens or component library in use

### 3. Delegate to Mockup Generator

```
Task(
  subagent_type="wicked-garden:product:mockup-generator",
  prompt="""Generate a {fidelity}-fidelity {format} mockup for the following.

## Design Brief / Target
{description or file contents}

## Format Requested
{ascii | html | spec}

## Fidelity
{low: quick sketch | medium: annotated | high: stakeholder-ready}

## Existing Design Context
{design tokens or component library if known from mem}

Deliverables:
- {ASCII wireframe | HTML/CSS preview | Component spec}
- Annotations for all states (default, hover, focus, disabled, error)
- Responsive behavior notes (mobile / tablet / desktop)
- Accessibility requirements
- Open questions for stakeholder input
- Next steps for implementation

Follow the mockup skill output format."""
)
```

### 4. Present Results

Display the mockup generator's output directly to the user.

## Format Guide

| Format | Output | Best For |
|--------|--------|----------|
| `ascii` | Text box-drawing wireframe | Quick ideation, flow sketches |
| `html` | Self-contained HTML/CSS file | Stakeholder review, demos |
| `spec` | Annotated Markdown component doc | Developer handoff |

## Integration

- **design:ux**: Pair mockups with UX flow diagrams
- **design:review**: Review built implementation against mockup
- **design:screenshot**: Compare screenshot of built UI to mockup
- **engineering**: Hand off spec to engineering for implementation
