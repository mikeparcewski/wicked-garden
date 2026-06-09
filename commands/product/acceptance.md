---
description: Define acceptance criteria from requirements and design
argument-hint: "<requirements/design path> [--story US-ID] [--feature name] [--format gherkin|table|markdown] [--scenarios]"
phase_relevance: ["test", "review"]
archetype_relevance: ["*"]
---

# /wicked-garden:product:acceptance

Generate testable acceptance criteria from requirements/design. `acceptance`
**defines** criteria; to **run** tests against them, use `/wicked-testing:execution`.

## Run it inline (no dispatch)

1. Read input: requirements/design docs or a user-story reference. Honor `--story`, `--feature`, `--format`, `--scenarios`.
2. `Read("${CLAUDE_PLUGIN_ROOT}/skills/product/refs/acceptance.md")` — the Given/When/Then process, output format, and the `--scenarios` wicked-scenarios conversion (priority->difficulty, AC-type->category/tools, stub format).
3. Apply the rubric directly: identify scenarios (happy/error/edge/non-functional), write + prioritize AC, specify test data, add QE handoff notes. When `--scenarios`, also emit wicked-scenarios stubs.

AC feed into `/wicked-testing:plan`. Persist on the active clarify task via `TaskCreate`/`TaskUpdate` (`metadata={event_type:"task", chain_id:"{project}.clarify", source_agent:"requirements-analyst", phase:"clarify"}`) for QE traceability.
