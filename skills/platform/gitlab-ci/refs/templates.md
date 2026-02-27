# GitLab CI Templates

Copy-paste templates with optimization built in.

## Node.js

```yaml
stages:
  - test
  - build
  - deploy

default:
  image: node:20-alpine

variables:
  npm_config_cache: "$CI_PROJECT_DIR/.npm"

cache:
  key:
    files:
      - package-lock.json
  paths:
    - .npm/
    - node_modules/

test:
  stage: test
  script:
    - npm ci --cache .npm
    - npm run lint
    - npm test
  coverage: '/All files[^|]*\|[^|]*\s+([\d\.]+)/'
  artifacts:
    reports:
      coverage_report:
        coverage_format: cobertura
        path: coverage/cobertura-coverage.xml

build:
  stage: build
  script:
    - npm ci --cache .npm
    - npm run build
  artifacts:
    paths:
      - dist/
    expire_in: 1 week
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
```

## Python

```yaml
stages:
  - test
  - build

default:
  image: python:3.12-slim

variables:
  PIP_CACHE_DIR: "$CI_PROJECT_DIR/.pip-cache"

cache:
  key: ${CI_COMMIT_REF_SLUG}
  paths:
    - .pip-cache/
    - .venv/

test:
  stage: test
  before_script:
    - python -m venv .venv
    - source .venv/bin/activate
    - pip install -e ".[dev]"
  script:
    - pytest --cov=src --cov-report=xml
  coverage: '/(?i)total.*? (100(?:\.0+)?\%|[1-9]?\d(?:\.\d+)?\%)$/'
  artifacts:
    reports:
      coverage_report:
        coverage_format: cobertura
        path: coverage.xml
```

## Docker

```yaml
stages:
  - build
  - push

variables:
  DOCKER_HOST: tcp://docker:2376
  DOCKER_TLS_CERTDIR: "/certs"
  IMAGE_TAG: $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA

build:
  stage: build
  image: docker:24
  services:
    - docker:24-dind
  script:
    - docker build -t $IMAGE_TAG .
    - docker save $IMAGE_TAG > image.tar
  artifacts:
    paths:
      - image.tar
    expire_in: 1 day

push:
  stage: push
  image: docker:24
  services:
    - docker:24-dind
  before_script:
    - docker load < image.tar
    - docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY
  script:
    - docker push $IMAGE_TAG
    - docker tag $IMAGE_TAG $CI_REGISTRY_IMAGE:latest
    - docker push $CI_REGISTRY_IMAGE:latest
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
```

## Security Scanning

```yaml
include:
  - template: Security/SAST.gitlab-ci.yml
  - template: Security/Dependency-Scanning.gitlab-ci.yml
  - template: Security/Secret-Detection.gitlab-ci.yml
  - template: Security/Container-Scanning.gitlab-ci.yml

# Override defaults if needed
sast:
  stage: test
  variables:
    SAST_EXCLUDED_PATHS: "spec, test, tests"
```

## Kubernetes Deploy

```yaml
stages:
  - build
  - deploy

deploy:
  stage: deploy
  image: bitnami/kubectl:latest
  script:
    - kubectl config set-cluster k8s --server="$KUBE_URL" --certificate-authority="$KUBE_CA_PEM_FILE"
    - kubectl config set-credentials admin --token="$KUBE_TOKEN"
    - kubectl config set-context default --cluster=k8s --user=admin
    - kubectl config use-context default
    - kubectl set image deployment/$CI_PROJECT_NAME app=$CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
  environment:
    name: production
    url: https://example.com
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
      when: manual
```

## Pages

```yaml
pages:
  stage: deploy
  script:
    - npm ci
    - npm run build
    - mv dist public
  artifacts:
    paths:
      - public
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
```

## Review Apps

```yaml
deploy-review:
  stage: deploy
  script:
    - deploy-review-app.sh
  environment:
    name: review/$CI_COMMIT_REF_SLUG
    url: https://$CI_COMMIT_REF_SLUG.review.example.com
    on_stop: stop-review
  rules:
    - if: $CI_MERGE_REQUEST_IID

stop-review:
  stage: deploy
  script:
    - delete-review-app.sh
  environment:
    name: review/$CI_COMMIT_REF_SLUG
    action: stop
  rules:
    - if: $CI_MERGE_REQUEST_IID
      when: manual
```

## Scheduled Maintenance

```yaml
cleanup:
  script:
    - cleanup-old-artifacts.sh
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"
```
