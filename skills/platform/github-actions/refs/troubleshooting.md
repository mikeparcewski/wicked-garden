# GitHub Actions Troubleshooting

Common errors and fixes.

## Permission Errors

### "Resource not accessible by integration"

**Cause:** Missing permissions.

**Fix:** Add explicit permissions block:
```yaml
permissions:
  contents: write  # or whatever you need
```

### "GITHUB_TOKEN does not have access"

**Cause:** Trying to trigger another workflow or push to protected branch.

**Fix:** Use a PAT or GitHub App token:
```yaml
- uses: actions/checkout@v4
  with:
    token: ${{ secrets.PAT }}
```

## Secrets Issues

### "Secret not found" in PR from fork

**Cause:** Secrets aren't available to forked PRs (by design).

**Fix:** Use `pull_request_target` cautiously, or skip steps:
```yaml
- if: github.event.pull_request.head.repo.full_name == github.repository
  run: deploy
```

## Cache Issues

### Cache not restoring

**Common causes:**
1. Key mismatch - check hash input
2. Cache size limit (10GB per repo)
3. 7-day expiration

**Debug:**
```yaml
- uses: actions/cache@v4
  with:
    path: ~/.npm
    key: ${{ runner.os }}-npm-${{ hashFiles('**/package-lock.json') }}
    restore-keys: |
      ${{ runner.os }}-npm-
```

## Workflow Triggers

### Workflow not triggering

**Check:**
1. Branch name matches filter
2. File path matches path filter
3. No `[skip ci]` in commit message
4. Not hitting concurrent run limits

### Double triggers

**Cause:** Both `push` and `pull_request` firing.

**Fix:** Use conditional:
```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
```

Or filter:
```yaml
jobs:
  build:
    if: github.event_name == 'push' || github.event.pull_request.head.repo.full_name != github.repository
```

## Timeout Issues

### Job killed without error

**Cause:** Hit 6-hour job limit or your timeout.

**Fix:**
```yaml
jobs:
  build:
    timeout-minutes: 60  # Set explicit limit
```

### Hanging on checkout

**Cause:** Large repo or LFS files.

**Fix:**
```yaml
- uses: actions/checkout@v4
  with:
    fetch-depth: 1  # Shallow clone
    lfs: false      # Skip LFS
```

## Rate Limiting

### "API rate limit exceeded"

**Fix:** Cache API responses or reduce calls:
```yaml
- uses: actions/cache@v4
  id: api-cache
  with:
    path: .api-cache
    key: api-${{ github.run_id }}
    restore-keys: api-

- if: steps.api-cache.outputs.cache-hit != 'true'
  run: fetch-from-api
```

## Docker Issues

### Build cache not working

**Fix:** Use buildx with GHA cache:
```yaml
- uses: docker/setup-buildx-action@v3
- uses: docker/build-push-action@v5
  with:
    cache-from: type=gha
    cache-to: type=gha,mode=max
```

### Out of disk space

**Fix:** Clean up before build:
```yaml
- run: docker system prune -af
```

## Debugging

### Enable debug logging

1. Set secret `ACTIONS_RUNNER_DEBUG` to `true`
2. Re-run workflow

### Print context

```yaml
- run: echo '${{ toJSON(github) }}'
- run: env | sort
```

### SSH into runner

```yaml
- uses: mxschmitt/action-tmate@v3
  if: failure()
```
