---
name: gitlab-ci
description: Write secure, optimized GitLab CI/CD pipelines. Use when creating .gitlab-ci.yml files, configuring runners, or debugging pipeline issues.
---

# GitLab CI/CD Pipeline Writing

Write production-ready GitLab CI/CD pipelines with security and optimization built in.

## When to Use

- Creating new CI/CD pipelines
- Optimizing slow or expensive pipelines
- Setting up multi-environment deployments
- Debugging pipeline failures

## Core Structure

```yaml
# .gitlab-ci.yml
stages:
  - build
  - test
  - deploy

variables:
  NODE_VERSION: "20"

build:
  stage: build
  script:
    - npm ci
    - npm run build
  artifacts:
    paths:
      - dist/
```

## GitLab vs GitHub Actions

| Concept | GitHub Actions | GitLab CI |
|---------|---------------|-----------|
| Config | `.github/workflows/*.yml` | `.gitlab-ci.yml` |
| Grouping | `jobs:` | `stages:` |
| Triggers | `on:` | `rules:` |
| Secrets | `${{ secrets.X }}` | `$VARIABLE` |
| Artifacts | `actions/upload-artifact` | Built-in |
| Caching | `actions/cache` | Built-in |

## Security

### Protected Variables

```yaml
deploy:
  script:
    - deploy --token $DEPLOY_TOKEN
  # Set DEPLOY_TOKEN as protected in GitLab UI
```

### Restrict Execution

```yaml
deploy:
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
      when: manual  # Require approval
    - when: never
```

## Performance

### Caching

```yaml
default:
  cache:
    key:
      files:
        - package-lock.json
    paths:
      - node_modules/
```

### DAG (Parallel Dependencies)

```yaml
deploy:
  needs:
    - build-frontend
    - build-backend
  # Starts when both complete, skips waiting for whole stage
```

### Path Filtering

```yaml
build:
  rules:
    - changes:
        - src/**/*
        - package.json
```

### Parallel Jobs

```yaml
test:
  parallel: 4
  script:
    - npm test -- --shard=$CI_NODE_INDEX/$CI_NODE_TOTAL
```

## Common Patterns

### Include Templates

```yaml
include:
  - local: .gitlab/ci/build.yml
  - template: Security/SAST.gitlab-ci.yml
```

### Services

```yaml
test:
  services:
    - postgres:15
  variables:
    DATABASE_URL: postgresql://postgres@postgres/test
```

### Multi-Environment

```yaml
.deploy: &deploy
  script: deploy.sh
  when: manual

deploy-staging:
  <<: *deploy
  environment: staging
  rules:
    - if: $CI_COMMIT_BRANCH == "develop"

deploy-production:
  <<: *deploy
  environment: production
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
```

## References

- `refs/templates.md` - Copy-paste templates for Node.js, Python, Docker, K8s
- `refs/troubleshooting.md` - Common errors and fixes
