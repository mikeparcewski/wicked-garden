# Screenshot UI Review Rubric (multimodal)

Apply this inline. Review UI design from screenshot images using Claude's vision —
no source code required. `Read` the image file(s) directly (the Read tool renders
PNG/JPG/JPEG/WEBP/GIF visually). Optional second image = design reference for
comparison.

## Read the image(s)

```
Read(file_path="{image-path}")
Read(file_path="{reference-path}")   # optional comparison target
```

## Evaluate

**Layout and spacing** — whitespace consistent and intentional? elements align to a
grid? content grouped logically?

**Color and contrast** — cohesive limited palette? sufficient text/background
contrast? semantic color (error/success/warning)?

**Typography** — clear heading hierarchy? readable sizes + line spacing? consistent
font family?

**Component consistency** — similar elements styled identically? interactive
elements visually distinct? states (selected/active) clearly shown?

## Comparison mode (if a reference is provided)

Spacing fidelity (built matches spec proportions?), color accuracy (same palette?),
typography match (weights/sizes/hierarchy), and missing/added elements.

## Output

```markdown
## Screenshot Review: {filename}

**Viewport**: {desktop|tablet|mobile|unknown}
**Overall**: {Polished | Minor Issues | Needs Work | Major Problems}

### Visual Design
**Spacing**: {…}   **Color**: {…}   **Typography**: {…}   **Components**: {…}

### Issues
{findings with location descriptions}

### Comparison {if reference provided}
{fidelity assessment}

### Recommendations
{prioritized fixes}
```

## Capturing first (optional)

If you need to capture from a URL, use an available browser-automation tool
(Playwright/Puppeteer/MCP browser) or `wicked-browse screenshot {url} --output …`
(incl. `--width 375` for mobile), then `Read` the saved file.
