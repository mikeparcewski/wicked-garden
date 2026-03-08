# Visual Analysis: General Description

This reference provides a high-level, human-readable summary of what is happening in the image. This is the entry point for most visual tasks.

## Core Objectives
- Provide a concise summary of the subject matter.
- Identify the primary actors or objects in the scene.
- Summarize the setting and context.

## Extraction Workflow
1. **Subject Identification:** "What is this an image of?"
2. **Contextual Summary:** "Where and when is this taking place?"
3. **Action/State:** "What is happening or what is the state of the objects?"

## Tooling

Use Claude's native Read tool to analyze the image directly — no external CLI needed:
```
Read(file_path="./asset.png")
```
Then apply the extraction workflow above to describe the image.

## Review Criteria
- Is the summary accurate but concise?
- Does it avoid overly technical jargon unless requested?
- Is it sufficient for a non-technical stakeholder to understand the content?
