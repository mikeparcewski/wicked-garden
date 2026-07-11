---
name: wicked-garden-product
user-invocable: true
description: |
  Product domain skill: 13 user-invokable actions — a11y | acceptance | align |
  analyze | elicit | listen | mockup | screenshot | strategy | synthesize | ux |
  ux-review | visual-direction — backed by the rubrics in refs/ and this
  domain's knowledge-module sub-skills.

  Use when: "accessibility audit", "WCAG compliance", "define acceptance
  criteria", "stakeholder alignment", "build consensus", "analyze customer
  feedback", "elicit requirements", "write user stories", "aggregate customer
  feedback", "ASCII wireframe or HTML mockup", "review this screenshot",
  "strategic analysis", "ROI / value proposition / market / competitive",
  "synthesize feedback into recommendations", "design a user flow", "UX review",
  "design audit", "visual direction", or any former
  /wicked-garden:product:{action} invocation.
phase_relevance: ["clarify", "design", "test", "review"]
archetype_relevance: ["*"]
---

# Product Domain

One entry point for the product domain. Pick the action, parse its args, load its
ref, apply it inline. Only `strategy --focus all` and `ux-review --focus all` dispatch.

## Action router

| Action | Use for | Args | Ref |
|--------|---------|------|-----|
| `a11y` | Accessibility audit: WCAG 2.1 AA, keyboard, screen reader, contrast | `<target> [--level A\|AA\|AAA] [--quick]` | `refs/a11y.md` |
| `acceptance` | Define testable acceptance criteria from requirements/design | `<path> [--story US-ID] [--feature name] [--format gherkin\|table\|markdown] [--scenarios]` | `refs/acceptance.md` |
| `align` | Stakeholder alignment: surface concerns, map trade-offs, build consensus | `[target-doc] [--stakeholders] [--focus concerns\|tradeoffs\|conflicts] [--conflict]` | `refs/align.md` |
| `analyze` | Customer-voice pipeline 2/3: themes, sentiment, trends | `[--theme X] [--sentiment pos\|neg] [--trend period] [--segment]` | `refs/analyze.md` |
| `elicit` | Turn a vague ask into user stories + AC | `[target-doc] [--interactive] [--personas] [--scope]` | `refs/elicit.md` |
| `listen` | Customer-voice pipeline 1/3: aggregate feedback from sources | `[--capability type] [--days N] [--since] [--tags x,y] [--limit N]` | `refs/listen.md` |
| `mockup` | ASCII wireframe / HTML mockup / annotated spec | `<description-or-target> [--format ascii\|html\|spec] [--fidelity low\|medium\|high]` | `refs/mockup.md` |
| `screenshot` | Multimodal UI review from image files | `<image-path> [<reference-path>]` | `refs/screenshot.md` |
| `strategy` | Strategic analysis: ROI, value, market, competitive | `<target> [--focus roi\|value\|market\|competitive\|all] [--quick]` | `refs/strategy.md` |
| `synthesize` | Customer-voice pipeline 3/3: prioritized recommendations | `[--priority high\|medium\|low\|critical] [--feature X] [--format brief\|detailed]` | `refs/synthesize.md` |
| `ux` | Create or analyze user flows / IA / interaction patterns | `<target-or-description> [--mode create\|analyze]` | `refs/ux.md` |
| `ux-review` | Broad design audit: flows + UI + a11y + research, score 1-5 per lens | `<target> [--focus flows\|ui\|a11y\|research\|all] [--quick]` | `refs/ux-review.md` |
| `visual-direction` | Reason from content structure to visual form (five questions) | `<section-or-description> [--skip-to N]` | `visual-direction/SKILL.md` |

## Action: a11y

Accessibility audit for UI code/components: WCAG 2.1 AA, keyboard nav, screen reader support, color contrast, semantic structure. Inline, no dispatch.
1. Parse `<target>`, `--level` (default AA), `--quick`.
2. `Read("${CLAUDE_PLUGIN_ROOT}/skills/product/refs/a11y.md")` — the POUR rubric, checklist, common violations, and output format. Read the target file(s), apply the rubric directly, emit the audit.
3. Deeper WCAG/ARIA/keyboard/screen-reader detail: the `accessibility` skill (`skills/product/accessibility/`). Track remediation via `TaskCreate`/`TaskUpdate` (`metadata.event_type="task"`); pair with the `ux-review` action for visual consistency.

## Action: acceptance

Generate testable acceptance criteria from requirements/design. `acceptance`
**defines** criteria; to **run** tests against them, use `/wicked-testing:execution`.
1. Read input: requirements/design docs or a user-story reference. Honor `--story`, `--feature`, `--format`, `--scenarios`.
2. `Read("${CLAUDE_PLUGIN_ROOT}/skills/product/refs/acceptance.md")` — the Given/When/Then process, output format, and the `--scenarios` wicked-scenarios conversion (priority->difficulty, AC-type->category/tools, stub format). For full requirements-graph AC nodes, see the `acceptance-criteria` skill.
3. Apply the rubric directly: identify scenarios (happy/error/edge/non-functional), write + prioritize AC, specify test data, add QE handoff notes. When `--scenarios`, also emit wicked-scenarios stubs.

AC feed into `/wicked-testing:plan`. Persist on the active clarify task via `TaskCreate`/`TaskUpdate` (`metadata={event_type:"task", chain_id:"{project}.clarify", source_agent:"requirements-analyst", phase:"clarify"}`) for QE traceability.

## Action: align

Facilitate stakeholder alignment, surface concerns, and build consensus. NOT requirements elicitation (`elicit`) or UX design (`ux`).
1. Read context: the target document if provided, plus `--stakeholders`, `--focus` (concerns/tradeoffs/conflicts), `--conflict`.
2. `Read("${CLAUDE_PLUGIN_ROOT}/skills/product/refs/align.md")` — the process, facilitation checklist, questions to ask, and output format.
3. Apply the rubric directly: identify stakeholders, surface concerns, classify ALIGNED / CONFLICTED / UNCLEAR, propose compromises, and emit decisions-required + next steps (owner + deadline).

Persist status via `TaskCreate`/`TaskUpdate` (`metadata.event_type="task"`); store stakeholder patterns via `wicked-brain:memory`. Heavyweight facilitation (value design + alignment in one worker): the `wicked-garden-product-value-strategist` fork skill — its Part B is the facilitation version of this rubric.

## Action: analyze

Analyze aggregated customer feedback for themes, sentiment patterns, and trends. Pipeline step 2 of 3: listen -> **analyze** -> synthesize. Inline, no dispatch.
1. Load feedback data:
   ```bash
   PRODUCT_ROOT=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/resolve_path.py wicked-garden:product)
   ls "${PRODUCT_ROOT}/voice/feedback/"
   ```
   If empty, tell the user to run the `listen` action first and stop.
2. `Read("${CLAUDE_PLUGIN_ROOT}/skills/product/refs/analyze.md")` — sentiment classes, theme extraction, trend detection, segment analysis, techniques, rules, and output format. Tier-3 depth: `skills/product/analyze/SKILL.md` + its refs (`algorithms.md`, `sentiment-patterns.md`).
3. Apply the rubric directly, honoring `--theme`/`--sentiment`/`--trend`/`--segment`. Emit the analysis report, then point to the `synthesize` action.

## Action: elicit

Elicit requirements and write user stories with acceptance criteria.
1. Read context: the target document(s) (`outcome.md`, brief, `docs/requirements/`), or accept `--interactive`. Honor `--personas` and `--scope`.
2. `Read("${CLAUDE_PLUGIN_ROOT}/skills/product/refs/elicit.md")` — the process, INVEST quality criteria, completeness check, traceability, and output format.
3. Apply the rubric directly and emit user stories (priority + complexity + dependencies + AC) and open questions. Persist on the active clarify task via `TaskUpdate`.

For complexity >= 3 or compliance signals, produce a requirements **graph** instead — load the `requirements-analysis` / `requirements-graph` skills. Dedicated worker: the `wicked-garden-product-requirements-analyst` fork skill.

## Action: listen

Aggregate customer feedback from discovered sources (support, surveys, social,
direct). Pipeline step 1 of 3: **listen** -> analyze -> synthesize.
1. Discover sources:
   ```bash
   PRODUCT_ROOT=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/resolve_path.py wicked-garden:product)
   ls "${PRODUCT_ROOT}/voice/feedback/" 2>/dev/null
   find . -name "*feedback*" -o -name "*survey*" -o -name "*tickets*" 2>/dev/null | head -10
   gh issue list --label "customer-reported" 2>/dev/null | head -5
   ```
2. `Read("${CLAUDE_PLUGIN_ROOT}/skills/product/refs/listen.md")` — normalization, tagging, prioritization, storage, and output format. Capability-integration detail: `skills/product/listen/SKILL.md` + `refs/channels.md`.
3. Apply the rubric directly: extract + normalize + tag + prioritize feedback, honoring `--days`/`--since`/`--tags`/`--capability`/`--limit`. Emit the listening report, then hand off to the `analyze` action.

## Action: mockup

Generate wireframes, mockups, and component specs at the right fidelity — ASCII
for ideation, HTML/CSS for stakeholder review, annotated spec for developer handoff.
1. Parse `<description-or-target>`, `--format` (ascii/html/spec), `--fidelity` (low/medium/high). Auto-select format: bare description / low -> ascii; high / stakeholder context -> html; file path -> spec.
2. Gather context: if a description, use as the brief; if a file path, read it to understand the current structure; recall design tokens via `wicked-brain:memory`.
3. `Read("${CLAUDE_PLUGIN_ROOT}/skills/product/refs/mockup.md")` — fidelity selection, ASCII/HTML/spec formats, generation process, and output format. Tier-3 depth: `skills/product/mockup/`.
4. Apply the rubric directly and emit the mockup with state/responsive/a11y annotations and open questions. Pair with the `ux` action (flows) and the `screenshot` action (compare to built UI).

## Action: screenshot

Review UI design from screenshot images using Claude's multimodal vision — layout,
spacing, color, typography, consistency — no source code. PNG/JPG/JPEG/WEBP/GIF.
1. Parse `<image-path>` (required) and optional `<reference-path>`.
2. `Read(file_path="{image-path}")` (and the reference if provided) — the Read tool renders images visually.
3. `Read("${CLAUDE_PLUGIN_ROOT}/skills/product/refs/screenshot.md")` — the evaluation rubric (layout/color/typography/components), comparison mode, and output format. Tier-3 depth: `skills/product/screenshot/SKILL.md`.
4. Apply the rubric directly to the rendered image(s) and emit the review. Flag contrast issues for the `a11y` action; compare against a `mockup` action spec when relevant.

## Action: strategy

Strategic business analysis: ROI, value proposition, market sizing/timing,
competitive landscape. `--quick` = go/no-go signal only. `strategy` evaluates an
idea; `elicit` converts a chosen direction into requirements. Tier-3 depth: `skills/product/strategy/` + its refs.
1. **Read target + parse focus.** Read `<target>` (proposal/feature doc). Determine focus(es) from `--focus` (default `all`).
2. **Single focus -> inline.** For one lens, `Read("${CLAUDE_PLUGIN_ROOT}/skills/product/refs/strategy.md")` and apply that lens's rubric directly — market lens for `roi|market|competitive`, value lens for `value`. No dispatch.
3. **`--focus all` -> dispatch value lens; run market lens inline.**

   ```
   Skill(skill="wicked-garden-product-value-strategist",
         args="""Target: {target_content}  Quick: {--quick}
   Design value proposition: customer JTBD, pain relievers, gain creators, differentiation, value statement.""")
   ```

   This dispatches the `wicked-garden-product-value-strategist` fork skill. The market lens (ROI / TAM-SAM-SOM / SWOT / Five Forces) runs **inline** — `Read("${CLAUDE_PLUGIN_ROOT}/skills/product/refs/strategy.md")` and apply its market rubric directly: investment/returns/payback for `roi`, TAM/SAM/SOM + timing for `market`, SWOT/positioning for `competitive`. No separate dispatch.
4. **Synthesis (always inline).** Render the verdict inline — Proceed / Caution / Defer / Do-Not-Proceed + confidence + assumptions + metrics (`refs/strategy.md` output format). Never delegate the synthesis.

## Action: synthesize

Translate customer-feedback analysis into prioritized, evidence-backed action
items. Pipeline step 3 of 3: listen -> analyze -> **synthesize**.
1. Locate analysis input:
   ```bash
   PRODUCT_ROOT=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/resolve_path.py wicked-garden:product)
   ls "${PRODUCT_ROOT}/voice/analysis/"
   ```
   If empty, tell the user to run the `analyze` action first and stop.
2. `Read("${CLAUDE_PLUGIN_ROOT}/skills/product/refs/synthesize.md")` — the impact x frequency x trend x effort x risk-of-inaction prioritization model, per-recommendation fields, and output format. Tier-3 depth: `skills/product/synthesize/SKILL.md` + refs (`prioritization.md`, `journey-mapping.md`).
3. Apply the rubric directly, honoring `--priority`/`--feature`/`--format`. Emit prioritized recommendations, quick wins, strategic initiatives, and metrics to track.

## Action: ux

Design and analyze user flows, interaction patterns, and information
architecture. For a broad design audit (UI + a11y + research), use `ux-review`.
1. Parse `<target>` (path or description) and `--mode`. Auto-detect: description string -> `create`; file/dir path -> `analyze`.
2. Gather content: if a path, read the target files (components, pages, routing); if a description, use as the brief.
3. `Read("${CLAUDE_PLUGIN_ROOT}/skills/product/refs/ux.md")` — create/analyze steps, flow checklist, Nielsen heuristics, interaction patterns, diagram + output formats.
4. Apply the rubric directly and emit the flow/IA + findings. Pair with the `mockup` action for wireframes.

## Action: ux-review

Broad design audit across four lenses — flows, visual consistency (UI), WCAG
accessibility, user-research quality. Each lens returns score 1-5 + findings.
`--quick` = critical-only. `ux-review` evaluates existing UI; `ux` generates flows.
1. **Determine focus.** Parse `--focus`. Auto-detect: `.tsx/.jsx/.vue` -> flows+ui+a11y; `.css/.scss` -> ui; requirements `.md` -> research; directory -> all.
2. **Single focus -> inline.** For one lens, `Read("${CLAUDE_PLUGIN_ROOT}/skills/product/refs/ux-review.md")`, apply that lens's rubric directly to the target, and emit the score + findings. No dispatch.
3. **`--focus all` -> dispatch the lenses in parallel.** Genuine multi-lens concurrency on a large surface earns the hop. Common preamble: `Target: {target_content}  Quick: {--quick}`. Each fork worker returns score 1-5 + findings.

   ```
   Skill(skill="wicked-garden-product-ux-designer",
         args="""<preamble> Two lenses. (1) Flows: clarity, error/empty/loading states, interaction patterns, IA. (2) Research: personas, journeys, JTBD, validation status. Issues with severity + file:line + impact + fix; plus a research-gap list.""")
   Skill(skill="wicked-garden-product-ui-reviewer",
         args="""<preamble> Eval design-system adherence, color/typography/spacing, component patterns, responsive + visual states. Issues with severity + fix.""")
   Skill(skill="wicked-garden-product-a11y-expert",
         args="""<preamble> Audit WCAG 2.1 AA (POUR): semantic HTML, ARIA, keyboard, screen reader, contrast, focus. Report WCAG level + issues with criterion + fix.""")
   ```

   These dispatch the `wicked-garden-product-ux-designer`, `wicked-garden-product-ui-reviewer`, and `wicked-garden-product-a11y-expert` fork skills. The research lens (personas / journeys / JTBD) is folded into the ux-designer dispatch — flow and research evaluation share the same artifact and reviewer skill. Merge the three returns inline into the combined report (`refs/ux-review.md` output format).

## Action: visual-direction

Stop before proposing any visual form. Reason from what the content *is* to what
it should look like — not from what the nearest project used.
1. Parse `<section-name-or-description>`. Read any file path given. `--skip-to <N>` starts at that question.
2. `Read("${CLAUDE_PLUGIN_ROOT}/skills/product/visual-direction/SKILL.md")` — five questions, anti-patterns, visual brief format.
3. **Answer all five questions out loud before proposing any treatment** (content type, audience mental model, desired action, physical-artifact metaphor, stupid-question test), then emit the visual brief. Do not skip to wireframe or implementation first.

## Knowledge modules and fork workers

Reference knowledge lives beside this skill, loaded on demand: `acceptance-criteria/`,
`accessibility/`, `analyze/`, `imagery/`, `listen/`, `mockup/`, `requirements-analysis/`,
`requirements-graph/`, `requirements-migrate/`, `requirements-navigate/`, `screenshot/`,
`strategy/`, `synthesize/`, `ux-review/`, `visual-direction/`, `visual-review/`, plus
the per-action rubrics in `refs/`. Standalone fork workers (top-level
`skills/product-<role>/`, dispatchable via Task): `a11y-expert`,
`requirements-analyst`, `ui-reviewer`, `ux-designer`, `value-strategist` — all
prefixed `wicked-garden-product-`.
