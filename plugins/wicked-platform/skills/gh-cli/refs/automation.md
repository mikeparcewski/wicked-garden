# CI/CD Integration Examples

Integrate gh_ops.py into your automation workflows.

## GitHub Actions Integration

```yaml
name: Monitor Failures
on:
  workflow_run:
    workflows: ["CI"]
    types: [completed]

jobs:
  report:
    if: ${{ github.event.workflow_run.conclusion == 'failure' }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: |
          python3 scripts/gh_ops.py diagnose --suggest-fixes > report.json
          # Send to Slack, email, etc.
```

## Slack Notification

```bash
#!/bin/bash
result=$(python3 gh_ops.py diagnose --suggest-fixes)
if echo "$result" | jq -e '.errors | length > 0' > /dev/null; then
  curl -X POST "$SLACK_WEBHOOK" \
    -H 'Content-type: application/json' \
    -d "{\"text\": \"CI Failed: $(echo $result | jq -r '.run.url')\"}"
fi
```

## Cron Job for Health Checks

```bash
# /etc/cron.d/repo-health
0 9 * * * /usr/bin/python3 /path/to/gh_ops.py health >> /var/log/repo-health.log
```

## PR Dashboard

```bash
# Daily PR review reminder
python3 gh_ops.py pr-review-queue | jq -r '.[] | "- [\(.title)](\(.url))"'
```

## Release Automation

```bash
#!/bin/bash
# Auto-release on tag push
if [[ "$GITHUB_REF" == refs/tags/* ]]; then
  python3 gh_ops.py release --bump patch
fi
```
