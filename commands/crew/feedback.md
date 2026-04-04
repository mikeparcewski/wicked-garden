---
description: Capture user or stakeholder feedback linked to the current crew project
argument-hint: "<feedback-text> [--source user|stakeholder|team|monitoring] [--sentiment positive|neutral|negative]"
---

# /wicked-garden:crew:feedback

Capture feedback and link it to relevant requirements via traceability.

## Arguments

- `feedback-text` (required): The feedback content
- `--source` (optional): Who provided the feedback. Default: user
  - `user`: End-user feedback
  - `stakeholder`: Business stakeholder feedback
  - `team`: Internal team feedback
  - `monitoring`: Automated monitoring/alerting signal
- `--sentiment` (optional): Feedback sentiment. Default: neutral
  - `positive`: Feature working well, good experience
  - `neutral`: Observation, suggestion, neither positive nor negative
  - `negative`: Problem report, poor experience, complaint

## Instructions

### 1. Find Active Project

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/crew.py find-active --json
```

If no active project found, inform user and suggest `/wicked-garden:crew:start`.

### 2. Parse Arguments

Extract from the command arguments:
- `feedback-text`: The feedback content (required)
- `source`: user, stakeholder, team, or monitoring (default: user)
- `sentiment`: positive, neutral, or negative (default: neutral)

If no feedback text provided, ask the user for it.

### 3. Store Feedback Record

Generate a feedback ID and store via DomainStore:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, sys, uuid
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path('${CLAUDE_PLUGIN_ROOT}/scripts')))
from _domain_store import DomainStore
ds = DomainStore('wicked-crew')
feedback = {
    'id': f'fb-{uuid.uuid4().hex[:8]}',
    'project_id': '{project_name}',
    'text': '''${FEEDBACK_TEXT}''',
    'source': '{source}',
    'sentiment': '{sentiment}',
    'created_at': datetime.now(timezone.utc).isoformat(),
    'linked_requirements': [],
    'traceability_links': []
}
result = ds.create('feedback', feedback)
print(json.dumps(result or feedback, indent=2))
"
```

### 4. Create Traceability Links

If the feedback relates to specific requirements or features, create FEEDBACK_ON links:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/traceability.py create \
  --source-id "{feedback_id}" \
  --source-type "feedback" \
  --target-id "{requirement_id}" \
  --target-type "requirement" \
  --link-type "FEEDBACK_ON" \
  --project "{project_name}" \
  --created-by "operate"
```

To identify relevant requirements, check the project's acceptance criteria and objectives for keyword overlap with the feedback text.

### 5. Display Feedback Summary

```markdown
## Feedback Captured: {feedback_id}

**Project**: {project-name}
**Source**: {source}
**Sentiment**: {sentiment_emoji} {sentiment}

### Feedback
> {feedback_text}

### Traceability
{links to related requirements, if any}

---

To view all feedback: check operate phase status
To generate insights: `/wicked-garden:crew:retro`
```

Sentiment indicators:
- positive: thumbs up
- neutral: dash
- negative: warning sign

## Examples

```bash
# Capture user feedback
/wicked-garden:crew:feedback "Search is much faster now, great improvement" --source user --sentiment positive

# Capture stakeholder feedback
/wicked-garden:crew:feedback "The new dashboard is missing export functionality" --source stakeholder --sentiment negative

# Capture team feedback (default sentiment)
/wicked-garden:crew:feedback "Deployment process was smooth, no rollback needed" --source team

# Capture monitoring signal
/wicked-garden:crew:feedback "P95 latency dropped 40% after cache layer deploy" --source monitoring --sentiment positive
```
