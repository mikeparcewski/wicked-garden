# GitLab CI Troubleshooting

Common errors and fixes.

## Pipeline Not Triggering

### Check Rules

```yaml
# Debug: Print why job is running
job:
  script:
    - echo "Source: $CI_PIPELINE_SOURCE"
    - echo "Branch: $CI_COMMIT_BRANCH"
    - echo "Tag: $CI_COMMIT_TAG"
```

### Common Causes

| Symptom | Cause | Fix |
|---------|-------|-----|
| Job never runs | Rules exclude it | Check `rules:` conditions |
| Duplicate pipelines | Both push + MR triggers | Use `workflow:rules:` |
| Missing on tags | No tag rule | Add `- if: $CI_COMMIT_TAG` |

### Prevent Duplicate Pipelines

```yaml
workflow:
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH && $CI_OPEN_MERGE_REQUESTS
      when: never
    - if: $CI_COMMIT_BRANCH
```

## Cache Issues

### Cache Not Restoring

1. Check key matches exactly
2. Verify paths exist at job end
3. Check runner has cache configured

```yaml
# Debug cache
job:
  script:
    - ls -la node_modules/ || echo "Cache miss"
```

### Force Cache Refresh

```yaml
cache:
  key: "v2-${CI_COMMIT_REF_SLUG}"  # Bump version
```

## Runner Issues

### "No Runner Available"

1. Check runner tags match job tags
2. Verify runner is online in GitLab UI
3. Check runner is allowed for project

```yaml
# Use shared runners
job:
  tags: []  # Remove specific tags
```

### Timeout

```yaml
job:
  timeout: 2h  # Increase timeout
```

## Docker-in-Docker

### "Cannot Connect to Docker Daemon"

```yaml
job:
  image: docker:24
  services:
    - docker:24-dind
  variables:
    DOCKER_HOST: tcp://docker:2376
    DOCKER_TLS_CERTDIR: "/certs"
    DOCKER_CERT_PATH: "/certs/client"
    DOCKER_TLS_VERIFY: "1"
```

### Slow Builds

```yaml
# Enable layer caching
variables:
  DOCKER_DRIVER: overlay2

# Or use Buildkit
variables:
  DOCKER_BUILDKIT: "1"
```

## Artifacts

### "Artifact Too Large"

1. Check `artifacts:expire_in` is set
2. Reduce artifact size with patterns

```yaml
artifacts:
  paths:
    - dist/
  exclude:
    - dist/**/*.map
  expire_in: 1 day
```

### Artifacts Not Passing Between Jobs

```yaml
job2:
  needs:
    - job: job1
      artifacts: true  # Explicit
```

## Variables

### "Variable Not Found"

1. Check variable exists in Settings > CI/CD
2. Check protected/masked settings
3. Check branch is protected (for protected variables)

```yaml
# Debug variables (careful with secrets!)
job:
  script:
    - echo "VAR exists: ${MY_VAR:+yes}"
```

### Expand Variables in Variables

```yaml
variables:
  BASE_URL: "https://example.com"
  API_URL: "${BASE_URL}/api"  # Works
```

## Services

### "Cannot Connect to Service"

```yaml
test:
  services:
    - name: postgres:15
      alias: db  # Use 'db' as hostname
  variables:
    DATABASE_URL: "postgresql://postgres@db/test"
```

### Service Startup Race

```yaml
before_script:
  - |
    for i in $(seq 1 30); do
      pg_isready -h db && break
      sleep 1
    done
```

## Debugging

### SSH Into Runner

```yaml
debug:
  script:
    - sleep 3600  # Keep job running
  when: manual
  # Then SSH from GitLab UI
```

### Print Environment

```yaml
debug:
  script:
    - env | sort
    - pwd
    - ls -la
```

### Check YAML Syntax

```bash
# Local validation
gitlab-ci-lint .gitlab-ci.yml

# Or use GitLab's CI Lint in pipeline editor
```
