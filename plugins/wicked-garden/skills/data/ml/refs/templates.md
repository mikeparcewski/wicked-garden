# ML Output Templates

Standard templates for ML model reviews and documentation.

## Model Review Report

```markdown
## ML Model Review: {model_name}

**Type**: {classification/regression/clustering/ranking}
**Status**: {development/staging/production}
**Reviewer**: {name}
**Date**: {date}

### Summary
{2-3 sentence assessment of model readiness}

### Assessment

#### Data Quality: {score}/10
- [ ] Sufficient volume (>1000x features)
- [ ] Label quality verified
- [ ] No data leakage from target
- [ ] Class balance acceptable
- [ ] Train/test split proper

**Notes**: {observations}

#### Feature Engineering: {score}/10
- [ ] Features available at inference time
- [ ] Proper scaling/encoding applied
- [ ] No leakage from target
- [ ] Feature importance analyzed
- [ ] Missing value handling documented

**Notes**: {observations}

#### Model Choice: {score}/10
- [ ] Appropriate for problem type
- [ ] Baseline model established
- [ ] Complexity justified by improvement
- [ ] Alternatives considered and documented
- [ ] Model interpretability assessed

**Notes**: {observations}

#### Evaluation: {score}/10
- [ ] Train/test split strategy proper
- [ ] Metrics aligned with business goal
- [ ] Cross-validation performed
- [ ] Performance acceptable for use case
- [ ] Confidence intervals reported

**Metrics**:
| Metric | Train | Test | Target |
|--------|-------|------|--------|
| {metric} | {val} | {val} | {target} |

**Notes**: {observations}

#### Deployment Readiness: {score}/10
- [ ] Inference latency acceptable (<{X}ms)
- [ ] Model size appropriate
- [ ] Feature pipeline reproducible
- [ ] Monitoring instrumented
- [ ] Rollback plan documented
- [ ] A/B testing framework ready

**Notes**: {observations}

### Recommendations
| Priority | Recommendation | Impact | Effort |
|----------|----------------|--------|--------|
| P1 | {action} | HIGH | {S/M/L} |
| P2 | {action} | MEDIUM | {S/M/L} |
| P3 | {action} | LOW | {S/M/L} |

### Overall Assessment

**Score**: {total}/50

**Decision**: [APPROVE | CONDITIONAL APPROVE | NEEDS REWORK]

**Conditions** (if applicable):
1. {condition that must be met before approval}

**Next Steps**:
1. {immediate action}
2. {follow-up action}
```

## Model Card

```markdown
# Model Card: {model_name}

## Model Details
- **Name**: {model_name}
- **Version**: {version}
- **Type**: {classification/regression/etc}
- **Algorithm**: {RandomForest/XGBoost/NeuralNet/etc}
- **Framework**: {sklearn/pytorch/tensorflow}
- **Created**: {date}
- **Owner**: {team/person}

## Intended Use
- **Primary use**: {description}
- **Users**: {who will use this}
- **Out of scope**: {what this should NOT be used for}

## Training Data
- **Source**: {data source}
- **Size**: {rows} rows, {features} features
- **Date range**: {start} to {end}
- **Preprocessing**: {summary of transformations}

## Evaluation
| Metric | Value | Target |
|--------|-------|--------|
| {metric} | {val} | {target} |

## Ethical Considerations
- **Bias**: {known biases and mitigations}
- **Fairness**: {fairness testing performed}
- **Privacy**: {PII handling}

## Limitations
- {limitation 1}
- {limitation 2}

## Deployment
- **Endpoint**: {URL/service}
- **Latency**: p50={X}ms, p99={Y}ms
- **Throughput**: {requests/sec}

## Monitoring
- **Dashboards**: {links}
- **Alerts**: {configured alerts}
- **Retraining trigger**: {criteria}
```

## Experiment Log

```markdown
## Experiment: {experiment_name}

**Goal**: {what are we trying to achieve}
**Baseline**: {current performance}
**Target**: {goal performance}

### Experiment 1: {description}
**Changes**: {what was changed}
**Results**:
| Metric | Before | After | Change |
|--------|--------|-------|--------|
| {metric} | {val} | {val} | {+/-X%} |

**Conclusion**: {SUCCESS/FAILED/INCONCLUSIVE}
**Notes**: {observations}

### Experiment 2: {description}
...

### Summary
**Best configuration**: {description}
**Final performance**: {metrics}
**Next steps**: {what to try next or ship}
```
