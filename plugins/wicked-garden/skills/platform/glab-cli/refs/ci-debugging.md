# GitLab CI Pipeline Debugging

Quick reference for debugging GitLab CI/CD failures.

## Common Issues

### Pipeline Stuck Pending

1. Check runner availability: Settings > CI/CD > Runners
2. Verify runner tags match job tags
3. Check concurrent job limits

### Job Timeout

```yaml
job:
  timeout: 2h  # Increase if needed
```

### Cache Not Restoring

```yaml
cache:
  key: ${CI_COMMIT_REF_SLUG}  # Check key format
  paths:
    - node_modules/
  policy: pull-push  # Ensure writing enabled
```

### Variables Not Available

Protected variables only work on protected branches. Check:
- Settings > CI/CD > Variables > Protected checkbox
- Settings > Repository > Protected branches

## Debug Techniques

### Print Environment

```yaml
debug:
  script:
    - env | sort
    - echo $CI_JOB_TOKEN | wc -c  # Check token exists
```

### Keep Job Running

```yaml
debug:
  script:
    - sleep 3600
  when: manual
```

### Validate YAML

```bash
# Local
gitlab-ci-lint .gitlab-ci.yml

# Or use CI/CD > Editor > Validate
```

## Using glab CLI

```bash
# List pipelines
glab ci list

# View specific pipeline
glab ci view <id>

# Watch live
glab ci view --live

# Get job logs
glab ci trace <job-id>

# Retry failed
glab ci retry
```

## Common Error Patterns

| Error | Cause | Fix |
|-------|-------|-----|
| "No runner available" | Tag mismatch | Check job tags |
| "Job failed: exit code 1" | Script error | Check logs |
| "Artifact too large" | Size limit | Set expire_in |
| "Variable not found" | Protected var | Check protection |
